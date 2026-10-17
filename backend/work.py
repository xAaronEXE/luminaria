"""Structured, persisted work events for the spatial workspace.

Events describe what the app observed: run lifecycle, model rounds, tool
execution, approvals, compaction and model-provided plans. They carry ids and
evidence references, never tool arguments, outputs or message text. A plan or
reasoning entry is labelled as model-provided; tool events are execution
evidence recorded by the engine itself.
"""
import hashlib
import json
from .store import now

TYPES = {
    'run.started', 'run.completed', 'run.failed', 'run.cancelled', 'run.interrupted', 'run.resumed',
    'plan.created', 'plan.revised',
    'generation.started', 'generation.completed', 'reasoning.started',
    'tool.requested', 'tool.started', 'tool.completed', 'tool.failed', 'tool.denied', 'tool.interrupted',
    'approval.requested', 'approval.allowed', 'approval.denied',
    'compaction.started', 'compaction.completed', 'compaction.skipped',
    'routing.started', 'routing.completed',
}
REGIONS = ('planning', 'memory', 'retrieval', 'files', 'tools', 'generation', 'verification')
PLAN_STATUSES = ('pending', 'active', 'done', 'blocked', 'skipped')

def region_for(tool):
    """Functional region from the tool's identity, not from its content."""
    if tool == 'update_plan': return 'planning'
    if tool in ('memory_search', 'history_read', 'remember'): return 'memory'
    if tool in ('web_search', 'web_fetch', 'discover_tools', 'list_skills', 'load_skill'): return 'retrieval'
    if tool in ('list_files', 'read_file', 'write_file', 'edit_file', 'delete_file', 'search_files'): return 'files'
    if tool in ('run_command', 'run_code'): return 'verification'
    return 'tools'

def event_id(run, *parts):
    return hashlib.sha256('\x1f'.join((run, *map(str, parts))).encode()).hexdigest()[:24]

def plan_steps(args):
    """Validate model-provided plan steps. Dependencies must reference known step ids."""
    steps = args.get('steps') if isinstance(args, dict) else None
    if not isinstance(steps, list) or not 1 <= len(steps) <= 24: raise ValueError('Provide 1 to 24 plan steps')
    out, ids = [], set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict): raise ValueError('Each plan step must be an object')
        sid = str(step.get('id') or f's{i+1}')[:40]
        title = str(step.get('title', '')).strip()[:160]
        status = step.get('status', 'pending')
        if not title: raise ValueError('Each plan step needs a title')
        if status not in PLAN_STATUSES: raise ValueError('Plan step status must be one of: ' + ', '.join(PLAN_STATUSES))
        if sid in ids: raise ValueError('Plan step ids must be unique')
        ids.add(sid); out.append({'id': sid, 'title': title, 'status': status, 'depends_on': [str(d)[:40] for d in step.get('depends_on', []) or []]} | ({'detail': str(step['detail']).strip()[:400]} if str(step.get('detail') or '').strip() else {}))
    for step in out:
        unknown = [d for d in step['depends_on'] if d not in ids or d == step['id']]
        if unknown: raise ValueError('Unknown plan dependency: ' + ', '.join(unknown))
    return out

class WorkLog:
    def __init__(self, store, broadcast):
        self.store = store; self.broadcast = broadcast
        store.execute('CREATE TABLE IF NOT EXISTS run_events(id TEXT PRIMARY KEY,chat TEXT,run TEXT,seq INTEGER,payload TEXT,created REAL)')
        store.execute('CREATE INDEX IF NOT EXISTS run_events_chat ON run_events(chat,run,seq)')

    def record(self, run, kind, key='', **fields):
        """Persist once and broadcast. Replays with the same key are ignored."""
        if kind not in TYPES: raise ValueError('Unknown work event: ' + kind)
        id = event_id(run['id'], kind, key)
        if self.store.rows('SELECT 1 FROM run_events WHERE id=?', (id,)): return None
        seq = (self.store.rows('SELECT MAX(seq) AS s FROM run_events WHERE run=?', (run['id'],))[0]['s'] or 0) + 1
        event = {'id': id, 'seq': seq, 'chat': run['chat'], 'run': run['id'], 'type': kind, 'at': now(),
                 **{k: v for k, v in fields.items() if v is not None}}
        self.store.execute('INSERT OR IGNORE INTO run_events VALUES(?,?,?,?,?,?)',
                           (id, run['chat'], run['id'], seq, json.dumps(event, ensure_ascii=False), event['at']))
        self.broadcast({'type': 'work', 'event': event})
        return event

    def events(self, chat, runs=12, limit=3000):
        """Most recent runs for a chat, oldest first, ordered by per-run sequence."""
        recent = [r['run'] for r in self.store.rows('SELECT run,MIN(created) AS c FROM run_events WHERE chat=? GROUP BY run ORDER BY c DESC LIMIT ?', (chat, max(1, min(runs, 50))))]
        if not recent: return []
        marks = ','.join('?' * len(recent))
        rows = self.store.rows(f'SELECT payload FROM run_events WHERE chat=? AND run IN ({marks}) ORDER BY created,seq LIMIT ?', (chat, *recent, limit))
        return [json.loads(r['payload']) for r in rows]
