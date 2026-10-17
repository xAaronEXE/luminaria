"""Local usage events for the insights dashboard.

Events hold counts, timings, model ids and tool or skill names. They never
hold message text, tool arguments, paths, page addresses or outputs. Each
event id is derived from what it describes, so a replayed write is ignored
instead of counted twice. Coverage starts at the first recorded event; older
activity is not reconstructed.
"""
import hashlib
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from .store import now, uid

KINDS = ('generation', 'tool', 'task', 'skill', 'compaction')
SYNC_KEYS = ('tokens_in', 'tokens_out', 'tokens_cached', 'generations', 'runs', 'active_seconds', 'wait_seconds',
             'tool_ok', 'tool_failed', 'reasoning_generations', 'skills_invoked')
FAST_MIN_TOKENS = 32
HISTORY_DAYS = 30
TOOL_FAILURES = ('error', 'interrupted')


def event_id(kind, key):
    return hashlib.sha256(f'{kind}\x1f{key}'.encode()).hexdigest()[:32]


def zone(name):
    """IANA zone when given and known, otherwise this PC's local zone."""
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name), name
        except Exception:
            pass
    local = datetime.now().astimezone().tzinfo
    return local, ''


def day_of(ts, tz):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(tz).date().isoformat()


def intervals_total(spans):
    total, end = 0.0, None
    for a, b in sorted(s for s in spans if s[1] > s[0]):
        if end is None or a > end:
            total += b - a; end = b
        elif b > end:
            total += b - end; end = b
    return total


def merged(spans):
    out = []
    for a, b in sorted(s for s in spans if s[1] > s[0]):
        if out and a <= out[-1][1]: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out


def task_times(events, started, finished):
    """Wall, active, approval-wait and paused seconds from the persisted work log."""
    requested, waits, pauses, paused_at = {}, [], [], None
    for e in sorted(events, key=lambda e: (e.get('at', 0), e.get('seq', 0))):
        kind, at = e.get('type'), e.get('at', 0)
        if kind == 'approval.requested': requested.setdefault(e.get('node'), at)
        elif kind in ('approval.allowed', 'approval.denied') and e.get('node') in requested: waits.append((requested.pop(e['node']), at))
        elif kind == 'run.interrupted' and paused_at is None: paused_at = at
        elif kind == 'run.resumed' and paused_at is not None: pauses.append((paused_at, at)); paused_at = None
    waits += [(at, finished) for at in requested.values()]
    if paused_at is not None: pauses.append((paused_at, finished))
    wall = max(0.0, finished - started)
    paused = intervals_total(pauses)
    idle = intervals_total(waits + pauses)
    return {'wall': round(wall, 1), 'active': round(max(0.0, wall - idle), 1), 'wait': round(idle - paused, 1), 'paused': round(paused, 1)}


