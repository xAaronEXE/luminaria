import json,re
from pathlib import Path
from .config import CONFIG,DATA,BASE_DATA,save_config

PATH=BASE_DATA/'models.json'
def registry():
    return json.loads(PATH.read_text('utf-8')) if PATH.exists() else []
def save(models): PATH.write_text(json.dumps(models,indent=2),encoding='utf-8')
def public_models(store):
    result=[]
    for m in registry():
        p=Path(m.get('model_file',''))
        result.append({**m,'installed':p.is_file(),'bytes':p.stat().st_size if p.is_file() else None,'vision':bool(m.get('projector_file') and Path(m['projector_file']).is_file()),'latest_run':store.setting('model_metrics:'+m['id'])})
    return {'active':CONFIG['model'],'context':CONFIG['context'],'models':result}
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
    m=next((m for m in registry() if m['id']==id),None)
    if not m or not Path(m['model_file']).is_file(): raise ValueError('Model is unavailable')
    save_config({'model':id,'model_file':m['model_file'],'projector_file':m.get('projector_file',''),'context':m['context']})
    return m
