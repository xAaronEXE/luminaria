"""Rules for carrying out a plan. The harness, never the model, decides what state a step is in.

A step has a status (pending, active, done, blocked, skipped) and, once it ends, a verdict:
  passed      its check proved the result
  unverified  work happened but nothing proved it
  failed      its check ran and did not pass
Everything here is deterministic and reads only the plan and the action journal.
"""
import hashlib, json, re
from pathlib import Path
from .checkpoint import SIDE_EFFECTS, CHANGES, call_key, may_change, result_data

ATTEMPTS = 3            # tries per step before it is blocked
CHECK_TYPES = ('command', 'file_exists', 'file_contains')
HARNESS_FIELDS = ('status', 'verdict', 'reason', 'attempts', 'note', 'check_result', 'fingerprint', 'added_by', 'evidence')
GO_AHEAD = re.compile(r"^\s*(?:ok(?:ay)?[,.! ]*|yes[,.! ]*|yep[,.! ]*|sure[,.! ]*|great[,.! ]*|please[,.! ]*|now[,.! ]*)*"
                      r"(?:go ahead|go for it|do it|proceed|continue|carry (?:it|this|that|the plan) out|carry out the (?:saved )?plan|"
                      r"run the plan|execute the plan|start the plan|implement (?:it|this|that|the plan)|build it|make it happen|"
                      r"let'?s (?:go|do it|do this|start|begin)|start|begin|resume|keep going|finish (?:it|the plan))"
                      r"(?:\s+(?:with|on)\s+the\s+plan)?(?:[,. ]+(?:please|now|then|one step at a time))*[.! ]*$", re.I)
TRIVIAL = re.compile(r'^\s*(?:true|exit(?:\s+0)?|echo\b.*|write-(?:host|output)\b.*|rem\b.*|:|\$true|cd\b.*|dir|ls|pwd)\s*;?\s*$', re.I)


def unfinished(plan):
    return [s for s in (plan or {}).get('steps', []) if s.get('status') not in ('done', 'skipped')]


def protected_paths(args):
    paths=args.get('protected_paths', [])
    if not isinstance(paths, list) or len(paths)>24 or any(not isinstance(path,str) or not path.strip() or len(path)>500 for path in paths):
        raise ValueError('Supply up to 24 protected file or folder paths.')
    return list(dict.fromkeys(path.strip() for path in paths))


def step_order(steps):
    """Preserve plan order among eligible steps, including forward dependencies."""
    remaining = {step['id']: set(step.get('depends_on', [])) for step in steps}
    ordered = []
    while remaining:
        ready = next((sid for sid, deps in remaining.items() if not deps), None)
        if ready is None:
            raise ValueError('Plan dependencies contain a cycle or reference a missing step.')
        ordered.append(ready)
        del remaining[ready]
        for deps in remaining.values():
            deps.discard(ready)
    return ordered


def unmet_dependencies(step, steps):
    passed = {s['id'] for s in steps if s.get('status') == 'done' and s.get('verdict') == 'passed'}
    return [s['title'] for s in steps if s['id'] in step.get('depends_on', []) and s['id'] not in passed]


def wants_plan_run(text, plan):
    """A short "go ahead" starts the step runner only when this chat has a plan with steps left."""
    return bool(unfinished(plan)) and len(text or '') <= 120 and bool(GO_AHEAD.match(text or ''))