class Usage:
    def __init__(self, store):
        self.store = store
        store.execute('CREATE TABLE IF NOT EXISTS usage_events(id TEXT PRIMARY KEY,kind TEXT,run TEXT,model TEXT,name TEXT,status TEXT,data TEXT,created REAL)')
        store.execute('CREATE INDEX IF NOT EXISTS usage_created ON usage_events(created)')

    def record(self, kind, key, run=None, model=None, name=None, status=None, created=None, **data):
        if kind not in KINDS: raise ValueError('Unknown usage event: ' + kind)
        id = event_id(kind, key)
        self.store.execute('INSERT OR IGNORE INTO usage_events VALUES(?,?,?,?,?,?,?,?)',
                           (id, kind, run, model, name, status, json.dumps({k: v for k, v in data.items() if v is not None}), created or now()))
        return id

    def generation(self, run, message_id, model, metrics, usage, timings, reasoning):
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        if cached is None and isinstance(timings, dict): cached = timings.get('cache_n')
        return self.record('generation', f'{run["id"]}:{message_id}', run=run['id'], model=model, status='done',
                           prompt_tokens=usage.get('prompt_tokens'), completion_tokens=usage.get('completion_tokens'),
                           cached_tokens=cached if isinstance(cached, int) and cached >= 0 else None,
                           elapsed=metrics.get('elapsed'), tps=metrics.get('tokens_per_second'),
                           first_token=metrics.get('first_token_seconds'), reasoning=bool(reasoning))

    def tool(self, run, action, name, status, duration_ms=None, skill=None):
        integration = name.split('__', 1)[0] if '__' in name else None
        return self.record('tool', action, run=run['id'], model=run.get('model_id'), name=name, status=status,
                           duration_ms=duration_ms, integration=integration,
                           skill=skill if status == 'done' and skill and re.fullmatch(r'[a-z0-9-]{1,60}', skill) else None)

    def skill(self, action, name):
        """User actions on skills: 'viewed', 'enabled' or 'disabled'."""
        return self.record('skill', uid(), name=name, status=action)

    def task(self, run, events, model):
        finished = run.get('finished') or now()
        times = task_times(events, run['started'], finished)
        gens = self.store.rows("SELECT data FROM usage_events WHERE kind='generation' AND run=?", (run['id'],))
        data = [json.loads(g['data']) for g in gens]
        tools = self.store.rows("SELECT status FROM usage_events WHERE kind='tool' AND run=?", (run['id'],))
        return self.record('task', run['id'], run=run['id'], model=model, status=run.get('phase', ''), created=finished,
                           **times, generations=len(data),
                           tokens_in=sum(d.get('prompt_tokens') or 0 for d in data),
                           tokens_out=sum(d.get('completion_tokens') or 0 for d in data),
                           tool_ok=sum(t['status'] == 'done' for t in tools),
                           tool_failed=sum(t['status'] in TOOL_FAILURES for t in tools),
                           reasoning=bool(run.get('reasoning')), planning=bool(run.get('plan_only')),
                           compaction=bool(run.get('compact_only')))

    def rows(self, kind=None):
        sql, args = 'SELECT * FROM usage_events', ()
        if kind: sql, args = sql + ' WHERE kind=?', (kind,)
        return [dict(r, data=json.loads(r['data'] or '{}')) for r in self.store.rows(sql + ' ORDER BY created', args)]

    def days(self, tz):
        """Daily totals in the given zone. These are the only values that can leave this PC."""
        out = {}
        def bucket(ts):
            return out.setdefault(day_of(ts, tz), {k: 0 for k in SYNC_KEYS})
        for e in self.rows():
            d, day = e['data'], bucket(e['created'])
            if e['kind'] == 'generation':
                day['generations'] += 1
                day['tokens_in'] += d.get('prompt_tokens') or 0
                day['tokens_out'] += d.get('completion_tokens') or 0
                day['tokens_cached'] += d.get('cached_tokens') or 0
                day['reasoning_generations'] += 1 if d.get('reasoning') else 0
            elif e['kind'] == 'tool':
                day['tool_ok'] += e['status'] == 'done'
                day['tool_failed'] += e['status'] in TOOL_FAILURES
                day['skills_invoked'] += e['name'] == 'load_skill' and e['status'] == 'done'
            elif e['kind'] == 'task':
                day['runs'] += 1
                day['active_seconds'] += round(d.get('active') or 0)
                day['wait_seconds'] += round(d.get('wait') or 0)
        return [{'day': k, 'metrics': {m: int(v) for m, v in out[k].items()}} for k in sorted(out)]

    def summary(self, tz_name='', today=None):
        tz, tz_used = zone(tz_name)
        events = self.rows()
        gens = [e for e in events if e['kind'] == 'generation']
        tools = [e for e in events if e['kind'] == 'tool']
        tasks = [e for e in events if e['kind'] == 'task']
        skills = [e for e in events if e['kind'] == 'skill']
        today = today or datetime.now(timezone.utc).astimezone(tz).date()
        result = {'coverage_start': events[0]['created'] if events else None, 'events': len(events),
                  'timezone': tz_used or 'local', 'timezone_label': tz_used or (datetime.now().astimezone(tz).tzname() or 'this PC'),
                  'timezone_requested': tz_name or '', 'timezone_valid': not tz_name or tz_used == tz_name, 'missing': []}
        if not events:
            result['missing'].append('Nothing recorded yet. Insights start with the next task; earlier activity is not reconstructed.')
            return result
        cached = [g['data']['cached_tokens'] for g in gens if g['data'].get('cached_tokens') is not None]
        tin = sum(g['data'].get('prompt_tokens') or 0 for g in gens); tout = sum(g['data'].get('completion_tokens') or 0 for g in gens)
        result['lifetime'] = {'tokens_in': tin, 'tokens_out': tout, 'total': tin + tout, 'generations': len(gens),
                              'tasks': len(tasks), 'cached': sum(cached) if cached else None, 'cached_measured': len(cached)}
        if gens and not cached: result['missing'].append('Reused (cached) prompt tokens: the model server has not reported them.')
        elif cached and len(cached) < len(gens): result['missing'].append(f'Reused (cached) prompt tokens were reported for {len(cached)} of {len(gens)} responses.')
        unreported = sum(1 for g in gens if g['data'].get('completion_tokens') is None)
        if unreported: result['missing'].append(f'{unreported} responses arrived without token counts and are left out of token totals.')
        daily = {d['day']: d['metrics'] for d in self.days(tz)}
        busiest = max(daily.items(), key=lambda kv: (kv[1]['tokens_in'] + kv[1]['tokens_out'], kv[0]), default=None)
        if busiest and busiest[1]['tokens_in'] + busiest[1]['tokens_out']:
            result['busiest_day'] = {'day': busiest[0], 'tokens': busiest[1]['tokens_in'] + busiest[1]['tokens_out'], 'generations': busiest[1]['generations']}
        if tasks:
            big = max(tasks, key=lambda t: (t['data'].get('tokens_in', 0) + t['data'].get('tokens_out', 0), t['created']))
            long = max(tasks, key=lambda t: (t['data'].get('active', 0), t['created']))
            result['largest_task'] = {'run': big['run'], 'day': day_of(big['created'], tz), 'tokens': big['data'].get('tokens_in', 0) + big['data'].get('tokens_out', 0), 'generations': big['data'].get('generations', 0)}
            result['longest_task'] = {'run': long['run'], 'day': day_of(long['created'], tz), **{k: long['data'].get(k, 0) for k in ('active', 'wait', 'paused', 'wall')}}
        else: result['missing'].append('Task length: no finished task recorded yet.')
        timed = [g for g in gens if g['data'].get('tps') and (g['data'].get('completion_tokens') or 0) >= FAST_MIN_TOKENS]
        if timed:
            fast = max(timed, key=lambda g: g['data']['tps'])
            result['fastest'] = {'tps': fast['data']['tps'], 'model': fast['model'], 'day': day_of(fast['created'], tz), 'tokens': fast['data']['completion_tokens']}
        elif gens: result['missing'].append(f'Fastest speed: no response of at least {FAST_MIN_TOKENS} generated tokens with timing yet.')
        result['streak'] = streaks(sorted(d for d, m in daily.items() if m['generations']), today)
        start = datetime.fromtimestamp(result['coverage_start'], timezone.utc).astimezone(tz).date()
        history = []
        for i in range(HISTORY_DAYS - 1, -1, -1):
            day = today - timedelta(days=i)
            m = daily.get(day.isoformat())
            history.append({'day': day.isoformat(), 'covered': day >= start, 'tokens_in': m['tokens_in'] if m else 0, 'tokens_out': m['tokens_out'] if m else 0})
        result['history'] = history
        result['reasoning'] = {'generations': sum(1 for g in gens if g['data'].get('reasoning')), 'of': len(gens),
                               'tasks': sum(1 for t in tasks if t['data'].get('reasoning')), 'levels': None}
        invoked = {}
        for t in tools:
            if t['name'] == 'load_skill' and t['status'] == 'done' and t['data'].get('skill'): invoked[t['data']['skill']] = invoked.get(t['data']['skill'], 0) + 1
        result['skills'] = {'browsed_by_assistant': sum(1 for t in tools if t['name'] == 'list_skills'),
                            'viewed': sum(1 for s in skills if s['status'] == 'viewed'),
                            'enabled': sum(1 for s in skills if s['status'] == 'enabled'),
                            'disabled': sum(1 for s in skills if s['status'] == 'disabled'),
                            'invoked': sum(invoked.values()),
                            'top': [{'name': k, 'count': v} for k, v in sorted(invoked.items(), key=lambda kv: -kv[1])[:6]]}
        result['tools'] = tally(tools, lambda t: t['name'])[:10]
        result['integrations'] = tally([t for t in tools if t['data'].get('integration')], lambda t: t['data']['integration'])
        models = {}
        for g in gens:
            entry = models.setdefault(g['model'] or 'unknown', {'model': g['model'] or 'unknown', 'generations': 0, 'tokens_out': 0, 'speeds': []})
            entry['generations'] += 1; entry['tokens_out'] += g['data'].get('completion_tokens') or 0
            if g['data'].get('tps') and (g['data'].get('completion_tokens') or 0) >= FAST_MIN_TOKENS: entry['speeds'].append(g['data']['tps'])
        result['models'] = sorted(({**{k: v for k, v in m.items() if k != 'speeds'}, 'median_tps': round(statistics.median(m['speeds']), 1) if m['speeds'] else None} for m in models.values()), key=lambda m: -m['generations'])
        return result

    def compaction(self, recent=8):
        """Compaction health: duration, tokens before and after, summary size, validations and history lookups."""
        runs = self.rows('compaction')
        done = [r for r in runs if r['status'] == 'done']
        lookups = self.store.rows("SELECT COUNT(*) AS n FROM usage_events WHERE kind='tool' AND name IN ('history_read','memory_search')")[0]['n']
        avg = lambda key: round(statistics.mean(r['data'][key] for r in done if r['data'].get(key) is not None), 1) if any(r['data'].get(key) is not None for r in done) else None
        saved = [1 - r['data']['tokens_after'] / r['data']['tokens_before'] for r in done if r['data'].get('tokens_before') and r['data'].get('tokens_after') is not None]
        return {'runs': len(runs), 'completed': len(done), 'failed': len(runs) - len(done),
                'failed_validations': sum(r['data'].get('failed_validations', 0) for r in runs),
                'restored_references': sum(r['data'].get('restored', 0) for r in done),
                'average_seconds': avg('seconds'), 'average_summary_tokens': avg('summary_tokens'),
                'average_reduction': round(100 * statistics.mean(saved)) if saved else None,
                'history_lookups': lookups,
                'recent': [{'created': r['created'], 'status': r['status'], **{k: r['data'].get(k) for k in ('seconds', 'tokens_before', 'tokens_after', 'summary_tokens', 'chunks', 'failed_validations', 'restored', 'forced', 'reason')}} for r in runs[-recent:]][::-1]}

    def export(self, tz_name=''):
        tz, used = zone(tz_name)
        return {'exported_at': now(), 'timezone': used or 'local', 'note': 'Counts and timings only. No message text, tool arguments, paths or outputs are recorded.',
                'events': [{k: e[k] for k in ('id', 'kind', 'run', 'model', 'name', 'status', 'created', 'data')} for e in self.rows()],
                'days': self.days(tz)}

    def delete(self):
        with self.store.db:
            n = self.store.db.execute('DELETE FROM usage_events').rowcount
        return n


