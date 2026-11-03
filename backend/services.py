"""Outside model services: anything with an OpenAI-compatible API.

OpenRouter, Groq, Gemini, OmniRoute, Ollama, LM Studio, or another PC running Luminaria with "Share my models" on.
Their models appear as ids like "svc:<service>/<model>" and can be used for chat or for any role (planning, coding, work).
A service that may not see files only ever receives the conversation text: no file contents, no tool results, no file tools.
"""
import re
import httpx
from .config import CONFIG, save_config
from .integrations import read_secrets, write_secrets, forget

PREFIX = 'svc:'
LLAMA_ONLY = ('dry_multiplier', 'dry_base', 'dry_allowed_length', 'repeat_penalty', 'chat_template_kwargs', 'cache_prompt')


def services():
    return [dict(s) for s in CONFIG.get('services') or []]


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:30] or 'service'


def _url(url):
    url = str(url or '').strip().rstrip('/')
    if not re.match(r'^https?://[^\s/]+', url): raise ValueError('Enter the service address, for example https://openrouter.ai/api/v1')
    return url.removesuffix('/chat/completions').removesuffix('/models')


async def list_models(url, key):
    headers = {'Authorization': 'Bearer ' + key} if key else {}
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        r = await client.get(url + '/models', headers=headers)
    if r.status_code in (401, 403): raise ValueError('The service refused the key. Check it and try again.')
    r.raise_for_status()
    data = r.json()
    rows = data.get('data', data.get('models', [])) if isinstance(data, dict) else data
    ids = [str(m.get('id') or m.get('name')) if isinstance(m, dict) else str(m) for m in rows or []]
    ids = sorted({i for i in ids if i and i != 'None'})
    if not ids: raise ValueError('The service answered but listed no models.')
    return ids[:300]


async def add(body):
    name = str(body.get('name') or '').strip()[:60]
    if not name: raise ValueError('Give the service a name')
    url, key = _url(body.get('url')), str(body.get('key') or '').strip()
    sid = _slug(name)
    current = services()
    if any(s['id'] == sid for s in current) and not body.get('replace'): raise ValueError('A service with that name already exists')
    try: models = await list_models(url, key)
    except httpx.HTTPError as error: raise ValueError(f'Could not reach {url}: {type(error).__name__}') from None
    entry = {'id': sid, 'name': name, 'url': url, 'files': bool(body.get('files')), 'models': models,
             'context': int(body.get('context') or 32768)}
    if key: write_secrets('service-' + sid, {'key': key})
    save_config({'services': [s for s in current if s['id'] != sid] + [entry]})
    return entry


def remove(sid):
    save_config({'services': [s for s in services() if s['id'] != sid]})
    forget('service-' + sid)
    if str(CONFIG.get('model', '')).startswith(f'{PREFIX}{sid}/'):
        from pathlib import Path
        from .models import registry
        local = next((m['id'] for m in registry() if Path(m.get('model_file', '')).is_file()), '')
        save_config({'model': local})  # back to an installed model


def set_files(sid, allowed):
    save_config({'services': [{**s, 'files': bool(allowed)} if s['id'] == sid else s for s in services()]})


def is_remote(model_id):
    return str(model_id or '').startswith(PREFIX)


def resolve(model_id):
    """(service, upstream model name) for an id like svc:<service>/<model>."""
    sid, _, model = str(model_id)[len(PREFIX):].partition('/')
    service = next((s for s in services() if s['id'] == sid), None)
    return (service, model) if service and model else (None, None)


def strengths(name):
    n = name.lower(); out = ['Writing', 'Tools']
    if re.search(r'cod(e|er)|devstral|starcoder|deepseek-v3|qwen.*coder', n): out.insert(0, 'Coding')
    if re.search(r'r1|reason|think|qwen3|gpt-oss|o[134]\b|o[134]-|gemini-2\.5|claude|kimi|glm', n): out.insert(0, 'Reasoning')
    return out


def remote_models():
    """Service models in the same shape as installed models, for roles, Auto and the model picker."""
    rows = []
    for s in services():
        for m in s.get('models', []):
            hit = re.search(r'(\d+(?:\.\d+)?)b\b', m.lower())
            rows.append({'id': f'{PREFIX}{s["id"]}/{m}', 'name': f'{m} · {s["name"]}', 'remote': True, 'service': s['id'],
                         'files': s.get('files', False), 'context': s.get('context', 32768), 'strengths': strengths(m),
                         'parameters': (hit.group(1) + 'B') if hit else '70B', 'variant': 'standard',
                         'description': f'Runs on {s["name"]}. ' + ('May see your files.' if s.get('files') else 'Sees only the conversation text, never your files.')})
    return rows


def request(model_id, body):
    """URL, headers and body for a chat request to a service. llama.cpp-only settings are removed."""
    service, model = resolve(model_id)
    if not service: raise ValueError('That model service was removed. Choose another model.')
    key = read_secrets('service-' + service['id']).get('key', '')
    clean = {k: v for k, v in body.items() if k not in LLAMA_ONLY}
    clean['model'] = model
    return service['url'] + '/chat/completions', ({'Authorization': 'Bearer ' + key} if key else {}), clean


def may_see_files(model_id):
    if not is_remote(model_id): return True
    service, _ = resolve(model_id)
    return bool(service and service.get('files'))
