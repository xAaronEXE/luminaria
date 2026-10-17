"""Deterministic progress reports for runs that stop before the model finishes.

Built only from the action journal and the saved plan, so a report is always
available even when the model cannot be called or the context is full.
"""
import hashlib, json

ROUND_LIMIT = 18
REPEAT_LIMIT = 3
SIDE_EFFECTS = frozenset({'write_file', 'edit_file', 'delete_file', 'run_command', 'run_code', 'web_fetch', 'remember', 'create_schedule'})
CHANGES = frozenset({'write_file', 'edit_file', 'delete_file'})

def call_key(name, args):
    return name + ':' + hashlib.sha256(json.dumps(args, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

def target(args):
    if not isinstance(args, dict): return ''
    for key in ('path', 'url', 'query', 'name', 'title', 'category', 'language'):
        if args.get(key): return str(args[key])[:120]
    if args.get('command'): return str(args['command'])[:80]
    return ''

def excerpt(result, limit=160):
    if not result: return ''
    text = result.get('text', '') if isinstance(result, dict) else str(result)
    if text.startswith('{'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ('error', 'message', 'title', 'summary', 'text'):
                    if isinstance(data.get(key), str) and data[key].strip(): text = data[key]; break
        except ValueError: pass
    text = ' '.join(text.split())
    return text[:limit] + ('…' if len(text) > limit else '')

def report(actions, plan=None, reason='limit', stalled=None):
    """Markdown summary. `actions` are store rows (args and result decoded) from this run."""
    done = [a for a in actions if a['status'] == 'done' and a['name'] != 'update_plan']
    failed = [a for a in actions if a['status'] in ('error', 'interrupted')]
    denied = [a for a in actions if a['status'] == 'denied']
    if reason == 'repeated':
        lines = [f"**Paused: the same step failed {REPEAT_LIMIT} times.** Retrying it again would not help, so I stopped here instead of looping."]
        if stalled: lines.append(f"The failing step was `{stalled}`.")
    elif reason == 'error':
        lines = ['**The task stopped before a final answer could be written.** Here is what had already happened.']
    else:
        lines = [f"**Paused after {ROUND_LIMIT} tool rounds.** Nothing was lost. This is a checkpoint, not a failure."]
    if done:
        lines.append(f"\n**Completed ({len(done)})**")
        for a in done[-12:]:
            what = target(a['args']); found = excerpt(a.get('result'))
            lines.append(f"- {a['name'].replace('__', ' · ')}" + (f" `{what}`" if what else '') + (f": {found}" if found else ''))
        if len(done) > 12: lines.append(f"- …and {len(done) - 12} earlier actions (see Activity)")
    changed = [a for a in done if a['name'] in CHANGES]
    lines.append('\n**Changes made:** ' + (', '.join(f"{a['name'].split('_')[0]} `{target(a['args'])}`" for a in changed) if changed else 'none. No files were written, edited or deleted.'))
    if failed:
        lines.append(f"\n**Failed ({len(failed)})**")
        for a in failed[-6:]:
            lines.append(f"- {a['name']}" + (f" `{target(a['args'])}`" if target(a['args']) else '') + f": {excerpt(a.get('result')) or 'no error detail recorded'}")
    if denied: lines.append('\n**Declined by you:** ' + ', '.join(sorted({a['name'] for a in denied})))
    remaining = [s for s in (plan or {}).get('steps', []) if s.get('status') not in ('done', 'skipped')]
    if remaining:
        lines.append('\n**Still to do (from the plan)**')
        lines += [f"- {s['title']}" + (' (blocked)' if s.get('status') == 'blocked' else '') for s in remaining[:10]]
    if not done:
        lines.append('\nNo useful results were produced in this run' + (', mainly because of the failures above.' if failed else '.'))
    lines.append('\nChoose **Continue task** to pick up from here. Steps that already changed something will not be repeated.')
    return '\n'.join(lines)