def clean_check(check):
    """Validate a step's check. A check that cannot fail proves nothing, so it is refused."""
    if check in (None, {}, ''): return None
    if not isinstance(check, dict) or check.get('type') not in CHECK_TYPES:
        raise ValueError('A step check needs a type: ' + ', '.join(CHECK_TYPES))
    kind = check['type']
    if kind == 'command':
        command = str(check.get('command') or '').strip()
        if not command or TRIVIAL.match(command): raise ValueError('A check command must actually test the result (not echo, exit 0 or true)')
        if len(command)>400: raise ValueError('A check command is limited to 400 characters.')
        out = {'type': kind, 'command': command}
        inputs = check.get('inputs', [])
        if not isinstance(inputs, list) or len(inputs)>128 or any(not isinstance(path, str) or not path.strip() for path in inputs):
            raise ValueError('Command check inputs must be a list of up to 128 workspace file paths.')
        if inputs: out['inputs'] = list(dict.fromkeys(inputs))
        if check.get('python') is True: out['python'] = True
        if str(check.get('expect') or '').strip(): out['expect'] = str(check['expect']).strip()[:200]
        return out
    path = str(check.get('path') or '').strip()
    if not path: raise ValueError('A file check needs a path')
    if kind == 'file_contains':
        text = str(check.get('text') or '')
        if not text.strip(): raise ValueError('file_contains needs the text to look for')
        return {'type': kind, 'path': path[:400], 'text': text[:300]}
    return {'type': kind, 'path': path[:400]}


def merge_plan(saved, proposed, plan_run):
    """Combine the model's plan update with the saved plan.

    While the plan is being carried out, existing steps are untouchable: the model may only add new steps.
    Otherwise the model may reshape the plan, but a step the harness already judged keeps that judgement,
    and a step the model calls done is recorded as done-but-unverified.
    """
    old = {s['id']: s for s in (saved or {}).get('steps', [])}
    if plan_run and old:
        steps = [dict(s) for s in saved['steps']]
        for step in proposed:
            if step['id'] not in old:
                steps.append({**step, 'status': 'pending', 'added_by': 'model', 'depends_on': [d for d in step.get('depends_on', []) if d in old]})
        return steps
    steps = []
    for step in proposed:
        before = old.get(step['id'])
        revision_fields = ('title', 'detail', 'check')
        if before and (any(before.get(key) != step.get(key) for key in revision_fields)
                       or before.get('depends_on', []) != step.get('depends_on', [])):
            step = {**step, 'status': 'pending'}
        elif before and before.get('verdict'):
            step = {**step, **{k: before[k] for k in HARNESS_FIELDS if k in before}}
        elif step['status'] == 'done':
            step = {**step, 'verdict': 'unverified', 'reason': 'Marked done by the model; not checked'}
        steps.append(step)
    return steps


def step_actions(store, chat, step_id, since):
    rows = store.rows('SELECT * FROM actions WHERE chat=? AND step=? AND created>=? ORDER BY created', (chat, step_id, since))
    for r in rows:
        try: r['args'] = json.loads(r['args'] or '{}')
        except ValueError: r['args'] = {}
        try: r['result'] = json.loads(r['result']) if r.get('result') else None
        except ValueError: r['result'] = None
    return rows


def plan_actions(store, chat, step_ids):
    """Every action taken in any step of this plan, across runs (Continue starts a new run)."""
    ids = [str(i) for i in step_ids]
    if not ids: return []
    rows = store.rows(f'SELECT name,args,status FROM actions WHERE chat=? AND step IN ({",".join("?" * len(ids))})', (chat, *ids))
    for r in rows:
        try: r['args'] = json.loads(r['args'] or '{}')
        except ValueError: r['args'] = {}
    return rows


def check_command_matches(check, args):
    return (str(args.get('command') or '').strip() == check['command']
            and bool(args.get('python')) == bool(check.get('python'))
            and set(args.get('inputs', [])) == set(check.get('inputs', [])))


def check_command_instruction(check):
    command = check['command']
    options = {key: check[key] for key in ('inputs', 'python') if key in check}
    return f'{command} (options: {json.dumps(options, ensure_ascii=False)})' if options else command


def _text(result):
    data = result_data({'result': result}) if isinstance(result, dict) else {}
    return ' '.join(str(data.get(k, '')) for k in ('stdout', 'stderr', 'output', 'text', 'message', 'error'))[:4000] or json.dumps(result)[:2000] if result else ''


def matching_check_actions(check, actions):
    return [(i, action) for i, action in enumerate(actions)
            if action['name']=='run_command' and action['status'] in ('done', 'error')
            and not (action.get('result') or {}).get('replayed')
            and check_command_matches(check, action['args'])]


