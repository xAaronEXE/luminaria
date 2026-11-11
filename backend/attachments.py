"""Validated text and document attachments, retained in the app-managed file boundary."""
import io,json,re,zipfile
from .config import DATA,workspace_path
from .store import uid

TEXT_EXTENSIONS={'.txt','.md','.csv','.json','.py','.js','.ts','.html','.css','.yaml','.yml','.xml','.sql','.log','.sh','.ps1','.toml','.ini','.cpp','.h','.cs','.rs','.go','.java'}
DOCUMENT_EXTENSIONS={'.pdf','.docx'}
DOCUMENT_LIMIT=25_000_000
PAGE_LIMIT=500
TEXT_LIMIT=5_000_000
UNPACKED_LIMIT=200_000_000
FOLDER_FILE_LIMIT=200
FOLDER_BYTE_LIMIT=100_000_000
TEXT_FILE_LIMIT=2_000_000

def _record(id,relative,name,original=None,kind='document'):
    manifest=DATA/'attachments';manifest.mkdir(exist_ok=True)
    info={'path':relative,'name':name[:100]}
    if original:info.update(original=original,kind=kind)
    (manifest/(id+'.json')).write_text(json.dumps(info),encoding='utf-8')
    return {'id':id,'name':name[:100],'mime':'text/plain','path':relative,**({'original':original} if original else {})}

def save_text(name,raw):
    from pathlib import Path
    if Path(name).suffix.lower() not in TEXT_EXTENSIONS:raise ValueError('Choose an image, PDF, Word document, UTF-8 text file, Markdown or source-code file')
    if len(raw)>512000:raise ValueError('Text attachments are limited to 512 KB; place larger files in My files')
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:raise ValueError('Text attachments must use UTF-8 encoding')
    if '\x00' in text:raise ValueError('Binary files cannot be attached as text')
    id=uid()+'.txt';relative='Attachments/'+id
    path=workspace_path(relative);path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    return _record(id,relative,name)

def _pdf_text(raw):
    from pypdf import PdfReader
    try:
        reader=PdfReader(io.BytesIO(raw))
        if reader.is_encrypted and not reader.decrypt(''):raise ValueError('This PDF is password-protected. Remove the password and attach it again')
        if len(reader.pages)>PAGE_LIMIT:raise ValueError(f'PDFs are limited to {PAGE_LIMIT} pages; split the document and attach the part you need')
        pages=[]
        for number,page in enumerate(reader.pages,1):
            text=(page.extract_text() or '').strip()
            if text:pages.append(f'--- Page {number} ---\n{text}')
        return '\n\n'.join(pages)
    except ValueError:raise
    except Exception as error:raise ValueError('This PDF could not be read. It may be damaged') from error

def _docx_text(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist())>UNPACKED_LIMIT:raise ValueError('This Word document expands to more than 200 MB and was not opened')
            if 'word/document.xml' not in archive.namelist():raise ValueError('This is not a Word .docx document')
    except zipfile.BadZipFile as error:raise ValueError('This Word document could not be read. Older .doc files must be saved as .docx first') from error
    from docx import Document
    try:document=Document(io.BytesIO(raw))
    except Exception as error:raise ValueError('This Word document could not be read. It may be damaged') from error
    blocks=[p.text for p in document.paragraphs if p.text.strip()]
    for number,table in enumerate(document.tables,1):
        rows=[' | '.join(cell.text.strip() for cell in row.cells) for row in table.rows]
        blocks.append(f'--- Table {number} ---\n'+'\n'.join(rows))
    return '\n\n'.join(blocks)

def save_document(name,raw):
    from pathlib import Path
    suffix=Path(name).suffix.lower()
    if suffix not in DOCUMENT_EXTENSIONS:raise ValueError('Choose a PDF or Word .docx document')
    if len(raw)>DOCUMENT_LIMIT:raise ValueError('Documents are limited to 25 MB; place larger files in My files')
    if suffix=='.pdf' and not raw.startswith(b'%PDF-'):raise ValueError('This file is not a PDF')
    text=_pdf_text(raw) if suffix=='.pdf' else _docx_text(raw)
    if not text.strip():
        raise ValueError('No selectable text was found. Scanned pages are images; attach them as PNG or JPEG instead' if suffix=='.pdf' else 'This Word document has no text')
    clipped=len(text)>TEXT_LIMIT
    text=text[:TEXT_LIMIT]+('\n\n[Extraction stopped at 5,000,000 characters; the original document is retained.]' if clipped else '')
    base=uid();original='Attachments/'+base+suffix;relative='Attachments/'+base+'.txt'
    folder=workspace_path(original).parent;folder.mkdir(exist_ok=True)
    workspace_path(original).write_bytes(raw);workspace_path(relative).write_text(text,encoding='utf-8')
    return _record(base+'.txt',relative,name,original)

