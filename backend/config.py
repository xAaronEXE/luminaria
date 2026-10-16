import json, os, sys
from pathlib import Path

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
APP_HOME = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else ROOT
BASE_DATA = Path(os.environ.get('STUDIO_DATA', str(APP_HOME/'data')))
VERSION = (ROOT/'VERSION').read_text(encoding='utf-8').strip()
PROFILE_ID='local'
if (BASE_DATA/'profiles.json').exists():
    import re
    candidate=json.loads((BASE_DATA/'profiles.json').read_text('utf-8')).get('selected','local')
    if candidate=='local' or re.fullmatch(r'[a-f0-9]{32}',candidate): PROFILE_ID=candidate
DATA=BASE_DATA if PROFILE_ID=='local' else BASE_DATA/'profiles'/PROFILE_ID
DATA.mkdir(parents=True,exist_ok=True)
CONFIG_PATH=DATA/'config.json'
DEFAULT={
 'workspace':str((Path(sys.executable).parent if getattr(sys,'frozen',False) else DATA)/'Files'/PROFILE_ID),
 'endpoint':'http://127.0.0.1:8098/v1', 'tokenizer':'http://127.0.0.1:8097',
 'model':'local-qwen','context':32768,'output_tokens':4096,'compact_ratio':0.80,
 'version':VERSION, 'python':'python','node':'node','mcp':{},'external_tools':False,'ask_reads':False
}
device=json.loads((BASE_DATA/'config.json').read_text('utf-8')) if (BASE_DATA/'config.json').exists() else {}
shared={k:v for k,v in device.items() if k in ('endpoint','tokenizer','model','context','model_file','projector_file','model_api_key','llama_executable','python','node')}
CONFIG=DEFAULT | shared | (json.loads(CONFIG_PATH.read_text('utf-8')) if CONFIG_PATH.exists() else {})
CONFIG['version']=VERSION
CONFIG.pop('release_repo',None)
# Permission mode is latched at process startup. Saving it never changes a live run.
FULL_ACCESS = CONFIG.get('access_mode', 'review') == 'full'
CONFIG['access_mode'] = 'full' if FULL_ACCESS else 'review'

def access_status():
    active = 'full' if FULL_ACCESS else 'review'
    return {'active': active, 'selected': CONFIG['access_mode'],
            'restart_required': active != CONFIG['access_mode']}

def external_tools_enabled():
    return FULL_ACCESS or CONFIG.get('external_tools', False)
try:
    Path(CONFIG['workspace']).mkdir(parents=True,exist_ok=True)
except PermissionError:
    if CONFIG_PATH.exists(): raise
    CONFIG['workspace']=str(DATA/'Files');Path(CONFIG['workspace']).mkdir(parents=True,exist_ok=True)

def save_config(changes):
    CONFIG.update(changes)
    CONFIG_PATH.write_text(json.dumps(CONFIG,indent=2),encoding='utf-8')

def workspace_path(path='.'):
    root=Path(CONFIG['workspace']).resolve()
    target=(root/path).resolve()
    if not target.is_relative_to(root): raise ValueError('Path is outside the selected workspace')
    return target