def run_check(check, actions, resolve):
    """(outcome, detail). outcome: passed, failed or not_run. File checks are read here; a command check is
    judged from the journal: the newest time that exact command ran in this step."""
    if not check: return 'none', ''
    kind = check['type']
    if kind in ('file_exists', 'file_contains'):
        try: path = Path(resolve(check['path']))
        except (PermissionError, ValueError, OSError) as error: return 'failed', str(error)[:200]
        if not path.exists(): return 'failed', f'{check["path"]} does not exist'
        if kind == 'file_exists':
            if path.is_file() and path.stat().st_size == 0: return 'failed', f'{check["path"]} is empty'
            return 'passed', f'{check["path"]} exists'
        try: body = path.read_text(encoding='utf-8', errors='replace')
        except OSError as error: return 'failed', str(error)[:200]
        return ('passed', f'{check["path"]} contains the expected text') if check['text'] in body else ('failed', f'{check["path"]} does not contain: {check["text"][:80]}')
    matched = matching_check_actions(check, actions)
    if not matched: return 'not_run', 'The check command was not run'
    index, last = matched[-1]
    if last['status'] == 'done' and any(
        may_change(action) and action['status'] in ('done', 'error')
        and not (action.get('result') or {}).get('replayed') for action in actions[index + 1:]
    ):
        return 'not_run', 'Work changed after the check command ran. Run the check again.'
    output = _text(last['result'])
    if last['status'] != 'done': return 'failed', ('Check failed: ' + output.strip())[:400]
    if check.get('expect') and check['expect'].lower() not in output.lower(): return 'failed', f'Check ran but its output did not contain: {check["expect"][:80]}'
    return 'passed', 'Check command succeeded'


def evidence(check, plan_actions, resolve):
    """How independent a passed check is.
    independent: a command that only uses files that existed before this plan started (your own tests or tools).
    self_written: the command runs a test or script the model wrote or changed during this plan, so a pass proves less.
    file: a file check (the deliverable exists or contains the expected text)."""
    if not check: return None
    if check['type'] != 'command': return 'file'
    touched = set()
    for a in plan_actions:
        if a['name'] in CHANGES and a['status'] == 'done':
            try: touched.add(Path(resolve(a['args'].get('path', ''))).name.lower())
            except (PermissionError, ValueError, OSError): pass
        if a['name'] == 'run_code' and a['status'] == 'done': touched.add('(script)')
    words = {Path(w.strip('"\'')).name.lower() for w in re.split(r'[\s;|&()]+', check['command']) if w}
    return 'self_written' if touched & words else 'independent'


def unknown_outcome(actions):
    """A side-effecting action that never reported back. Its result is unknown, so nothing is retried on top of it."""
    return next((a for a in actions if a['status'] in ('running', 'interrupted') and (a['name'] in SIDE_EFFECTS or '__' in a['name'])), None)


def fingerprint(actions, check_outcome, resolve=None):
    """What this attempt changed. The same value twice in a row means the model is not getting anywhere."""
    done = sorted({call_key(a['name'], a['args']) for a in actions if a['status'] == 'done' and (a['name'] in SIDE_EFFECTS or '__' in a['name'])})
    files = []
    for a in actions:
        if a['name'] in CHANGES and a['status'] == 'done' and resolve:
            try:
                p = Path(resolve(a['args'].get('path', '')))
                files.append((str(p), hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else 'gone'))
            except (PermissionError, ValueError, OSError): pass
    failures = sorted({call_key(a['name'], a['args']) for a in actions if a['status'] == 'error'})
    return hashlib.sha256(json.dumps([done, sorted(set(files)), failures, check_outcome], sort_keys=True).encode()).hexdigest()[:24]