def save(name,raw):
    from pathlib import Path
    return save_document(name,raw) if Path(name).suffix.lower() in DOCUMENT_EXTENSIONS else save_text(name,raw)

def _size(n):
    for unit in ('bytes','KB','MB','GB'):
        if n<1024 or unit=='GB': return f'{n:.0f} {unit}' if unit=='bytes' else f'{n:.1f} {unit}'
        n/=1024

def attach_location(path,label=None):
    """Attach a file or folder that stays where it is on the PC. Nothing is copied: the assistant is told where it is
    and works on it in place with its normal tools, so any type and any size can be attached."""
    from pathlib import Path
    target=workspace_path(str(path),roam=True)   # refuses protected places such as the Windows folder
    if not target.exists(): raise ValueError('That file or folder no longer exists: '+str(path)[:200])
    name=label or target.name or str(target)
    if target.is_dir():
        entries=[]
        try:
            for i,child in enumerate(sorted(target.iterdir(),key=lambda c:(c.is_file(),c.name.lower()))):
                if i>=200: entries.append('… more items not listed'); break
                try: entries.append(child.name+('/' if child.is_dir() else f'  ({_size(child.stat().st_size)})'))
                except OSError: entries.append(child.name)
        except OSError as error: raise ValueError('That folder could not be opened: '+str(error)[:160])
        lines=[f'Folder on this PC: {target}',f'{len(entries)} item{"" if len(entries)==1 else "s"} at the top level:','']+entries
        kind='folder_location'
    else:
        size=target.stat().st_size
        lines=[f'File on this PC: {target}',f'Type: {target.suffix.lower() or "no extension"}   Size: {_size(size)}']
        if target.suffix.lower() in TEXT_EXTENSIONS and size<=TEXT_FILE_LIMIT:
            try: lines+=['','Start of the file:',target.read_text(encoding='utf-8-sig',errors='replace')[:12000]]
            except OSError: pass
        kind='file_location'
    id=uid()+'.txt';relative='Attachments/'+id
    note=workspace_path(relative);note.parent.mkdir(exist_ok=True);note.write_text('\n'.join(lines),encoding='utf-8')
    return {**_record(id,relative,name,str(target),kind),'location':str(target)}

def save_any(name,raw):
    """A file of any other type (spreadsheet, archive, video…) sent from the browser: kept as it is in My files and attached by location."""
    from pathlib import Path
    clean=re.sub(r'[^A-Za-z0-9 ._()-]+','_',Path(str(name)).name).strip(' .')[:100] or 'file'
    target=workspace_path('Attachments/'+uid()[:8]+'-'+clean);target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
    return attach_location(target,clean)


def _import_state(id):
    if not re.fullmatch(r'[a-f0-9]{32}',id):raise ValueError('Invalid folder import')
    path=DATA/'attachments'/'imports'/(id+'.json')
    if not path.is_file():raise ValueError('Folder import not found. Start the folder attachment again')
    return path,json.loads(path.read_text('utf-8'))

def start_import(name):
    label=re.sub(r'[^A-Za-z0-9 ._-]+','',str(name)).strip(' .')[:60] or 'Folder'
    id=uid();root=f'Imports/{label}-{id[:8]}'
    folder=DATA/'attachments'/'imports';folder.mkdir(parents=True,exist_ok=True)
    (folder/(id+'.json')).write_text(json.dumps({'name':label,'root':root,'files':[],'bytes':0}),encoding='utf-8')
    return {'id':id,'root':root}

