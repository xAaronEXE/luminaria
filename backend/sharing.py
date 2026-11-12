"""Several PCs working together.

Share my models: other PCs running Luminaria can use this PC's installed models, as a model service
(http://<this PC>:8099/v1 plus a pairing key). Only chat requests are accepted; nothing else on this PC is reachable.

Lend my graphics card: runs llama.cpp's rpc-server so another PC can split one large model across both GPUs.
Use other PCs' graphics cards: adds those PCs to the model manager with llama.cpp's --rpc option.
llama.cpp's RPC has no password, so it is meant for a trusted home or office network only.
"""
import asyncio, os, secrets, socket, subprocess
from pathlib import Path
import httpx
from .config import CONFIG, save_config
from .integrations import read_secrets, write_secrets

SHARE_PORT = 8099
RPC_PORT = 50052
DISCOVERY_PORT = 8100
HELLO = b'LUMINARIA_DISCOVER_1'
_pairing = {'code': None, 'expires': 0, 'failures': 0}
_discovery = None
_server = None
_task = None
_rpc = None


def addresses():
    """This PC's addresses on the local network."""
    found = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET): found.add(info[4][0])
    except OSError: pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1)); found.add(s.getsockname()[0])  # no packet is sent
    except OSError: pass
    return sorted(a for a in found if not a.startswith('127.'))


def share_key():
    key = read_secrets('share').get('key')
    if not key:
        key = secrets.token_urlsafe(24); write_secrets('share', {'key': key})
    return key


