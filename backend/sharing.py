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

    @app.get('/v1/models')
    async def models(request: Request):
        if not allowed(request): return JSONResponse({'error': 'Wrong pairing key'}, 401)
        from .models import registry
        return {'object': 'list', 'data': [{'id': m['id'], 'object': 'model'} for m in registry() if Path(m.get('model_file', '')).is_file()]}

    @app.post('/v1/chat/completions')
    async def chat(request: Request):
        if not allowed(request): return JSONResponse({'error': 'Wrong pairing key'}, 401)
        body = await request.json()
        await ensure_manager()
        headers = {'Authorization': 'Bearer ' + CONFIG.get('model_api_key', '')}
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
    global _server, _task
    if _task and not _task.done(): return
    import uvicorn
    _server = uvicorn.Server(uvicorn.Config(share_app(), host='0.0.0.0', port=SHARE_PORT, log_level='warning', access_log=False, log_config=None))
    _server.install_signal_handlers = lambda: None
    _task = asyncio.create_task(_server.serve())


async def stop_share():
    global _server, _task
    if _server: _server.should_exit = True
    if _task:
        try: await asyncio.wait_for(_task, 5)
        except (asyncio.TimeoutError, Exception): _task.cancel()
    _server = _task = None


def rpc_executable():
    from .runtime import resolve_executable
    try: exe = Path(resolve_executable()).with_name('rpc-server.exe' if os.name == 'nt' else 'rpc-server')
    except ValueError: return None
    return exe if exe.is_file() else None


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


def rpc_peers():
    """Validated 'host:port' list for llama.cpp's --rpc option."""
    import re
    peers = []
    for item in str(CONFIG.get('rpc_peers') or '').replace(';', ',').split(','):
        item = item.strip()
        if not item: continue
        if ':' not in item: item += f':{RPC_PORT}'
        if not re.fullmatch(r'[A-Za-z0-9.\-]{1,253}:\d{2,5}', item): raise ValueError(f'"{item}" is not a PC address. Use something like 192.168.1.20 or 192.168.1.20:{RPC_PORT}.')
        peers.append(item)
    return peers[:8]


def status():
    return {'share': {'on': bool(CONFIG.get('share_models')), 'running': bool(_task and not _task.done()), 'port': SHARE_PORT,
                      'addresses': addresses(), 'key': share_key() if CONFIG.get('share_models') else None},
            'lend': {'on': bool(CONFIG.get('lend_gpu')), 'running': bool(_rpc and _rpc.poll() is None), 'port': RPC_PORT,
                     'available': rpc_executable() is not None, 'addresses': addresses()},
            'peers': CONFIG.get('rpc_peers') or ''}


async def apply(changes):
    """Turn sharing on or off. Used at start-up and when the user changes the settings."""
    if 'share_models' in changes:
        save_config({'share_models': bool(changes['share_models'])})
        await (start_share() if changes['share_models'] else stop_share())
    if 'lend_gpu' in changes:
        if changes['lend_gpu']: start_rpc()
        else: stop_rpc()
        save_config({'lend_gpu': bool(changes['lend_gpu'])})
    if 'rpc_peers' in changes:
        old = CONFIG.get('rpc_peers') or ''
        save_config({'rpc_peers': str(changes['rpc_peers'] or '')[:600]})
        try: rpc_peers()
        except ValueError: save_config({'rpc_peers': old}); raise
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
