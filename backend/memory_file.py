"""Memory as plain Markdown, like CLAUDE.md.

MEMORY.md (in Luminaria's data folder) holds what to remember about the user across every task.
LUMINARIA.md (optional, in the root of a working folder) holds notes about that project.

The file on disk is the real copy. A mirror row in the database lets the existing cloud sync carry it to
other devices unchanged. Both files are loaded word for word near the top of each request and only change
when edited, so the model's prompt cache stays valid between messages.
"""
import re, time
from pathlib import Path
from .config import DATA, CONFIG

PATH = DATA / 'MEMORY.md'
PROJECT_NAME = 'LUMINARIA.md'
ROW = 'memory-md'                 # database mirror used only by cloud sync
MAX_FILE = 100_000                # characters
PROMPT_BUDGET = 8_000             # about 2,000 tokens of memory in every request
PROJECT_BUDGET = 6_000
TEMPLATE = ('# Memory\n\n'
            'What Luminaria remembers across your tasks. Plain Markdown: edit, reorder or delete anything.\n\n'
            '## About me\n\n## Preferences\n\n## Notes\n')

def _write_disk(text):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix('.tmp'); tmp.write_text(text, encoding='utf-8'); tmp.replace(PATH)

def migrate(store):
    """First run: turn saved memory entries into MEMORY.md, then retire the old entries."""
    old = [m for m in store.memory() if m['id'] != ROW]
    text = TEMPLATE
    if old:
        lines = '\n'.join(f"- **{m['title'].strip()}:** {' '.join(m['content'].split())}" for m in sorted(old, key=lambda m: m['updated']))
        text = text.rstrip('\n') + '\n' + lines + '\n'
    write(store, text)
    for m in old: store.execute('DELETE FROM memories WHERE id=?', (m['id'],))
    return text

def read(store):
    if PATH.is_file():
        try: return PATH.read_text('utf-8')
        except OSError: pass
    mirror = next((m for m in store.memory() if m['id'] == ROW), None)
    if mirror:  # arrived through cloud sync before the file existed on this device
        _write_disk(mirror['content']); return mirror['content']
    return migrate(store)

def write(store, text):
    if not isinstance(text, str): raise ValueError('Memory must be text')
    text = text.replace('\r\n', '\n')
    if len(text) > MAX_FILE: raise ValueError(f'Memory is limited to {MAX_FILE:,} characters. Remove or shorten some notes.')
    _write_disk(text)
    store.save_memory('MEMORY.md', text, source='file', id=ROW)
    return text

def from_sync(content):
    """Cloud sync brought a newer MEMORY.md from another device."""
    if isinstance(content, str) and len(content) <= MAX_FILE: _write_disk(content)

def entries(text):
    return [l for l in text.splitlines() if re.match(r'\s*[-*]\s+\S', l)]

def remember(store, title, content):
    """Add one line under '## Notes' (created if missing)."""
    title = ' '.join(str(title or '').split())[:120]; content = ' '.join(str(content or '').split())
    if not content: raise ValueError('Nothing to remember')
    if len(content) > 2000: raise ValueError('Keep each memory under 2,000 characters')
    line = f"- **{title}:** {content} _({time.strftime('%Y-%m-%d')})_" if title else f"- {content} _({time.strftime('%Y-%m-%d')})_"
    lines = read(store).split('\n')
    head = next((i for i, l in enumerate(lines) if l.strip().lower() == '## notes'), None)
    if head is None:
        while lines and not lines[-1].strip(): lines.pop()
        lines += ['', '## Notes', line, '']
    else:
        end = head + 1
        while end < len(lines) and not lines[end].startswith('## '): end += 1
        at = end
        while at > head + 1 and not lines[at - 1].strip(): at -= 1   # keep the blank line before the next heading
        lines.insert(at, line)
    text = '\n'.join(lines)
    write(store, text)
    return {'saved': line, 'file': 'MEMORY.md'}

def search(store, query):
    q = query.lower()
    return [l.strip() for l in read(store).splitlines() if q in l.lower()][:30]

def _budget(text, limit, where):
    text = text.strip()
    if len(text) <= limit: return text
    cut = text.rfind('\n', 0, limit)
    return text[:cut if cut > limit // 2 else limit] + f'\n[{where} continues; use memory_search to find the rest.]'

def project_path():
    try: return Path(CONFIG['workspace']).resolve() / PROJECT_NAME
    except (OSError, KeyError): return None

def project_text():
    p = project_path()
    try:
        if p and p.is_file() and p.stat().st_size <= 400_000: return p.read_text('utf-8', errors='replace')
    except OSError: pass
    return ''

def prompt(store):
    """The memory section of the system prompt: stable text that changes only when a file is edited."""
    parts = []
    mine = read(store)
    if entries(mine) or len(mine.strip()) > len(TEMPLATE.strip()):
        parts.append('About the user (MEMORY.md; follow it, and add to it with remember only when asked or for a lasting preference):\n'
                     + _budget(mine, PROMPT_BUDGET, 'MEMORY.md'))
    project = project_text()
    if project.strip():
        parts.append(f'Project notes for this working folder ({PROJECT_NAME}; keep it current with edit_file when you learn lasting facts about the project):\n'
                     + _budget(project, PROJECT_BUDGET, PROJECT_NAME))
    return '\n\n'.join(parts)