def share_app():
    """The only thing other PCs can reach: list models and chat, with the pairing key."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    local = 'http://127.0.0.1:8098/v1'

    def allowed(request):
        return secrets.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + share_key())

    async def ensure_manager():
        from . import runtime
        if not runtime.listening(8098):
            await asyncio.to_thread(runtime.start_swap)
            for _ in range(40):
                if runtime.listening(8098): break
                await asyncio.sleep(.25)

    @app.get('/luminaria/hello')
    async def hello():
        return {'name': socket.gethostname(), 'version': CONFIG.get('version'), 'pairing': pairing_open()}

    @app.post('/luminaria/pair')
    async def pair(request: Request):
        body = await request.json()
        if not pairing_open(): return JSONResponse({'error': 'Pairing is not open on this PC. Turn on "Let other PCs pair" there first.'}, 403)
        if _pairing['failures'] >= 5: return JSONResponse({'error': 'Too many wrong codes. Turn pairing off and on again on that PC.'}, 429)
        if not secrets.compare_digest(str(body.get('code', '')).strip(), _pairing['code']):
            _pairing['failures'] += 1
            return JSONResponse({'error': 'That code is not right. Check the code shown on the other PC.'}, 401)
        _pairing['code'] = None   # one pairing per code
        return {'key': share_key(), 'name': socket.gethostname(), 'port': SHARE_PORT}

    @app.get('/v1/models')
    async def models(request: Request):
        if not allowed(request): return JSONResponse({'error': 'Wrong pairing key'}, 401)
        from .models import registry
        rows = [m for m in registry() if Path(m.get('model_file', '')).is_file()]
        # Extra details let the other PC's Auto mode and roles judge these models like its own.
        return {'object': 'list', 'data': [{'id': m['id'], 'object': 'model', 'luminaria': {k: m.get(k) for k in ('name', 'parameters', 'strengths', 'context', 'variant')}} for m in rows]}

    @app.post('/luminaria/lend')
    async def lend(request: Request):
        if not allowed(request): return JSONResponse({'error': 'Wrong pairing key'}, 401)
        on = bool((await request.json()).get('on'))
        try: start_rpc() if on else stop_rpc()
        except ValueError as error: return JSONResponse({'error': str(error)}, 409)
        save_config({'lend_gpu': on})
        return {'on': on, 'port': RPC_PORT}

    @app.post('/v1/chat/completions')
    async def chat(request: Request):
        if not allowed(request): return JSONResponse({'error': 'Wrong pairing key'}, 401)
        body = await request.json()
        await ensure_manager()
        key = CONFIG.get('model_api_key')
        headers = {'Authorization': 'Bearer ' + key} if key else {}
        client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10), trust_env=False)
        upstream = await client.send(client.build_request('POST', local + '/chat/completions', json=body, headers=headers), stream=True)

        async def relay():
            try:
                async for chunk in upstream.aiter_raw(): yield chunk
            finally:
                await upstream.aclose(); await client.aclose()
        return StreamingResponse(relay(), status_code=upstream.status_code, media_type=upstream.headers.get('content-type', 'application/json'))
    return app


async def start_share():
    global _server, _task, _discovery
    if _task and not _task.done(): return
    try:
        _discovery, _ = await asyncio.get_running_loop().create_datagram_endpoint(_Discovery, local_addr=('0.0.0.0', DISCOVERY_PORT), allow_broadcast=True)
    except OSError: _discovery = None   # discovery is a convenience; pairing by address still works
    import uvicorn
    _server = uvicorn.Server(uvicorn.Config(share_app(), host='0.0.0.0', port=SHARE_PORT, log_level='warning', access_log=False, log_config=None))
    _server.install_signal_handlers = lambda: None
    _task = asyncio.create_task(_server.serve())


async def stop_share():
    global _server, _task, _discovery
    if _discovery: _discovery.close(); _discovery = None
    _pairing['code'] = None
    if _server: _server.should_exit = True
    if _task:
        try: await asyncio.wait_for(_task, 5)
        except (asyncio.TimeoutError, Exception): _task.cancel()
    _server = _task = None


def pairing_open():
    import time
    return bool(_pairing['code'] and time.time() < _pairing['expires'])


def open_pairing():
    """A fresh 6-digit code, valid for 10 minutes and for one pairing."""
    import time
    _pairing.update(code=f'{secrets.randbelow(10**6):06d}', expires=time.time() + 600, failures=0)
    return _pairing['code']


class _Discovery(asyncio.DatagramProtocol):
    """Answers "is Luminaria here?" broadcasts from other PCs on the local network."""
    def connection_made(self, transport): self.transport = transport
    def datagram_received(self, data, addr):
        if data == HELLO:
            import json
            self.transport.sendto(json.dumps({'name': socket.gethostname(), 'port': SHARE_PORT, 'pairing': pairing_open()}).encode(), addr)


async def find_pcs(wait=1.5):
    """PCs on the local network that are sharing with Luminaria."""
    import json
    found = {}
    loop = asyncio.get_running_loop()

    class Listen(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            try: info = json.loads(data.decode())
            except ValueError: return
            if addr[0] not in addresses(): found[addr[0]] = {'address': addr[0], 'name': str(info.get('name', addr[0]))[:60], 'port': int(info.get('port', SHARE_PORT)), 'pairing': bool(info.get('pairing'))}

    transport, _ = await loop.create_datagram_endpoint(Listen, local_addr=('0.0.0.0', 0), allow_broadcast=True)
    try:
        for _ in range(2):
            transport.sendto(HELLO, ('255.255.255.255', DISCOVERY_PORT)); await asyncio.sleep(wait / 2)
    finally: transport.close()
    return sorted(found.values(), key=lambda p: p['name'])


async def pair(address, code, port=SHARE_PORT):
    """Pair with another PC using the code it shows. It becomes a model service whose models join Auto and the roles."""
    import re
    from . import services
    address = str(address or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9.\-]{1,253}', address): raise ValueError('Enter the other PC\'s address, for example 192.168.1.20')
    base = f'http://{address}:{int(port)}'
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            r = await client.post(base + '/luminaria/pair', json={'code': str(code or '').strip(), 'name': socket.gethostname()})
    except httpx.HTTPError: raise ValueError(f"Couldn't reach {address}. Make sure Luminaria is open there with \"Let other PCs pair\" on, and that Windows allowed it on private networks.") from None
    if r.status_code >= 400:
        try: message = r.json().get('error')
        except ValueError: message = None
        raise ValueError(message or f'Pairing failed ({r.status_code}).')
    info = r.json()
    entry = await services.add({'name': info.get('name') or address, 'url': base + '/v1', 'key': info['key'], 'files': True, 'kind': 'pc', 'replace': True})
    return entry


async def set_split(on):
    """Split big models across this PC and every paired PC that can lend its graphics card."""
    from . import services
    peers, problems = [], []
    if not on:
        await apply({'rpc_peers': '', 'split_models': False})
    for pc in [s for s in services.services() if s.get('kind') == 'pc']:
        base = pc['url'].removesuffix('/v1')
        key = services.read_secrets(services._secret(pc['id'])).get('key', '')
        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                r = await client.post(base + '/luminaria/lend', json={'on': on}, headers={'Authorization': 'Bearer ' + key})
            if r.status_code >= 400: problems.append(f"{pc['name']}: {r.json().get('error', r.status_code)}")
            elif on: peers.append(f"{base.split('//')[1].rsplit(':', 1)[0]}:{r.json().get('port', RPC_PORT)}")
        except (httpx.HTTPError, ValueError): problems.append(f"{pc['name']}: not reachable")
    if on:
        await apply({'rpc_peers': ','.join(peers), 'split_models': bool(peers)})
    return {'peers': peers, 'problems': problems}


def rpc_executable():
    from .runtime import resolve_executable
    try: folder = Path(resolve_executable()).parent
    except ValueError: return None
    names = ('ggml-rpc-server', 'rpc-server')   # newer llama.cpp builds renamed rpc-server
    return next((folder / (n + ('.exe' if os.name == 'nt' else '')) for n in names if (folder / (n + ('.exe' if os.name == 'nt' else ''))).is_file()), None)


def start_rpc():
    global _rpc
    if _rpc and _rpc.poll() is None: return
    exe = rpc_executable()
    if not exe: raise ValueError("This copy of the model runtime has no rpc-server, so this PC can't lend its graphics card. Reinstall Luminaria to restore it.")
    _rpc = subprocess.Popen([str(exe), '-H', '0.0.0.0', '-p', str(RPC_PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def stop_rpc():
    global _rpc
    if _rpc and _rpc.poll() is None:
        _rpc.terminate()
        try: _rpc.wait(5)
        except subprocess.TimeoutExpired: _rpc.kill()
    _rpc = None


def rpc_peers(value=None):
    """Validated 'host:port' list for llama.cpp's --rpc option."""
    import re
    peers = []
    for item in str((CONFIG.get('rpc_peers') if value is None else value) or '').replace(';', ',').split(','):
        item = item.strip()
        if not item: continue
        if ':' not in item: item += f':{RPC_PORT}'
        if not re.fullmatch(r'[A-Za-z0-9.\-]{1,253}:\d{2,5}', item): raise ValueError(f'"{item}" is not a PC address. Use something like 192.168.1.20 or 192.168.1.20:{RPC_PORT}.')
        peers.append(item)
    return peers[:8]


