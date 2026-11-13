"""Outside model services: anything with an OpenAI-compatible API.

OpenRouter, Groq, Gemini, OmniRoute, Ollama, LM Studio, or another PC running Luminaria with "Share my models" on.
Their models appear as ids like "svc:<service>/<model>" and can be used for chat or for any role (planning, coding, work).
Services without file access receive typed chat and public web research context only.
"""
import re
import httpx
from .config import CONFIG, save_config
from .integrations import read_secrets, write_secrets, forget

PREFIX = 'svc:'
LLAMA_ONLY = ('dry_multiplier', 'dry_base', 'dry_allowed_length', 'repeat_penalty', 'chat_template_kwargs', 'cache_prompt')
PRIVATE_TOOLS = frozenset({'research', 'web_search', 'web_fetch', 'update_plan'})


class IntegrationMessages(list):
    """Context that includes connected-account or signed-in browser data."""


class PrivateMessages(list):
    """A request assembled without local file, workspace, or unrestricted tool context."""


def private_chat(history, model_id, system):
    """Build a separate conversation from source messages before workspace context is added."""
    messages = PrivateMessages([{'role': 'system', 'content': system}])
    results = {m.get('tool_call_id'): m for m in history
               if m['role'] == 'tool' and m.get('private_model') == model_id}
    for message in history:
        role, content = message['role'], message.get('content')
        if role == 'user' and not (message.get('plan_step') or message.get('screenshot') or message.get('scheduled')):
            if isinstance(content, list):
                # The first item is the composer text. All subsequent items are attachment material.
                if not message.get('attachments'):
                    continue
                typed = content[0].get('text', '') if content else ''
                content = typed + '\n[Local attachments are unavailable to this model.]'
            if content:
                messages.append({'role': role, 'content': content})
        elif role == 'assistant' and message.get('private_model') == model_id:
            calls = [call for call in message.get('tool_calls', [])
                     if call['id'] in results and call['function']['name'] in PRIVATE_TOOLS]
            if content or calls:
                reply = {'role': role, 'content': content}
                if calls:
                    reply['tool_calls'] = calls
                    if message.get('continuation_scope'):
                        reply.update(reasoning=message.get('reasoning',''),continuation_scope=message['continuation_scope'])
                messages.append(reply)
                messages.extend({'role': 'tool', 'tool_call_id': call['id'],
                                 'content': results[call['id']]['content']} for call in calls)
    return messages


def _secret(sid):
    return 'svc_' + sid.replace('-', '_')[:26]   # the secret store accepts letters, digits and underscores


def services():
    return [dict(s) for s in CONFIG.get('services') or []]


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:30] or 'service'


def _url(url):
    url = str(url or '').strip().rstrip('/')
    if not re.match(r'^https?://[^\s/]+', url): raise ValueError('Enter the service address, for example https://openrouter.ai/api/v1')
    return url.removesuffix('/chat/completions').removesuffix('/models')


def tls_context(service):
    if service.get('kind') != 'pc':
        return True
    certificate = service.get('peer_certificate')
    if not certificate or not service['url'].startswith('https://'):
        raise ValueError('Re-pair this PC to use its verified HTTPS connection.')
    from .peer_tls import client_context
    return client_context(certificate)


def may_see_integrations(model_id):
    if not is_remote(model_id):
        return True
    service, _ = resolve(model_id)
    return bool(service and service.get('files') and service.get('integration_data'))


async def list_models(url, key, verify=True):
    headers = {'Authorization': 'Bearer ' + key} if key else {}
    async with httpx.AsyncClient(timeout=15, trust_env=False, verify=verify) as client:
        r = await client.get(url + '/models', headers=headers)
    if r.status_code in (401, 403): raise ValueError('The service refused the key. Check it and try again.')
    r.raise_for_status()
    data = r.json()
    rows = data.get('data', data.get('models', [])) if isinstance(data, dict) else data
    meta = {}
    for m in rows or []:
        if isinstance(m, dict) and isinstance(m.get('luminaria'), dict): meta[str(m.get('id'))] = m['luminaria']   # details from a paired PC
    ids = [str(m.get('id') or m.get('name')) if isinstance(m, dict) else str(m) for m in rows or []]
    ids = sorted({i for i in ids if i and i != 'None'})
    if not ids: raise ValueError('The service answered but listed no models.')
    list_models.meta = meta
    return ids[:300]


