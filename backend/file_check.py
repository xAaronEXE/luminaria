"""inspect_file: lets the assistant confirm a file it made is real and valid before it says the job is done.

Opens each format the way a real program would (Office files as their zip packages, PDFs by their structure)
and returns the type, size, a short preview and any problem, in plain words. Read-only; never runs the file."""
import json, re, struct, zipfile
from pathlib import Path

PREVIEW = 600
MAX_READ = 50_000_000

def _office(path, kind):
    required = {'docx': 'word/document.xml', 'xlsx': 'xl/workbook.xml', 'pptx': 'ppt/presentation.xml'}[kind]
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if '[Content_Types].xml' not in names or required not in names:
                return {'ok': False, 'problem': f'This is not a valid {kind.upper()} file: it is missing {required}. It may be plain text with the wrong extension.'}
            if z.testzip() is not None: return {'ok': False, 'problem': 'The file is damaged: part of it fails its checksum.'}
            if kind == 'docx':
                xml = z.read('word/document.xml').decode('utf-8', 'replace')
                paragraphs = [re.sub(r'<[^>]+>', '', p) for p in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)]
                text = '\n'.join(p for p in paragraphs if p.strip())
                return {'ok': bool(text.strip()), 'paragraphs': len([p for p in paragraphs if p.strip()]), 'preview': text[:PREVIEW],
                        **({} if text.strip() else {'problem': 'The document opens but has no text.'})}
            if kind == 'xlsx':
                sheets = sorted(n for n in names if re.match(r'xl/worksheets/sheet\d+\.xml$', n))
                cells = sum(len(re.findall(r'<c[ >]', z.read(n).decode('utf-8', 'replace'))) for n in sheets[:20])
                shared = z.read('xl/sharedStrings.xml').decode('utf-8', 'replace') if 'xl/sharedStrings.xml' in names else ''
                shared += ''.join(z.read(n).decode('utf-8', 'replace') for n in sheets[:3])  # text written straight into cells
                words = ' '.join(re.sub(r'<[^>]+>', ' ', t) for t in re.findall(r'<t[^>]*>.*?</t>', shared, re.S))
                return {'ok': cells > 0, 'sheets': len(sheets), 'cells': cells, 'preview': ' '.join(words.split())[:PREVIEW],
                        **({} if cells else {'problem': 'The workbook opens but every sheet is empty.'})}
            slides = sorted(n for n in names if re.match(r'ppt/slides/slide\d+\.xml$', n))
            text = ' '.join(re.sub(r'<[^>]+>', ' ', z.read(n).decode('utf-8', 'replace')) for n in slides[:30])
            return {'ok': bool(slides), 'slides': len(slides), 'preview': ' '.join(text.split())[:PREVIEW],
                    **({} if slides else {'problem': 'The presentation has no slides.'})}
    except zipfile.BadZipFile:
        return {'ok': False, 'problem': f'This is not a valid {kind.upper()} file (Office files are zip packages; this one is not). It may be plain text saved with the wrong extension.'}

def _pdf(path):
    data = path.read_bytes()[:MAX_READ]
    if not data.startswith(b'%PDF-'): return {'ok': False, 'problem': 'This is not a PDF: it does not start with the PDF header.'}
    if b'%%EOF' not in data[-2048:]: return {'ok': False, 'problem': 'The PDF looks cut off: its end marker is missing.'}
    pages = len(re.findall(rb'/Type\s*/Page[^s]', data))
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path)); pages = len(reader.pages)
        text = (reader.pages[0].extract_text() or '') if pages else ''
        return {'ok': pages > 0, 'pages': pages, 'preview': ' '.join(text.split())[:PREVIEW]}
    except Exception:
        return {'ok': pages > 0, 'pages': pages, **({} if pages else {'problem': 'No pages were found in this PDF.'})}

def _image(path, head):
    if head.startswith(b'\x89PNG\r\n\x1a\n') and len(head) >= 24:
        w, h = struct.unpack('>II', head[16:24]); return {'ok': True, 'format': 'PNG', 'width': w, 'height': h}
    if head.startswith(b'\xff\xd8'): return {'ok': True, 'format': 'JPEG'}
    if head[:6] in (b'GIF87a', b'GIF89a'):
        w, h = struct.unpack('<HH', head[6:10]); return {'ok': True, 'format': 'GIF', 'width': w, 'height': h}
    if head.startswith(b'RIFF') and head[8:12] == b'WEBP': return {'ok': True, 'format': 'WebP'}
    return {'ok': False, 'problem': 'The file has an image extension but is not a PNG, JPEG, GIF or WebP image.'}

def inspect(path):
    path = Path(path)
    if not path.exists(): return {'status': 'error', 'ok': False, 'problem': 'There is no file at this path.'}
    if path.is_dir(): return {'status': 'error', 'ok': False, 'problem': 'This is a folder, not a file.'}
    size = path.stat().st_size
    base = {'path': str(path), 'bytes': size}
    if size == 0: return {**base, 'status': 'error', 'ok': False, 'problem': 'The file is empty.'}
    ext = path.suffix.lower().lstrip('.')
    try:
        if ext in ('docx', 'xlsx', 'pptx'): result = {'type': ext, **_office(path, ext)}
        elif ext == 'pdf': result = {'type': 'pdf', **_pdf(path)}
        elif ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            with path.open('rb') as f: result = {'type': 'image', **_image(path, f.read(32))}
        else:
            if size > MAX_READ: return {**base, 'status': 'ok', 'ok': True, 'type': ext or 'file', 'note': 'Large file; only its size was checked.'}
            raw = path.read_bytes()
            try: text = raw.decode('utf-8')
            except UnicodeDecodeError: return {**base, 'status': 'ok', 'ok': True, 'type': ext or 'binary', 'note': 'Binary file; only its size was checked.'}
            result = {'type': ext or 'text', 'ok': True, 'lines': text.count('\n') + 1, 'preview': text[:PREVIEW]}
            if ext == 'json':
                try: json.loads(text)
                except ValueError as e: result.update(ok=False, problem=f'Invalid JSON: {e}')
            elif ext in ('html', 'htm'):
                title = re.search(r'<title[^>]*>(.*?)</title>', text, re.S | re.I)
                result['title'] = title.group(1).strip()[:120] if title else ''
                if not re.search(r'<(html|body|div|main|section|p|h1)\b', text, re.I): result.update(ok=False, problem='This does not look like an HTML page: no page elements were found.')
            elif ext == 'csv':
                rows = [r for r in text.splitlines() if r.strip()]
                widths = {r.count(',') for r in rows[:200]}
                result['rows'] = len(rows)
                if len(widths) > 1: result['note'] = 'Rows have different numbers of columns; check quoting.'
    except Exception as e:
        return {**base, 'status': 'error', 'ok': False, 'problem': f'Could not open the file: {type(e).__name__}'}
    return {**base, 'status': 'ok' if result.get('ok') else 'error', **result}
