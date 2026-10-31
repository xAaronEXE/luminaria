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
 'model':'local-qwen','context':32768,'output_tokens':4096,'compact_ratio':0.80,'compact_keep_turns':4,
 'version':VERSION, 'python':'python','node':'node','mcp':{},'external_tools':False,'ask_reads':False
}
device=json.loads((BASE_DATA/'config.json').read_text('utf-8')) if (BASE_DATA/'config.json').exists() else {}
shared={k:v for k,v in device.items() if k in ('endpoint','tokenizer','model','context','model_file','projector_file','model_api_key','llama_executable','python','node')}
CONFIG=DEFAULT | shared | (json.loads(CONFIG_PATH.read_text('utf-8')) if CONFIG_PATH.exists() else {})
CONFIG['version']=VERSION
CONFIG.pop('release_repo',None)
# Permission mode is read live, so choosing Hands-free applies to the next task without a restart.
if CONFIG.get('access_mode') not in ('review','full'): CONFIG['access_mode']='review'

def full_access():
    return CONFIG.get('access_mode','review')=='full'

def whole_pc():
    # Hands-free plus "whole PC": file tools may reach any drive, not only the working folder.
    return full_access() and bool(CONFIG.get('whole_pc',False))

def access_status():
    mode='full' if full_access() else 'review'
    return {'active':mode,'selected':mode,'restart_required':False,'whole_pc':whole_pc()}

def external_tools_enabled():
    return full_access() or CONFIG.get('external_tools',False)

# A missing drive, a file where the folder should be, or no permission must never stop the app from opening.
# Fall back to the default folder for this session and say why; the saved choice is left for the user to change.
WORKSPACE_PROBLEM=''
try:
    Path(CONFIG['workspace']).mkdir(parents=True,exist_ok=True)
    if not Path(CONFIG['workspace']).is_dir(): raise NotADirectoryError(CONFIG['workspace'])
except OSError as error:
    chosen=CONFIG['workspace']
    CONFIG['workspace']=DEFAULT['workspace']
    try: Path(CONFIG['workspace']).mkdir(parents=True,exist_ok=True)
    except OSError: CONFIG['workspace']=str(DATA/'Files');Path(CONFIG['workspace']).mkdir(parents=True,exist_ok=True)
    WORKSPACE_PROBLEM=f'Your working folder {chosen} could not be opened ({type(error).__name__}), so Luminaria is using {CONFIG["workspace"]} for now. Choose a folder in Settings › Working folder.'

def save_config(changes):
    CONFIG.update(changes)
    CONFIG_PATH.write_text(json.dumps(CONFIG,indent=2),encoding='utf-8')

def protected_roots():
    # Places the assistant never reads or writes through file tools, even with Whole PC on:
    # Luminaria's own data (settings, tokens, history), the program itself, Windows, and credential folders.
    home=Path.home()
    roots=[DATA,BASE_DATA,APP_HOME,home/'.ssh',home/'.aws',home/'.gnupg',home/'.azure',home/'.config'/'gcloud',home/'.kube']
    for name in ('WINDIR','SystemRoot','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMDATA'):
        if os.environ.get(name): roots.append(Path(os.environ[name]))
    if os.name!='nt': roots+=[Path('/etc'),Path('/proc'),Path('/sys'),Path('/boot'),Path('/root')]
    for name in ('APPDATA','LOCALAPPDATA'):
        if os.environ.get(name): roots+= [Path(os.environ[name])/'Microsoft'/'Credentials',Path(os.environ[name])/'Microsoft'/'Protect']
    return [r.resolve() for r in roots]

def workspace_path(path='.',roam=False):
    root=Path(CONFIG['workspace']).resolve()
    target=(root/path).resolve()
    if not target.is_relative_to(root):
        if roam and whole_pc():
            if any(target==r or target.is_relative_to(r) for r in protected_roots()):
                raise PermissionError('That location is protected: Luminaria\'s own data, program files, Windows and credential folders are never available to the assistant.')
            return target
        raise ValueError('Path is outside the selected workspace. Turn on "Whole PC" in Settings › Permissions to let the assistant use other folders and drives.')
    return target
