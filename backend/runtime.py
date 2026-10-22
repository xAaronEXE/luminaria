"""Own only our llama-swap process. Existing unrelated model servers are not killed."""
import json, os, subprocess, socket
from .config import CONFIG,DATA,ROOT

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

def start_swap():
    global swap_process
    if listening(8098): return {'started':False,'message':'Model manager is already listening on 8098'}
    exe=CONFIG.get('llama_executable'); model=CONFIG.get('model_file')
    from pathlib import Path
    if not exe or not model or not Path(exe).is_file() or not Path(model).is_file(): raise ValueError('Set llama-server executable and GGUF model paths in Settings, or configure an existing endpoint')
    if listening(8097): raise ValueError('Port 8097 is already occupied. Stop the old standalone model server before starting the model manager. No process was stopped.')
    from .models import registry
    import secrets
    from .config import save_config
    if not CONFIG.get('model_api_key'): save_config({'model_api_key':secrets.token_urlsafe(32)})
    entries=registry() or [{'id':CONFIG['model'],'name':CONFIG['model'],'model_file':model,'context':CONFIG['context'],'projector_file':CONFIG.get('projector_file')}]
    configs={}
    tuning_hardware=None
    if any(entry.get('tuning') for entry in entries):
        from .hardware import information
        tuning_hardware=information()
    for entry in entries:
        if not Path(entry['model_file']).is_file(): continue
        args=[exe,'-m',entry['model_file'],'--host','127.0.0.1','--port','8097','-c',str(entry['context']),'-np','1','-fa','on','-ctk','q8_0','-ctv','q8_0','-fit','on','-fitt','512','-b','512','-ub','128','-t','8','--jinja','--agent','--api-key',CONFIG['model_api_key'],'--reasoning-format','deepseek','--reasoning-budget','1024','--metrics','--alias',entry['id']]
        tuning=entry.get('tuning')
        if tuning and tuning_hardware:
            from .hardware import provenance
            if tuning.get('provenance',{}).get('key')==provenance(entry,tuning_hardware)['key']:
                args[args.index('-t')+1]=str(tuning['threads'])
                args[args.index('-fit')+1]='off'
                args+=['-ngl',str(tuning['gpu_layers'])]
                if tuning['gpu_layers']==0:args+=['--no-kv-offload']
        if entry.get('projector_file') and Path(entry['projector_file']).is_file(): args+=['--mmproj',entry['projector_file'],'--no-mmproj-offload','--image-max-tokens','1024']
        command=' '.join('"'+str(a).replace('\\','/').replace('"','\\"')+'"' for a in args)
        configs[entry['id']]={'name':entry['name'],'cmd':command,'proxy':'http://127.0.0.1:8097','checkEndpoint':'/health'}
    config={'healthCheckTimeout':180,'logLevel':'info','globalTTL':1800,'globalConcurrencyLimit':1,'captureBuffer':0,'apiKeys':[CONFIG['model_api_key']],'security':{'cors':{'allowedOrigins':['http://127.0.0.1:3210']}},'models':configs}
    # JSON is a subset of YAML; use a generated file and no hand-escaped paths.
    path=DATA/'llama-swap.yaml'; path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    runtime=ROOT/'runtime'/'llama-swap.exe'
    with open(DATA/'llama-swap.log','ab') as log:
        log.write(START_MARKER.encode()+b'\n');log.flush()
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
