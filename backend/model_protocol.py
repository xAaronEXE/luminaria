"""Provider-specific wire behavior for the shared execution loop."""
import json
from hashlib import sha256
from urllib.parse import urlsplit


def deepseek_wire(url):
    return urlsplit(url).hostname == 'api.deepseek.com'


def continuation_scope(model, endpoint, run_id):
    return sha256(f'{model}\n{endpoint}\n{run_id}'.encode()).hexdigest()


def prepare_messages(messages, scope):
    result = type(messages)()
    for message in messages:
        clean = {k: v for k, v in message.items() if k not in ('reasoning', 'continuation_scope')}
        if scope and message.get('continuation_scope') == scope and message.get('tool_calls'):
            clean['reasoning_content'] = message.get('reasoning', '')
            clean['content'] = clean.get('content') or ''
        result.append(clean)
    return result


def complete_tool_batch(calls):
    calls = list(calls)
    if not calls:
        return False
    ids = set()
    for call in calls:
        function = call['function']
        if not function['name'] or (call['id'] and call['id'] in ids):
            return False
        ids.add(call['id'])
        try:
            if not isinstance(json.loads(function['arguments']), dict):
                return False
        except (TypeError, ValueError):
            return False
    return True
