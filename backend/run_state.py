"""Read-only lifecycle contract shared by the API and desktop renderer."""

MAX_CONTINUATIONS = 5
TERMINAL_PHASES = frozenset({'Complete', 'Stopped', 'Error', 'Denied', 'Checkpoint'})


def lifecycle(run):
    phase = run.get('phase')
    finished = bool(run.get('finished')) or phase in TERMINAL_PHASES
    actions = []
    if finished:
        state = {'Complete': 'completed', 'Denied': 'denied', 'Error': 'failed',
                 'Checkpoint': 'checkpoint', 'Stopped': 'stopped'}.get(phase, 'finished')
        if run.get('checkpoint') and run.get('continuations', 0) < MAX_CONTINUATIONS:
            actions.append('continue')
    elif phase == 'Waiting for approval':
        state, actions = 'awaiting_approval', ['decide', 'stop']
    elif run.get('resume_available'):
        state, actions = 'resumable', ['resume', 'stop']
    else:
        state, actions = ('queued' if phase == 'Queued' else 'running'), ['stop']
    return {'state': state, 'active': not finished, 'actions': actions}
