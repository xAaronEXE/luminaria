import json,re,shutil
from pathlib import Path
from .config import CONFIG,DATA,BASE_DATA,save_config

PATH=BASE_DATA/'models.json'

def model_storage(models):
    """Report the actual target volume, counting each installed weight once."""
    folder=BASE_DATA.parent/'models'
    probe=folder
    while not probe.exists() and probe.parent!=probe: probe=probe.parent
    usage=shutil.disk_usage(probe)
    seen=set(); model_bytes=0
    for model in models:
        for key in ('model_file','projector_file'):
            raw=model.get(key)
            if not raw: continue
            path=Path(raw).resolve()
            if path in seen: continue
            seen.add(path)
            try:
                if path.is_file(): model_bytes+=path.stat().st_size
            except OSError: pass
    return {'path':str(folder),'drive':probe.resolve().anchor,'total':usage.total,
            'used':usage.used,'free':usage.free,'model_bytes':model_bytes}
def registry():
    return json.loads(PATH.read_text('utf-8')) if PATH.exists() else []
def save(models):
    tmp=PATH.with_suffix('.tmp');tmp.write_text(json.dumps(models,indent=2),encoding='utf-8');tmp.replace(PATH)
def public_models(store):
    from .benchmark_store import history
    result=[]
    for m in registry():
        p=Path(m.get('model_file',''))
        result.append({**m,'benchmarks':history(m['id'],m.get('benchmarks',[])),'installed':p.is_file(),'bytes':p.stat().st_size if p.is_file() else None,'vision':bool(m.get('projector_file') and Path(m['projector_file']).is_file()),'latest_run':store.setting('model_metrics:'+m['id'])})
    storage=model_storage(result)
    from .services import remote_models
    result+=[{**m,'installed':True,'benchmarks':[],'bytes':None,'vision':False} for m in remote_models()]
    return {'active':CONFIG['model'],'context':CONFIG['context'],'models':result,'storage':storage}
def add_model(body):
    id=body.get('id','')
    if not re.fullmatch('[a-zA-Z0-9_-]{1,60}',id): raise ValueError('Use a short model ID containing letters, numbers, hyphens or underscores')
    models=registry()
    if any(m['id']==id for m in models): raise ValueError('That model ID already exists')
    path=Path(body['model_file'])
    if not path.is_file() or path.suffix.lower()!='.gguf': raise ValueError('Choose an existing GGUF file')
    if body.get('projector_file') and not Path(body['projector_file']).is_file(): raise ValueError('Projector file does not exist')
    models.append({'id':id,'name':str(body.get('name') or id)[:120],'description':str(body.get('description','User-added model. Capabilities have not been tested.'))[:1000],'model_file':str(path),'projector_file':body.get('projector_file',''),'context':max(4096,min(262144,int(body.get('context',16384)))),'quantization':str(body.get('quantization','Unknown'))[:50],'strengths':['User-configured'],'benchmarks':[],'benchmark_note':'Not benchmarked on this machine.'})
    save(models); return {'id':id,'restart_required':True}
def select(id):
    from .services import is_remote, remote_models
    if is_remote(id):
        m=next((m for m in remote_models() if m['id']==id),None)
        if not m: raise ValueError('That model service is not set up')
        save_config({'model':id,'context':m['context']}); return m
    m=next((m for m in registry() if m['id']==id),None)
    if not m or not Path(m['model_file']).is_file(): raise ValueError('Model is unavailable')
    from .runtime import resolve_executable
    executable=resolve_executable()
    save_config({'model':id,'model_file':m['model_file'],'projector_file':m.get('projector_file',''),'context':m['context'],'llama_executable':executable,'endpoint':'http://127.0.0.1:8098/v1','tokenizer':'http://127.0.0.1:8097'})
    return m

def set_context(id,value):
    if isinstance(value,bool) or not isinstance(value,int) or not 4096<=value<=262144:
        raise ValueError('Choose a whole number from 4,096 to 262,144 tokens')
    models=registry();model=next((m for m in models if m['id']==id),None)
    if not model or not Path(model['model_file']).is_file():raise ValueError('Install this model first')
    supported=model.get('context_supported')
    from .model_catalog import CATALOG
    for entry in CATALOG:
        if any(q['id']==id or q['filename']==Path(model['model_file']).name for q in entry['quants']):
            supported=entry.get('context_supported') or supported;break
    if supported and value>supported:raise ValueError(f'This model reports a maximum of {supported:,} tokens')
    model['context']=value;save(models)
    if CONFIG['model']==id:save_config({'context':value})
    return model

LAUNCH_FIELDS={'gpu_layers':(-1,512),'cpu_moe':(0,256),'ubatch':(64,4096)}

def set_launch(id,body):
    """Save how llama-server loads one model. 'auto' clears custom settings and lets llama.cpp fit it."""
    models=registry();model=next((m for m in models if m['id']==id),None)
    if not model or not Path(model['model_file']).is_file():raise ValueError('Install this model first')
    if body.get('mode')=='auto':
        model.pop('launch',None);save(models);return model
    launch={}
    for key,(low,high) in LAUNCH_FIELDS.items():
        value=body.get(key)
        if value is None:continue
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:raise ValueError(f'{key.replace("_"," ")} must be a whole number from {low} to {high}')
        launch[key]=value
    if launch.get('ubatch') and launch['ubatch']&(launch['ubatch']-1):raise ValueError('Batch size must be a power of two, such as 128, 256 or 512')
    model['launch']=launch;save(models)
    if body.get('context') is not None:return set_context(id,body['context'])
    return model
