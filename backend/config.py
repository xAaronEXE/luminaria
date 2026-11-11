import re
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

def launcher(name):
    """Full path of a bundled npx or uvx, falling back to the bare name so a PC install still works."""
    tools=agent_tools_dir()
    exe={'npx':('node','npx.cmd'),'uvx':('python/Scripts','uvx.exe'),'uv':('python/Scripts','uv.exe')}[name]
    if tools and (tools/exe[0]/exe[1]).is_file(): return str(tools/exe[0]/exe[1])
    return exe[1] if os.name=='nt' else name

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
    # The whole PC is always in reach: file tools take full paths on any drive. Relative paths start in the
    # default folder (CONFIG['workspace']). Protected places below stay off limits. Approvals still follow the mode.
    return True

def pc_places():
    """Drives and the user's usual folders, so the assistant knows where things are without guessing."""
    home=Path.home();places={}
    for name in ('Desktop','Documents','Downloads','Pictures','Music','Videos'):
        for base in (home/'OneDrive',home):   # Windows often moves these into OneDrive
            if (base/name).is_dir(): places[name]=str(base/name);break
    drives=[]
    if os.name=='nt':
        try:
            import ctypes;mask=ctypes.windll.kernel32.GetLogicalDrives()
            drives=[f'{chr(65+i)}:\\' for i in range(26) if mask>>i&1]
        except Exception: drives=[]
    else: drives=['/']
    return {'home':str(home),'drives':drives,'folders':places}

def access_status():
    mode='full' if full_access() else 'review'
    return {'active':mode,'selected':mode,'restart_required':False}

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
    WORKSPACE_PROBLEM=f'Your default folder {chosen} could not be opened ({type(error).__name__}), so Luminaria is using {CONFIG["workspace"]} for now. Choose a folder in Settings › Default folder.'

def save_config(changes):
    CONFIG.update(changes)
    CONFIG_PATH.write_text(json.dumps(CONFIG,indent=2),encoding='utf-8')

def protected_roots():
    # Places the assistant never reads or writes through file tools, anywhere on the PC:
    # Luminaria's own data (settings, tokens, history), the program itself, Windows, and credential folders.
    home=Path.home()
    roots=[DATA,BASE_DATA,APP_HOME,home/'.ssh',home/'.aws',home/'.gnupg',home/'.azure',home/'.config'/'gcloud',home/'.kube']
    for name in ('WINDIR','SystemRoot'):
        if os.environ.get(name): roots.append(Path(os.environ[name]))
    if os.name!='nt': roots+=[Path('/etc'),Path('/proc'),Path('/sys'),Path('/boot'),Path('/root')]
    for name in ('APPDATA','LOCALAPPDATA'):
        if os.environ.get(name): roots+= [Path(os.environ[name])/'Microsoft'/'Credentials',Path(os.environ[name])/'Microsoft'/'Protect']
    return [r.resolve() for r in roots]

def sensitive_roots():
    """Installed programs and their shared data. Open to the assistant, but changing anything there always asks first,
    in every access mode, until scripts run under their own locked-down Windows identity."""
    return [Path(os.environ[n]).resolve() for n in ('PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROGRAMDATA') if os.environ.get(n)]

def always_ask(name,args):
    """True when this tool call changes something under Program Files or ProgramData."""
    if name not in ('write_file','edit_file','delete_file') or not isinstance(args,dict) or not args.get('path'): return False
    try: target=(Path(CONFIG['workspace']).resolve()/os.path.expandvars(str(args['path']))).resolve()
    except (OSError,ValueError): return False
    return any(_inside(target,root) for root in sensitive_roots())

SYSTEM_FOLDERS=('$recycle.bin','system volume information','recovery','$winreagent','$sysreset')
def system_area(target):
    """Other people's profiles and Windows' own housekeeping folders on any drive."""
    parts=[p.lower() for p in target.parts]
    if len(parts)>1 and parts[1] in SYSTEM_FOLDERS: return True
    home=Path.home().resolve(); users=home.parent
    if os.name=='nt' and _inside(target,users) and target!=users and not _inside(target,home):
        return target.relative_to(users).parts[0].lower() not in ('public',)
    return False

def command_guard(text):
    """Refuse a command or script that names a strictly off-limits place or asks for administrator rights.
    This reads the text only, so it is a guard against mistakes, not a security boundary: a determined script could
    still reach these places until scripts run under their own Windows identity."""
    low=str(text or '').lower().replace('/','\\')
    if re.search(r'-verb\s+runas|\brunas(\.exe)?\s|\bsudo\s|start-process[^\n|;]*-verb|\bgsudo\b|\[security\.principal\.windowsprincipal\]',low):
        raise PermissionError('Luminaria does not run commands as administrator. Tell the user which step needs administrator rights so they can do it themselves.')
    named=['%windir%','%systemroot%','$env:windir','$env:systemroot','\\system32','\\syswow64','\\microsoft\\credentials','\\microsoft\\protect',
           '\\.ssh','\\.aws','\\.gnupg','\\.azure','\\.kube','cmdkey','vaultcmd']
    for name in ('WINDIR','SystemRoot'):
        if os.environ.get(name): named.append(os.environ[name].lower().rstrip('\\')+'\\')
    work=Path(CONFIG['workspace']).resolve()
    for root in (DATA,BASE_DATA):
        # When the default folder sits inside the data folder (development runs), naming it must stay possible.
        if not _inside(work,root.resolve()): named.append(str(root).lower().replace('/','\\')+'\\')
    hit=next((n for n in named if n and n in low+'\\'),None)
    if hit: raise PermissionError('This command touches a place that is strictly off limits to Luminaria (Windows itself, saved credentials or Luminaria\'s own data). Work somewhere else, or tell the user it cannot be done.')

def skill_folders():
    """Where skills live. The assistant may read these (a skill's scripts and references) but never change them."""
    return [(ROOT/'skills').resolve(),(DATA/'skills').resolve()]

def manual_path():
    """Luminaria's user manual (the README), shipped with the app so the assistant can answer questions about itself."""
    return (ROOT/'README.md').resolve()

def _inside(target,folder): return target==folder or target.is_relative_to(folder)

def workspace_path(path='.',roam=False,write=False):
    root=Path(CONFIG['workspace']).resolve()
    path=str(path or '.').strip()
    if path.startswith('~'): path=str(Path(path).expanduser())
    if os.name=='nt' and '%' in path: path=os.path.expandvars(path)
    target=(root/path).resolve()
    if target==manual_path():
        if write: raise PermissionError("Luminaria's manual is read-only.")
        return target
    for folder in skill_folders():
        if _inside(target,folder):
            if write: raise PermissionError('Skill folders are read-only. Save outputs in the default folder.')
            return target
    if system_area(target): raise PermissionError('That place belongs to Windows or to another person on this PC and is off limits.')
    for protected in protected_roots():
        if _inside(target,protected):
            # A protected area that contains the default folder (the default folder sits inside Luminaria's own
            # folder) does not block the default folder's own contents. Anything else inside it stays off limits,
            # even when the default folder is a whole drive that happens to contain Luminaria's data.
            if _inside(root,protected) and _inside(target,root): continue
            raise PermissionError('That location is protected: Luminaria\'s own settings and history, program files, Windows and credential folders are never available to the assistant.')
    if not _inside(target,root):
        if roam: return target
        raise ValueError('Path is outside the default folder.')
    return target