def streaks(days, today):
    """Consecutive calendar days with at least one completed model response."""
    if not days: return {'current': 0, 'longest': 0, 'qualifying': 'a day with at least one completed model response'}
    dates = [datetime.fromisoformat(d).date() for d in days]
    longest = run = 1
    for a, b in zip(dates, dates[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        longest = max(longest, run)
    current = 0
    if (today - dates[-1]).days <= 1:
        current = 1
        for a, b in zip(reversed(dates[:-1]), reversed(dates[1:])):
            if (b - a).days != 1: break
            current += 1
    return {'current': current, 'longest': longest, 'last_active': days[-1], 'qualifying': 'a day with at least one completed model response'}


def tally(items, key):
    out = {}
    for t in items:
        entry = out.setdefault(key(t), {'name': key(t), 'ok': 0, 'failed': 0, 'denied': 0})
        if t['status'] == 'done': entry['ok'] += 1
        elif t['status'] == 'denied': entry['denied'] += 1
        elif t['status'] in TOOL_FAILURES: entry['failed'] += 1
    return sorted(out.values(), key=lambda e: -(e['ok'] + e['failed'] + e['denied']))


SYNC_BATCH = 90


def sync_state(store):
    state = store.setting('insights_sync', None) or {}
    if not re.fullmatch('[a-f0-9]{32}', str(state.get('device', ''))):
        state['device'] = uid(); store.set_setting('insights_sync', state)
    return state


async def service(method, path, payload=None):
    import httpx
    from .identity import ORIGIN, _any_session, forget_gate
    token = _any_session('Sign in to sync insights across your devices.')
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.request(method, ORIGIN + path, json=payload, headers={'Authorization': 'Bearer ' + token})
    if response.status_code == 404: raise ValueError('Insights sync needs the updated sign-in service. Your insights stay on this PC.')
    if response.status_code == 401: forget_gate(); raise ValueError('Your sign-in on this PC expired or was revoked. Sign in again.')
    if response.status_code == 400: raise ValueError(str(response.json().get('error', 'The sign-in service rejected the insights upload.'))[:200])
    response.raise_for_status()
    return response.json()


async def sync(store, usage, tz_name=''):
    """Upload this PC's daily totals. Each day replaces the previous upload for this PC, so retries never double-count."""
    state = sync_state(store)
    tz, _ = zone(tz_name)
    days = usage.days(tz)
    sent = 0
    for i in range(0, len(days), SYNC_BATCH):
        batch = days[i:i + SYNC_BATCH]
        await service('POST', '/insights/days', {'device': state['device'], 'days': batch})
        sent += len(batch)
    combined = await service('GET', '/insights/days')
    state.update(last_sync=now(), last_error=None, days_sent=sent)
    store.set_setting('insights_sync', state)
    return {'sent': sent, 'account': account_view(combined)}


def account_view(combined):
    days = [d for d in combined.get('days', []) if isinstance(d, dict) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(d.get('day', '')))]
    metric = lambda d, k: int((d.get('metrics') or {}).get(k) or 0)
    active = sorted(d['day'] for d in days if metric(d, 'generations'))
    tin = sum(metric(d, 'tokens_in') for d in days); tout = sum(metric(d, 'tokens_out') for d in days)
    return {'devices': int(combined.get('devices') or 0), 'days': len(days), 'active_days': len(active),
            'tokens_in': tin, 'tokens_out': tout, 'total': tin + tout,
            'active_seconds': sum(metric(d, 'active_seconds') for d in days),
            'streak': streaks(active, datetime.now().astimezone().date()), 'first_day': days[0]['day'] if days else None}
