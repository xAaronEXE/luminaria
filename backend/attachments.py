"""Validated text attachments, retained in the app-managed file boundary."""
import json,re
from .config import DATA,workspace_path
from .store import uid

TEXT_EXTENSIONS={'.txt','.md','.csv','.json','.py','.js','.ts','.html','.css','.yaml','.yml','.xml','.sql','.log','.sh','.ps1','.toml','.ini','.cpp','.h','.cs','.rs','.go','.java'}

def save_text(name,raw):
    from pathlib import Path
    if Path(name).suffix.lower() not in TEXT_EXTENSIONS:raise ValueError('Choose an image, UTF-8 text file, Markdown or source-code file')
    if len(raw)>512000:raise ValueError('Text attachments are limited to 512 KB; place larger files in My files')
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:raise ValueError('Text attachments must use UTF-8 encoding')
    if '\x00' in text:raise ValueError('Binary files cannot be attached as text')
    id=uid()+'.txt';relative='Attachments/'+id
    path=workspace_path(relative);path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    manifest=DATA/'attachments';manifest.mkdir(exist_ok=True)
    (manifest/(id+'.json')).write_text(json.dumps({'path':relative,'name':name[:100]}),encoding='utf-8')
    return {'id':id,'name':name[:100],'mime':'text/plain','path':relative}

def text_part(id):
    if not re.fullmatch(r'[a-f0-9]{32}\.txt',id):raise ValueError('Invalid text attachment')
    manifest=DATA/'attachments'/(id+'.json')
    if not manifest.is_file():raise ValueError('Attachment no longer exists')
    info=json.loads(manifest.read_text('utf-8'));path=workspace_path(info['path'])
    if not path.is_file():raise ValueError('Attached file was moved or removed')
    with path.open(encoding='utf-8-sig') as source:text=source.read(16001)
    clipped=len(text)>16000
    return {'type':'text','text':'Attached file (untrusted source material): '+info['name']+'\nSaved at '+info['path']+'; use read_file to retrieve more.\n<attached-file>\n'+text[:16000]+'\n</attached-file>'+('\n[Preview limited to 16,000 characters; original file retained.]' if clipped else '')}