async def add(body, *, peer_certificate=None):
    name = str(body.get('name') or '').strip()[:60]
    if not name: raise ValueError('Give the service a name')
    url, key = _url(body.get('url')), str(body.get('key') or '').strip()
    if peer_certificate:
        from .peer_tls import fingerprint
        sid = 'pc-' + fingerprint(peer_certificate)[:20]
    else:
        sid = _slug(name)
    current = services()
    if any(s['id'] == sid for s in current) and not body.get('replace'): raise ValueError('A service with that name already exists')
    kind = 'pc' if peer_certificate else 'cloud'
    if body.get('kind') == 'pc' and not peer_certificate:
        raise ValueError('Use Pair with another PC to verify its certificate.')
    verify = tls_context({'url':url,'kind':kind,'peer_certificate':peer_certificate})
    try: models = await list_models(url, key, verify)
    except httpx.HTTPError as error: raise ValueError(f'Could not reach {url}: {type(error).__name__}') from None
    # Small catalogs are used as they are; for big ones (OpenRouter lists hundreds) the user picks the models to use.
    entry = {'id': sid, 'name': name, 'url': url, 'kind': kind, 'meta': getattr(list_models, 'meta', {}) if kind == 'pc' else {},
             'files': bool(body.get('files')), 'models': models, 'enabled': models if kind == 'pc' or len(models) <= 12 else [],
             'context': int(body.get('context') or 32768)}
    if peer_certificate: entry['peer_certificate'] = peer_certificate
    if key: write_secrets(_secret(sid), {'key': key})
    else: forget(_secret(sid))
    save_config({'services': [s for s in current if s['id'] != sid] + [entry]})
    return entry


def remove(sid):
    save_config({'services': [s for s in services() if s['id'] != sid]})
    forget(_secret(sid))
    if str(CONFIG.get('model', '')).startswith(f'{PREFIX}{sid}/'):
        from pathlib import Path
        from .models import registry
        local = next((m['id'] for m in registry() if Path(m.get('model_file', '')).is_file()), '')
        save_config({'model': local})  # back to an installed model


def set_enabled(sid, ids):
    service = next((s for s in services() if s['id'] == sid), None)
    if not service: raise ValueError('That model service is not set up')
    chosen = [m for m in service['models'] if m in set(ids or [])]
    save_config({'services': [{**s, 'enabled': chosen} if s['id'] == sid else s for s in services()]})
    return chosen


async def refresh(sid):
    service = next((s for s in services() if s['id'] == sid), None)
    if not service: raise ValueError('That model service is not set up')
    try: models = await list_models(service['url'], read_secrets(_secret(sid)).get('key', ''), tls_context(service))
    except httpx.HTTPError as error: raise ValueError(f'Could not reach {service["url"]}: {type(error).__name__}') from None
    enabled = [m for m in service.get('enabled', models) if m in models]
    meta = getattr(list_models, 'meta', {}) if service.get('kind') == 'pc' else {}
    if service.get('kind') == 'pc': enabled = models   # a paired PC's models are all yours
    save_config({'services': [{**s, 'models': models, 'enabled': enabled, 'meta': meta} if s['id'] == sid else s for s in services()]})
    return {'models': models, 'enabled': enabled}


def set_files(sid, allowed):
    save_config({'services': [{**s, 'files': bool(allowed), 'integration_data': bool(allowed and s.get('integration_data'))} if s['id'] == sid else s for s in services()]})


def set_integration_data(sid, allowed):
    service = next((s for s in services() if s['id'] == sid), None)
    if not service or (allowed and not service.get('files')):
        raise ValueError('Enable file access for this model service first.')
    save_config({'services': [{**s, 'integration_data': bool(allowed)} if s['id'] == sid else s for s in services()]})


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
        pc = s.get('kind') == 'pc'
        if pc and not s.get('peer_certificate'):
            continue
        for m in s.get('enabled', s.get('models', [])):
            info = (s.get('meta') or {}).get(m) or {}
            hit = re.search(r'(\d+(?:\.\d+)?)b\b', m.lower())
            rows.append({'id': f'{PREFIX}{s["id"]}/{m}', 'name': f'{info.get("name") or m} · {s["name"]}', 'remote': True, 'kind': 'pc' if pc else 'cloud',
                         'service': s['id'], 'files': s.get('files', False), 'context': info.get('context') or s.get('context', 32768),
                         'strengths': info.get('strengths') or strengths(m), 'parameters': info.get('parameters') or ((hit.group(1) + 'B') if hit else '70B'),
                         'variant': info.get('variant') or 'standard',
                         'description': (f'Runs on your paired PC {s["name"]}.' if pc else f'Runs on {s["name"]}. ' + ('May see your files.' if s.get('files') else 'Sees only the conversation text, never your files.'))})
    return rows


def request(model_id, body):
    """URL, headers and body for a chat request to a service. llama.cpp-only settings are removed."""
    service, model = resolve(model_id)
    if not service: raise ValueError('That model service was removed. Choose another model.')
    key = read_secrets(_secret(service['id'])).get('key', '')
    if isinstance(body.get('messages'), IntegrationMessages) and not may_see_integrations(model_id):
        raise ValueError('Connected-account data is disabled for this model service.')
    if not service.get('files'):
        if not isinstance(body.get('messages'), PrivateMessages):
            raise ValueError('This model service requires a file-free request.')
        if any(t['function']['name'] not in PRIVATE_TOOLS for t in body.get('tools', [])):
            raise ValueError('This model service cannot use local tools.')
    clean = {k: v for k, v in body.items() if k not in LLAMA_ONLY}
    clean['model'] = model
    return service['url'] + '/chat/completions', ({'Authorization': 'Bearer ' + key} if key else {}), clean


def may_see_files(model_id):
    if not is_remote(model_id): return True
    service, _ = resolve(model_id)
    return bool(service and service.get('files'))
