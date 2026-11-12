"""Own only our llama-swap process. Existing unrelated model servers are not killed."""
import json, os, subprocess, socket
from .config import CONFIG,DATA,ROOT

def resolve_executable():
    """Use a valid explicit runtime, otherwise the runtime shipped with the app."""
    from pathlib import Path
    explicit=CONFIG.get('llama_executable')
    if explicit and Path(explicit).is_file():return str(Path(explicit))
    bundled=ROOT/'runtime'/'local-ai'/'runtime-vulkan'/'llama-server.exe'
    if not bundled.is_file():raise ValueError('The bundled model runtime is missing. Repair or reinstall Luminaria; your downloaded models will be kept.')
    from .config import save_config
    save_config({'llama_executable':str(bundled)})
    return str(bundled)

swap_process=None
START_MARKER='=== Luminaria started the model manager ==='
PROBLEMS=[
 (r'out of memory|cudaMalloc failed|failed to allocate|unable to allocate|ErrorOutOfDeviceMemory|not enough memory',
  'Not enough GPU memory to load this model. Choose a smaller quantization, lower the context size, or close other GPU apps.'),
 (r'invalid magic|failed to read magic|unknown model architecture|error loading model|failed to load model|gguf_init_from_file',
  'The model file could not be loaded. It may be incomplete, damaged or unsupported. Check it in the Model library, or download it again.'),
 (r'mmproj|clip_model_load|failed to load (vision|projector)',
  'The vision projector could not be loaded. Check that it matches this model.'),
 (r'address already in use|bind.*failed|only one usage of each socket',
  'A model port is already in use by another program. Close the other model server, then restart the model manager.'),
 (r'health check timed out|timed out waiting|did not become healthy',
  'The model took too long to load. Try again, or choose a smaller model.'),
]

def log_tail(limit=65536):
    path=DATA/'llama-swap.log'
    if not path.is_file(): return ''
    with open(path,'rb') as f:
        f.seek(max(0,path.stat().st_size-limit)); text=f.read().decode('utf-8','replace')
    return text.rsplit(START_MARKER,1)[-1]

def diagnose(text=None):
    """Plain explanation of the most recent model-manager failure, or None."""
    import re
    text=log_tail() if text is None else text
    lines=text.splitlines()[-300:]
    for line in reversed(lines):
        for pattern,message in PROBLEMS:
            if re.search(pattern,line,re.I): return message
    return None

def manager_state():
    if swap_process is None: return {'owned':False,'running':listening(8098)}
    code=swap_process.poll()
    return {'owned':True,'running':code is None,'exit_code':code}

def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1): return True
    except OSError: return False


def reachable_rpc_peers(peers):
    """Check the configured lenders once before building model commands."""
    available, unavailable = [], []
    for peer in peers:
        host, port = peer.rsplit(':', 1)
        try:
            with socket.create_connection((host, int(port)), timeout=0.5):
                available.append(peer)
        except (OSError, OverflowError):
            unavailable.append(peer)
    return available, unavailable

