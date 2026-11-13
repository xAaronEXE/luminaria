"""Run paired live benchmarks against an installed desktop in a disposable workspace."""
import argparse
import json
import subprocess
from pathlib import Path
import time
from urllib.request import Request, urlopen

CASES = {
    'chat': 'Reply with the single word READY.',
    'multi_file': (
        'Fix add.py so add(a, b) adds, and multiply.py so multiply(a, b) multiplies. '
        'Read both files first. Run python -m unittest test_math_ops and report the result.'
    ),
    'approval': 'Use write_file to create approval.txt containing exactly APPROVED.',
    'long_tool_run': (
        'Read part-01.txt through part-20.txt in numeric order. Read each with its own '
        'read_file call, one call per response. Return all 20 values in order.'
    ),
    'research': (
        'Use web tools to retrieve https://www.rfc-editor.org/rfc/rfc9110.html. '
        'What does a 404 mean? Include the source URL and cite section 15.5.5.'
    ),
    'interrupted': (
        'Use write_file to create resume.txt containing exactly RESUMED. '
        'Wait for approval before writing.'
    ),
    'context': 'What was the tracking code from the first message? Reply with the code.',
}


def request(base, route, token=None, body=None):
    headers = {'X-Studio-Token': token} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(base + '/api/' + route, data, headers), timeout=30) as response:
        return json.load(response)


def fixture(workspace):
    (workspace / 'add.py').write_text('def add(a, b): return a - b\n')
    (workspace / 'multiply.py').write_text('def multiply(a, b): return a + b\n')
    (workspace / 'test_math_ops.py').write_text(
        'import unittest\nfrom add import add\nfrom multiply import multiply\n'
        'class MathTests(unittest.TestCase):\n'
        ' def test_add(self): self.assertEqual(add(3, 4), 7)\n'
        ' def test_multiply(self): self.assertEqual(multiply(3, 4), 12)\n'
    )
    for name in ('approval.txt', 'resume.txt'):
        (workspace / name).unlink(missing_ok=True)
    for i in range(1, 21):
        (workspace / f'part-{i:02}.txt').write_text(f'VALUE-{100 + i}')