def add_import_file(id,relative,raw):
    from pathlib import PurePosixPath
    state_path,state=_import_state(id)
    parts=PurePosixPath(str(relative).replace('\\','/')).parts
    if not parts or len(parts)>12 or any(p in ('','.','..') or p.startswith(('.','/')) or ':' in p or len(p)>120 for p in parts):raise ValueError('Unsupported file path in folder: '+str(relative)[:200])
    clean='/'.join(parts);suffix=PurePosixPath(clean).suffix.lower()
    if suffix not in TEXT_EXTENSIONS|DOCUMENT_EXTENSIONS:raise ValueError('Unsupported file type in folder: '+clean)
    if clean in state['files']:raise ValueError('File already added: '+clean)
    if len(state['files'])>=FOLDER_FILE_LIMIT:raise ValueError(f'Folders are limited to {FOLDER_FILE_LIMIT} files')
    if state['bytes']+len(raw)>FOLDER_BYTE_LIMIT:raise ValueError('Folders are limited to 100 MB of supported files')
    if suffix in TEXT_EXTENSIONS:
        if len(raw)>TEXT_FILE_LIMIT:raise ValueError(clean+' is larger than 2 MB')
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:raise ValueError(clean+' is not UTF-8 text')
        if '\x00' in text:raise ValueError(clean+' is binary, not text')
        extracted=None
    else:
        if len(raw)>DOCUMENT_LIMIT:raise ValueError(clean+' is larger than 25 MB')
        if suffix=='.pdf' and not raw.startswith(b'%PDF-'):raise ValueError(clean+' is not a PDF')
        try:extracted=_pdf_text(raw) if suffix=='.pdf' else _docx_text(raw)
        except ValueError as error:extracted='[Text could not be extracted: '+str(error)+']'
        extracted=extracted[:TEXT_LIMIT] or '[No selectable text found]'
    target=workspace_path(state['root']+'/'+clean);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    if extracted is not None:workspace_path(state['root']+'/'+clean+'.txt').write_text(extracted,encoding='utf-8')
    state['files'].append(clean);state['bytes']+=len(raw)
    state_path.write_text(json.dumps(state),encoding='utf-8')
    return {'path':clean,'files':len(state['files'])}

def finish_import(id,skipped=0):
    state_path,state=_import_state(id)
    if not state['files']:raise ValueError('No supported files were found in this folder')
    lines=[f"Folder: {state['name']}",f"Saved at {state['root']} ({len(state['files'])} file{'' if len(state['files'])==1 else 's'})."]
    if skipped:lines.append(f'{int(skipped)} unsupported, hidden or oversized files were left out.')
    lines.append('PDF and Word files have extracted text beside them with an added .txt extension. Use read_file or search_files with these paths.\n')
    lines+=[state['root']+'/'+f+('  (text: '+f+'.txt)' if f.lower().endswith(tuple(DOCUMENT_EXTENSIONS)) else '') for f in sorted(state['files'])]
    attachment=uid()+'.txt';relative='Attachments/'+attachment
    path=workspace_path(relative);path.parent.mkdir(exist_ok=True);path.write_text('\n'.join(lines),encoding='utf-8')
    state_path.unlink()
    return _record(attachment,relative,state['name']+' (folder)',state['root'],'folder')

def text_part(id):
    if not re.fullmatch(r'[a-f0-9]{32}\.txt',id):raise ValueError('Invalid text attachment')
    manifest=DATA/'attachments'/(id+'.json')
    if not manifest.is_file():raise ValueError('Attachment no longer exists')
    info=json.loads(manifest.read_text('utf-8'));path=workspace_path(info['path'])
    if not path.is_file():raise ValueError('Attached file was moved or removed')
    with path.open(encoding='utf-8-sig') as source:text=source.read(16001)
    clipped=len(text)>16000
    origin=''
    if info.get('kind') in ('file_location','folder_location'):
        what='folder' if info['kind']=='folder_location' else 'file'
        return {'type':'text','text':f"Attached {what} (it stays where it is on this PC; nothing was copied): {info['name']}\nFull path: {info['original']}\n"
                f"Work on it in place with your tools (list_files, read_file, inspect_file, search_files, run_code, run_command) using that full path.\n<attached-{what}>\n{text[:16000]}\n</attached-{what}>"}
    if info.get('kind')=='folder':origin=f"Contents list for a folder copied to {info['original']}.\n"
    elif info.get('original'):origin=f"Text extracted from the attached document; original saved at {info['original']}.\n"
    return {'type':'text','text':'Attached file (untrusted source material): '+info['name']+'\n'+origin+'Saved at '+info['path']+'; use read_file to retrieve more.\n<attached-file>\n'+text[:16000]+'\n</attached-file>'+('\n[Preview limited to 16,000 characters; original file retained.]' if clipped else '')}