def judge(step, actions, flags, check_outcome, check_detail, previous_fingerprint, current_fingerprint, attempt):
    """Decide what happens to a step after an attempt.

    Returns (decision, verdict, reason) where decision is 'done', 'retry' or 'blocked'.
    flags: denied, checkpoint (ran out of rounds), stalled (repeated itself).
    """
    waiting = unknown_outcome(actions)
    if waiting: return 'blocked', None, f'{waiting["name"]} was interrupted and its outcome is unknown. Check what it did before continuing.'
    if flags.get('denied'): return 'blocked', None, 'You declined an action this step needed.'
    if check_outcome == 'passed': return 'done', 'passed', check_detail
    progressed = current_fingerprint != previous_fingerprint
    can_retry = attempt < ATTEMPTS and (progressed or attempt == 1)
    if check_outcome == 'failed':
        return ('retry', None, check_detail) if can_retry else ('blocked', 'failed', check_detail + ('' if progressed else ' No progress between attempts.'))
    if flags.get('checkpoint') or flags.get('stalled'):
        why = 'ran out of rounds' if flags.get('checkpoint') else 'kept repeating the same action'
        if can_retry and progressed: return 'retry', None, f'The step {why} before finishing.'
        return 'blocked', None, f'The step {why} and made no further progress.'
    worked = [a for a in actions if a['status'] == 'done']
    if check_outcome == 'not_run':
        return ('retry', None, check_detail) if can_retry else ('blocked', 'unverified', check_detail)
    if not worked:
        return ('retry', None, 'No action was taken in this step.') if attempt == 1 else ('done', 'unverified', 'No action was taken in this step; only a reply was given.')
    return 'done', 'unverified', 'Work was done, but this step had no check to prove it.'


def retry_instruction(step, reason, check, attempt):
    lines = [f'[Step not finished, attempt {attempt + 1} of {ATTEMPTS}] {step["title"]}', f'Why it is not finished: {reason}']
    if check and check['type'] == 'command': lines.append(f'The check for this step is the command: {check_command_instruction(check)}\nRun it with run_command and fix the work until it succeeds.')
    elif check: lines.append('The check for this step: ' + (f'{check["path"]} must exist' if check['type'] == 'file_exists' else f'{check["path"]} must contain "{check["text"][:80]}"') + '.')
    lines.append('Use a different approach from what was already tried. Do the work with tools now; do not describe it. '
                 'If the step truly needs no action, say exactly why in one sentence.')
    return '\n'.join(lines)


def summary(plan):
    """Plain-language result of a plan run, built only from recorded step states."""
    steps = (plan or {}).get('steps', [])
    if not steps: return ''
    count = lambda test: sum(1 for s in steps if test(s))
    passed = count(lambda s: s.get('status') == 'done' and s.get('verdict') == 'passed')
    unverified = [s for s in steps if s.get('status') == 'done' and s.get('verdict') != 'passed']
    blocked = [s for s in steps if s.get('status') == 'blocked']
    skipped = count(lambda s: s.get('status') == 'skipped')
    waiting = [s for s in steps if s.get('status') in ('pending', 'active')]
    total = len(steps)
    if not blocked and not waiting and not unverified:
        head = f'**Plan finished: all {total} steps were checked and passed.**' if not skipped else f'**Plan finished: {passed} of {total} steps passed their checks; {skipped} skipped.**'
    elif not blocked and not waiting:
        head = f'**Plan finished, but not fully proven.** {passed} of {total} steps passed a check; {len(unverified)} were done without proof.'
    else:
        head = f'**Plan not finished.** {passed + len(unverified)} of {total} steps are done' + (f', {len(waiting)} not started' if waiting else '') + '.'
    lines = [head]
    for n, s in enumerate(steps, 1):
        if s.get('status') == 'blocked':
            lines.append(f'- Step {n}, **{s["title"]}**, stopped: {s.get("reason") or "it could not be completed."}')
    for s in unverified:
        lines.append(f'- Step {steps.index(s) + 1}, **{s["title"]}**, was done but not proven: {s.get("reason") or "no check."}')
    self_tested = [s for s in steps if s.get('verdict') == 'passed' and s.get('evidence') == 'self_written']
    if self_tested:
        lines.append(f'- {len(self_tested)} passed step{"s" if len(self_tested) != 1 else ""} were checked with tests written during this plan, which prove less than your own tests would.')
    if blocked or waiting: lines.append('Press **Continue plan** to pick up from the step that stopped, or tell me what to change.')
    return '\n'.join(lines)
