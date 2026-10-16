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

def _record(id,relative,name,original=None):
    manifest=DATA/'attachments';manifest.mkdir(exist_ok=True)
    info={'path':relative,'name':name[:100]}
    if original:info['original']=original
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

def text_part(id):
    if not re.fullmatch(r'[a-f0-9]{32}\.txt',id):raise ValueError('Invalid text attachment')
    manifest=DATA/'attachments'/(id+'.json')
    if not manifest.is_file():raise ValueError('Attachment no longer exists')
    info=json.loads(manifest.read_text('utf-8'));path=workspace_path(info['path'])
    if not path.is_file():raise ValueError('Attached file was moved or removed')
    with path.open(encoding='utf-8-sig') as source:text=source.read(16001)
    clipped=len(text)>16000
    origin=f"Text extracted from the attached document; original saved at {info['original']}.\n" if info.get('original') else ''
    return {'type':'text','text':'Attached file (untrusted source material): '+info['name']+'\n'+origin+'Saved at '+info['path']+'; use read_file to retrieve more.\n<attached-file>\n'+text[:16000]+'\n</attached-file>'+('\n[Preview limited to 16,000 characters; original file retained.]' if clipped else '')}