def host_settings():
    """Generation threads and the system-memory prompt cache size for this PC (not the build PC)."""
    try:
        import psutil
        threads=psutil.cpu_count(logical=False) or 8
        ram_mib=psutil.virtual_memory().total//2**20
    except Exception: threads,ram_mib=8,16384
    return max(2,min(threads,32)),int(max(1024,min(16384,ram_mib//4)))

def ensure_model_file():
    """Keep the selected model pointing at a file that exists. After models are removed and downloaded again,
    the saved file can be gone while the same or other models are installed."""
    from pathlib import Path
    from .models import registry
    current=CONFIG.get('model_file')
    if current and Path(current).is_file(): return current
    installed=[m for m in registry() if Path(m['model_file']).is_file()]
    if not installed: return None
    chosen=next((m for m in installed if m['id']==CONFIG.get('model')),installed[0])
    from .config import save_config
    save_config({'model':chosen['id'],'model_file':chosen['model_file'],'projector_file':chosen.get('projector_file') or '','context':chosen.get('context') or CONFIG.get('context')})
    return chosen['model_file']

def swap_model_ids():
    """Models the running model manager was started with."""
    try: return set(json.loads((DATA/'llama-swap.yaml').read_text('utf-8')).get('models',{}))
    except (OSError,ValueError): return set()

def start_swap():
    global swap_process
    if listening(8098): return {'started':False,'message':'Model manager is already listening on 8098'}
    exe=resolve_executable(); model=ensure_model_file()
    from pathlib import Path
    if not model or not Path(model).is_file(): raise ValueError('Choose an installed model using Use this model in the Model library.')
    if listening(8097): raise ValueError('Port 8097 is already occupied. Stop the old standalone model server before starting the model manager. No process was stopped.')
    from .models import registry
    import secrets
    from .config import save_config
    if not CONFIG.get('model_api_key'): save_config({'model_api_key':secrets.token_urlsafe(32)})
    entries=registry() or [{'id':CONFIG['model'],'name':CONFIG['model'],'model_file':model,'context':CONFIG['context'],'projector_file':CONFIG.get('projector_file')}]
    configs={}
    from .sharing import rpc_peers
    try: peers, unavailable_peers = reachable_rpc_peers(rpc_peers() if CONFIG.get('split_models') is not False else [])
    except ValueError: peers, unavailable_peers = [], []
    tuning_hardware=None
    if any(entry.get('tuning') for entry in entries):
        from .hardware import information
        tuning_hardware=information()
    for entry in entries:
        if not Path(entry['model_file']).is_file(): continue
        threads,cache_ram=host_settings()
        # Batch sizes are llama.cpp's defaults (fast prompt reading); -fit sizes GPU layers around them.
        # --cache-ram keeps recent prompts' KV cache in system memory, so returning to a chat does not re-read it.
        args=[exe,'-m',entry['model_file'],'--host','127.0.0.1','--port','8097','-c',str(entry['context']),'-np','1','-fa','on','-ctk','q8_0','-ctv','q8_0','-fit','on','-fitt','512','-b','2048','-ub','512','-t',str(threads),'--cache-ram',str(cache_ram),'--cache-reuse','256','--jinja','--agent','--api-key',CONFIG['model_api_key'],'--reasoning-format','deepseek','--reasoning-budget','4096','--metrics','--alias',entry['id']]
        launch=entry.get('launch') or {}
        if launch.get('ubatch'):
            args[args.index('-ub')+1]=str(launch['ubatch']);args[args.index('-b')+1]=str(max(2048,launch['ubatch']))
        if launch.get('gpu_layers') is not None or launch.get('cpu_moe'):
            # Custom placement chosen in the library: llama.cpp's own fitting would override it.
            args[args.index('-fit')+1]='off'
            layers=launch.get('gpu_layers');layers=999 if layers in (None,-1) else layers
            args+=['-ngl',str(layers)]
            if launch.get('cpu_moe'):args+=['--n-cpu-moe',str(launch['cpu_moe'])]
            if layers==0:args+=['--no-kv-offload']
        tuning=entry.get('tuning')
        if tuning and tuning_hardware and not launch:
            from .hardware import provenance
            if tuning.get('provenance',{}).get('key')==provenance(entry,tuning_hardware)['key']:
                args[args.index('-t')+1]=str(tuning['threads'])
                args[args.index('-fit')+1]='off'
                args+=['-ngl',str(tuning['gpu_layers'])]
                if tuning.get('cpu_moe'):args+=['--n-cpu-moe',str(tuning['cpu_moe'])]
                if tuning.get('ubatch'):args[args.index('-ub')+1]=str(tuning['ubatch']);args[args.index('-b')+1]=str(max(2048,tuning['ubatch']))
                if tuning['gpu_layers']==0:args+=['--no-kv-offload']
        if peers: args+=['--rpc',','.join(peers)]   # split the model across these PCs' graphics cards
        if entry.get('projector_file') and Path(entry['projector_file']).is_file(): args+=['--mmproj',entry['projector_file'],'--no-mmproj-offload','--image-max-tokens','1024']
        command=' '.join('"'+str(a).replace('\\','/').replace('"','\\"')+'"' for a in args)
        configs[entry['id']]={'name':entry['name'],'cmd':command,'proxy':'http://127.0.0.1:8097','checkEndpoint':'/health'}
    keep=int(CONFIG.get('keep_model_loaded',0) or 0)
    # Luminaria unloads the model itself once work is done; this is only a backstop if the app closes unexpectedly.
    config={'healthCheckTimeout':180,'logLevel':'info','globalTTL':max(300,keep),'globalConcurrencyLimit':1,'captureBuffer':0,'apiKeys':[CONFIG['model_api_key']],'security':{'cors':{'allowedOrigins':['http://127.0.0.1:3210']}},'models':configs}
    # JSON is a subset of YAML; use a generated file and no hand-escaped paths.
    path=DATA/'llama-swap.yaml'; path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    runtime=ROOT/'runtime'/'llama-swap.exe'
    with open(DATA/'llama-swap.log','ab') as log:
        log.write(START_MARKER.encode()+b'\n');log.flush()
        if unavailable_peers:
            log.write(('Paired GPU endpoints unreachable and omitted: '+', '.join(unavailable_peers)+'\n').encode('utf-8'))
            log.flush()
        swap_process=subprocess.Popen([str(runtime),'-config',str(path),'-listen','127.0.0.1:8098'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (DATA/'llama-swap.pid').write_text(str(swap_process.pid))
    return {'started':True,'pid':swap_process.pid,'message':'Model loads on first request; unloads after 30 idle minutes'}

def stop_owned():
    global swap_process
    owned=swap_process is not None
    if swap_process and swap_process.poll() is None:
        if os.name=='nt': subprocess.run(['taskkill','/PID',str(swap_process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else: swap_process.terminate()
        try: swap_process.wait(timeout=10)
        except subprocess.TimeoutExpired: pass
    swap_process=None
    import time
    for _ in range(20 if owned else 0):
        if not listening(8098) and not listening(8097): break
        time.sleep(.25)
