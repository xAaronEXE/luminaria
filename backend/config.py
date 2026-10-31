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

def agent_tools_dir():
    """Folder with the bundled Python, Node and connectors that ship with the installer."""
    for folder in (APP_HOME/'runtime'/'agent-tools', ROOT/'runtime'/'agent-tools', APP_HOME.parent/'runtime'/'agent-tools'):
        if folder.is_dir(): return folder
    return None

def bundled_runtime(kind):
    tools=agent_tools_dir()
    if not tools: return None
    exe=tools/('python' if kind=='python' else 'node')/('python.exe' if kind=='python' else 'node.exe')
    return str(exe) if exe.is_file() else None

def runtime_path_dirs():
    """Folders to put first on PATH for commands, so `python`, `pip`, `node` and `npx` use the bundled copies."""
    tools=agent_tools_dir()
    if not tools: return []
    return [str(d) for d in (tools/'python', tools/'python'/'Scripts', tools/'node') if d.is_dir()]

def find_runtime(kind):
    """Find Python or Node on this PC without asking the user. Returns a path string or None."""
    import shutil
    name={'python':'python','node':'node'}[kind]
    configured=str(CONFIG.get(kind) or name)
    bundled=bundled_runtime(kind)
    if bundled and configured==name: return bundled  # the copy shipped with Luminaria, unless the user chose another
    def real(path):
        low=str(path).lower().replace('/','\\')
        return bool(path) and Path(path).is_file() and '\\windowsapps\\' not in low  # the Store shortcut is not a real install
    if real(configured): return configured
    found=shutil.which(configured) or shutil.which(name)
    if found and real(found): return found
    roots=[os.environ.get(k) for k in ('LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)')]
    candidates=[]
    for root in filter(None,roots):
        base=Path(root)
        if kind=='python':
            for folder in (base/'Programs'/'Python',base/'Python',base):
                if folder.is_dir(): candidates+=sorted(folder.glob('Python3*/python.exe'),reverse=True)
        else:
            candidates+=[base/'nodejs'/'node.exe',base/'Programs'/'nodejs'/'node.exe']
    if kind=='python':
        launcher=shutil.which('py')
        if launcher:
            try:
                import subprocess
                out=subprocess.run([launcher,'-3','-c','import sys;print(sys.executable)'],capture_output=True,text=True,timeout=8).stdout.strip()
                if out: candidates.insert(0,Path(out))
            except Exception: pass
    for c in candidates:
        if real(c): return str(c)
    return bundled

def runtime_missing_message(kind):
    if kind=='python': return 'Luminaria could not find its built-in Python. Reinstall Luminaria to restore it, then ask again. Nothing was changed.'
    return 'Luminaria could not find its built-in Node.js. Reinstall Luminaria to restore it, then ask again. Nothing was changed.'

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