def verify(case, state, workspace, approvals, interrupted):
    text = '\n'.join(str(m.get('content') or '') for m in state['messages'] if m['role'] == 'assistant')
    actions = state['actions']
    done = [a for a in actions if a['status'] == 'done']
    if case == 'chat':
        return text.strip() == 'READY'
    if case == 'multi_file':
        import sys
        check = ('from add import add; from multiply import multiply; '
                 'assert add(3, 4) == 7 and add(-3, 4) == 1; '
                 'assert multiply(3, 4) == 12 and multiply(-3, 4) == -12')
        return subprocess.run([sys.executable, '-B', '-c', check], cwd=workspace,
                              capture_output=True, timeout=20).returncode == 0
    if case in ('approval', 'interrupted'):
        name, value = ('approval.txt', 'APPROVED') if case == 'approval' else ('resume.txt', 'RESUMED')
        output = workspace / name
        return (approvals == 1 and (case == 'approval' or interrupted)
                and output.exists() and output.read_text().strip() == value
                and sum(a['name'] == 'write_file' for a in done) == 1)
    if case == 'long_tool_run':
        paths = {a['args'].get('path') for a in done if a['name'] == 'read_file'}
        values = [text.find(f'VALUE-{100+i}') for i in range(1, 21)]
        return len(paths) >= 20 and values[0] >= 0 and values == sorted(set(values))
    if case == 'research':
        retrieved = any(a['name'] in ('web_fetch', 'research') for a in done)
        return retrieved and 'rfc9110.html' in text and '15.5.5' in text and 'not found' in text.lower()
    return 'AMBER-7214' in text and any(m['role'] == 'assistant' for m in state['messages'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--base', default='http://127.0.0.1:3210')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--modes', nargs='+', default=['legacy', 'agent', 'direct'])
    parser.add_argument('--model', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--desktop-pid', type=int, required=True)
    parser.add_argument('--desktop-exe', type=Path, required=True)
    args = parser.parse_args()
    boot = request(args.base, 'bootstrap')

    def api(route, body=None):
        return request(args.base, route, boot['token'], body)

    rows = []
    for case, prompt in CASES.items():
        for mode in args.modes:
            if mode == 'direct' and case not in ('chat', 'context'):
                continue
            fixture(args.workspace)
            chat = api('sessions', {})['id']
            started = time.monotonic()
            row = {'case': case, 'mode': mode, 'prompt': prompt, 'chat': chat}
            state = {}
            approvals = 0
            interrupted = False
            decisions = set()
            try:
                if case == 'context':
                    # Seed through the ordinary run endpoint to exercise conversation continuity.
                    prompts = ['Remember the tracking code AMBER-7214. Reply OK.']
                    prompts += [('Background filler ' * 4000) + '\nReply OK.' for _ in range(2)]
                else:
                    prompts = []
                for message in [*prompts, prompt]:
                    api(f'chats/{chat}/run', {'text': message, 'execution_mode': mode})
                    deadline = time.monotonic() + (270 if case == 'long_tool_run' else 145)
                    while time.monotonic() < deadline:
                        state = api(f'state?chat={chat}')
                        pending = [a for a in state['actions'] if a['status'] == 'pending']
                        for action in pending:
                            if action['id'] in decisions:
                                continue
                            decisions.add(action['id'])
                            expected = {'approval': 'approval.txt', 'interrupted': 'resume.txt'}.get(case)
                            path = action['args'].get('path')
                            allow = action['name'] == 'write_file' and expected is not None and path == expected
                            if case == 'multi_file':
                                allow = action['name'] in ('write_file', 'edit_file') and path in ('add.py', 'multiply.py')
                            if allow and case == 'interrupted' and not interrupted:
                                subprocess.run(['taskkill', '/PID', str(args.desktop_pid), '/T', '/F'],
                                               check=True, capture_output=True, timeout=20)
                                desktop = subprocess.Popen([str(args.desktop_exe), '--server'])
                                args.desktop_pid = desktop.pid
                                for _ in range(45):
                                    try:
                                        boot = request(args.base, 'bootstrap')
                                        restored = api(f'state?chat={chat}')
                                        if restored['run'] and restored['run']['phase'] == 'Waiting for approval':
                                            break
                                    except OSError:
                                        pass
                                    time.sleep(1)
                                else:
                                    raise RuntimeError('Desktop restart did not restore the pending approval')
                                if (args.workspace / 'resume.txt').exists():
                                    raise RuntimeError('Interrupted write executed without approval')
                                interrupted = True
                            approvals += int(allow)
                            api(f'approvals/{action["id"]}', {'approved': allow})
                        else:
                            if state['run'] and state['run'].get('finished'):
                                break
                            time.sleep(0.8)
                            continue
                        continue
                    else:
                        api(f'chats/{chat}/stop', {})
                        raise TimeoutError('No terminal state before benchmark deadline')
                row['verdict'] = 'PASS' if verify(case, state, args.workspace, approvals, interrupted) else 'FAIL'
            except Exception as error:
                row.update(verdict='UNVERIFIED', error=str(error))
            run = state.get('run') or {}
            row.update(seconds=round(time.monotonic()-started, 2), approvals=approvals,
                       interrupted=interrupted, phase=run.get('phase'), provider_error=run.get('error'),
                       checkpoint=run.get('checkpoint'), context=run.get('context'),
                       tool_outcomes=[(a['name'], a['status']) for a in state.get('actions', [])])
            rows.append(row)
            report = dict(version=boot['version'], revision=args.revision, installer_sha256=args.sha256,
                          model=args.model, app_endpoint=args.base, inference_endpoint='http://127.0.0.1:8098/v1',
                          permission_mode='review', results=rows)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(case, mode, row['verdict'], row['seconds'], flush=True)


if __name__ == '__main__':
    main()