def status():
    from . import services
    return {'name': socket.gethostname(),
            'share': {'on': bool(CONFIG.get('share_models')), 'running': bool(_task and not _task.done()), 'port': SHARE_PORT,
                      'addresses': addresses(), 'code': _pairing['code'] if pairing_open() else None},
            'paired': [{'id': s['id'], 'name': s['name'], 'url': s['url'], 'models': len(s.get('models', []))} for s in services.services() if s.get('kind') == 'pc'],
            'split': bool(CONFIG.get('split_models')),
            'lend': {'on': bool(CONFIG.get('lend_gpu')), 'running': bool(_rpc and _rpc.poll() is None), 'port': RPC_PORT,
                     'available': rpc_executable() is not None, 'addresses': addresses()},
            'peers': CONFIG.get('rpc_peers') or ''}


async def apply(changes):
    """Turn sharing on or off. Used at start-up and when the user changes the settings."""
    if 'share_models' in changes:
        save_config({'share_models': bool(changes['share_models'])})
        await (start_share() if changes['share_models'] else stop_share())
        if changes['share_models']: open_pairing()
    if 'lend_gpu' in changes:
        if changes['lend_gpu']: start_rpc()
        else: stop_rpc()
        save_config({'lend_gpu': bool(changes['lend_gpu'])})
    if 'rpc_peers' in changes:
        value = str(changes['rpc_peers'] or '')[:600]
        rpc_peers(value)
        save_config({'rpc_peers': value, 'split_models': bool(changes.get('split_models', value))})
        from . import runtime
        if runtime.manager_state().get('owned'):  # the model manager reads --rpc when it starts
            await asyncio.to_thread(runtime.stop_owned); await asyncio.to_thread(runtime.start_swap)
    return status()


async def resume():
    if CONFIG.get('share_models'):
        try: await start_share()
        except Exception: pass
    if CONFIG.get('lend_gpu'):
        try: start_rpc()
        except Exception: pass


async def shutdown():
    await stop_share(); stop_rpc()
