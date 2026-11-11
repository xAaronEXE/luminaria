"""File changes a task makes: written safely, recorded, and undoable where that is honestly possible.

Only files changed through Luminaria's file tools can be undone. Anything a command or script did (installs,
network requests, other programs' data) is listed as not undoable, never silently promised.
A file is restored only if it is still exactly as the task left it; if something else changed it since, it is
reported as a conflict and left alone.
"""
import hashlib, os, shutil, time, uuid
from pathlib import Path

SNAPSHOT_LIMIT = 50 * 1024 * 1024      # larger files are not copied; changing one cannot be undone
NOT_UNDOABLE = {'run_command': 'A command it ran', 'run_code': 'A script it ran', 'remember': 'A saved memory',
                'create_schedule': 'A scheduled task', 'create_file_workflow': 'A file workflow'}


def file_hash(path):
    path = Path(path)
    if not path.is_file(): return None
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''): digest.update(block)
    return digest.hexdigest()


def atomic_write(path, text):
    """Write the whole file or nothing: a crash or power cut never leaves a half-written file.
    Antivirus and sync tools can hold a file for a moment on Windows, so a refused replace is retried."""
    path = Path(path)
    temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex[:8]}.luminaria-tmp')
    try:
        with temp.open('w', encoding='utf-8', newline='') as handle:
            handle.write(text); handle.flush(); os.fsync(handle.fileno())
        for attempt in range(5):
            try: os.replace(temp, path); return
            except PermissionError:
                if attempt == 4: raise
                time.sleep(0.15 * (attempt + 1))
    finally:
        if temp.exists():
            try: temp.unlink()
            except OSError: pass


def setup(store):
    store.execute('CREATE TABLE IF NOT EXISTS changes(id TEXT PRIMARY KEY,chat TEXT,run TEXT,step TEXT,path TEXT,existed INTEGER,'
                  'before_hash TEXT,after_hash TEXT,snapshot TEXT,undone INTEGER DEFAULT 0,created REAL)')


def before(store, data, run, path):
    """Call before a file tool changes or deletes `path`. Keeps a copy the first time this run touches the file."""
    setup(store); path = Path(path)
    if store.rows('SELECT id FROM changes WHERE run=? AND path=? AND undone=0', (run['id'], str(path))): return
    existed = path.is_file(); snapshot = None
    if existed and path.stat().st_size <= SNAPSHOT_LIMIT:
        folder = Path(data) / 'snapshots' / run['id']; folder.mkdir(parents=True, exist_ok=True)
        snapshot = folder / (uuid.uuid4().hex + '-' + path.name)
        shutil.copy2(path, snapshot)
    store.execute('INSERT INTO changes(id,chat,run,step,path,existed,before_hash,after_hash,snapshot,undone,created) VALUES(?,?,?,?,?,?,?,?,?,0,?)',
                  (uuid.uuid4().hex, run['chat'], run['id'], run.get('step_id'), str(path), int(existed), file_hash(path) if existed else None, None,
                   str(snapshot) if snapshot else None, time.time()))


def after(store, run, path):
    """Call after the change, so undo can tell whether the file is still as the task left it."""
    store.execute('UPDATE changes SET after_hash=? WHERE run=? AND path=? AND undone=0', (file_hash(path), run['id'], str(Path(path))))


def _rows(store, chat, run=None):
    setup(store)
    if run: return store.rows('SELECT * FROM changes WHERE chat=? AND run=? AND undone=0 ORDER BY created DESC', (chat, run))
    return store.rows('SELECT * FROM changes WHERE chat=? AND undone=0 ORDER BY created DESC', (chat,))


def _state(row):
    """What undo would do with this file right now."""
    path = Path(row['path']); current = file_hash(path)
    if current != row['after_hash']: return 'conflict'            # changed (or removed, or recreated) since the task
    if row['existed'] and not row['snapshot']: return 'too_large'
    if row['existed'] and not Path(row['snapshot']).is_file(): return 'snapshot_missing'
    return 'restore' if row['existed'] else 'remove'


def summary(store, chat, run=None):
    """What the last task (or one run) changed, and what can and cannot be put back."""
    rows = _rows(store, chat, run)
    if not run and rows: rows = [r for r in rows if r['run'] == rows[0]['run']]
    run_id = rows[0]['run'] if rows else run
    files = [{'path': r['path'], 'action': 'created' if not r['existed'] else 'deleted' if r['after_hash'] is None else 'changed', 'undo': _state(r)} for r in rows]
    other = []
    if run_id:
        seen = {}
        for a in store.rows("SELECT name FROM actions WHERE chat=? AND status='done' AND created>=(SELECT MIN(created) FROM changes WHERE run=?)", (chat, run_id)):
            label = NOT_UNDOABLE.get(a['name']) or ('An action in another app' if '__' in a['name'] else None)
            if label: seen[label] = seen.get(label, 0) + 1
        other = [{'what': k, 'count': v} for k, v in seen.items()]
    return {'run': run_id, 'files': files, 'cannot_undo': other, 'undoable': sum(f['undo'] in ('restore', 'remove') for f in files)}


def undo(store, data, chat, run=None):
    """Put back every file the task changed that is still exactly as the task left it."""
    rows = _rows(store, chat, run)
    if not run and rows: rows = [r for r in rows if r['run'] == rows[0]['run']]
    restored, conflicts, skipped = [], [], []
    for row in rows:
        path = Path(row['path']); state = _state(row)
        if state == 'conflict': conflicts.append(row['path']); continue
        if state in ('too_large', 'snapshot_missing'): skipped.append(row['path']); continue
        try:
            if state == 'restore':
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex[:8]}.luminaria-tmp')
                shutil.copy2(row['snapshot'], temp); os.replace(temp, path)
            else:
                # A file the task created is moved aside, not destroyed, in case it was wanted after all.
                trash = Path(data) / 'undo-trash' / row['run']; trash.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(trash / (uuid.uuid4().hex[:8] + '-' + path.name)))
            store.execute('UPDATE changes SET undone=1 WHERE id=?', (row['id'],)); restored.append(row['path'])
        except OSError as error:
            skipped.append(f"{row['path']} ({error.strerror or type(error).__name__})")
    parts = [f'Put back {len(restored)} file{"s" if len(restored) != 1 else ""}.' if restored else 'No files were put back.']
    if conflicts: parts.append(f'{len(conflicts)} left alone because something changed them after the task.')
    if skipped: parts.append(f'{len(skipped)} could not be put back.')
    return {'restored': restored, 'conflicts': conflicts, 'skipped': skipped, 'message': ' '.join(parts)}
