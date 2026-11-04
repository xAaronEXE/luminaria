"""Downloadable model library. Files land only in the app models folder."""
import hashlib, json, re, shutil, threading, time
from pathlib import Path
from urllib.parse import urlparse
import httpx
from . import models
from .config import CONFIG
from .model_catalog import BUDGET, CATALOG, HEADROOM

_lock = threading.Lock()
_jobs = {}
_queue = []
_cancels = {}
_worker = None
_generation = 0
_loaded = False

def reset():
    """Stop workers and forget in-memory jobs. Used by tests and process reuse."""
    global _worker, _generation, _loaded
    with _lock:
        _generation += 1
        for event in _cancels.values(): event.set()
        worker = _worker
        _queue.clear(); _jobs.clear(); _cancels.clear(); _worker = None
        _loaded = False
    if worker and worker.is_alive(): worker.join(timeout=2)

def models_folder():
    return models.BASE_DATA.parent / 'models'

def partial_file(quant_id):
    if not re.fullmatch(r'[a-z0-9-]{1,60}', quant_id): raise ValueError('Unknown model')
    return models_folder() / '.partial' / f'{quant_id}.part'

def state_path():
    return models.BASE_DATA / 'model-downloads.json'

def quant_by_id(quant_id):
    """Find a catalog file by id. Projectors are shared, so the first family that lists one owns the lookup."""
    for entry in CATALOG:
        for quant in entry['quants']:
            if quant['id'] == quant_id: return entry, quant
        if entry['projector'] and entry['projector']['id'] == quant_id: return entry, entry['projector']
    return None, None

def is_projector(item): return bool(item) and item.get('kind') == 'projector'

def catalog_files():
    seen = {}
    for entry in CATALOG:
        for item in entry['quants'] + ([entry['projector']] if entry['projector'] else []):
            seen.setdefault(item['filename'], item)
    return list(seen.values())

def _verified(path, item):
    sidecar = Path(str(path) + '.sha256')
    try: return path.is_file() and sidecar.is_file() and sidecar.read_text(encoding='utf-8').strip() == item['sha256']
    except OSError: return False

def projector_path(entry):
    """Path of this family's projector when it is downloaded and verified, else ''."""
    projector = entry.get('projector') if entry else None
    if not projector: return ''
    path = models_folder() / projector['filename']
    return str(path) if _verified(path, projector) else ''

def format_bytes(n):
    if n >= 1 << 30: return f'{n / (1 << 30):.1f} GB'
    if n >= 1 << 20: return f'{n / (1 << 20):.1f} MB'
    if n >= 1 << 10: return f'{round(n / (1 << 10))} KB'
    return f'{n} B'

def canonical_url(entry, quant):
    repo, revision = (quant['repo'], quant['revision']) if is_projector(quant) else (entry['repo'], entry['revision'])
    return f"https://huggingface.co/{repo}/resolve/{revision}/{quant['filename']}"

def host_allowed(url, origin):
    host = (urlparse(url).hostname or '').lower()
    origin_host = (urlparse(origin).hostname or '').lower()
    if origin_host in ('127.0.0.1', 'localhost'): return host in ('127.0.0.1', 'localhost')
    return host == 'huggingface.co' or host.endswith('.huggingface.co') or host.endswith('.hf.co')

def check_room(needed, already, free, spent, reserved_additional, reserved_full, budget=None):
    limit = BUDGET if budget is None else budget
    if needed <= 0: raise ValueError('This catalog entry has no file size. Nothing was downloaded.')
    additional = max(0, needed - already)
    if free < additional + HEADROOM + reserved_additional:
        raise ValueError(f'Not enough free space for this {format_bytes(needed)} download. Keep at least 1 GB free afterward. Nothing new was saved.')
    if spent + reserved_full + needed > limit:
        raise ValueError(f'This {format_bytes(needed)} download would pass the 100 GB additional-model budget. Remove a downloaded model or choose a smaller quantization. Nothing new was saved.')

def _digest(header):
    raw = re.sub(r'^W/', '', (header or '').strip()).strip('"').lower()
    if raw.startswith('sha256:'): raw = raw.split(':', 1)[1]
    return raw

def resolve(entry, quant):
    url = canonical_url(entry, quant)
    try:
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=True) as client:
            response = client.head(url, headers={'User-Agent': 'Luminaria'})
    except httpx.HTTPError as exc:
        raise ValueError('Could not reach the model publisher. Check your connection and try again. Nothing was downloaded.') from exc
    if response.status_code not in (200, 301, 302, 303, 307, 308):
        raise ValueError(f'Could not read the published file ({response.status_code}). Nothing was downloaded.')
    size = int(response.headers.get('x-linked-size') or response.headers.get('content-length') or 0)
    digest = _digest(response.headers.get('x-linked-etag') or response.headers.get('etag'))
    if not size or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('The publisher did not provide a size and SHA256. Nothing was downloaded.')
    if size != quant['bytes'] or digest != quant['sha256']:
        raise ValueError('The published file no longer matches the catalog. Nothing was downloaded.')
    return {'url': url, 'size': size, 'sha256': digest}

def _open_stream(url, headers):
    client = httpx.Client(timeout=httpx.Timeout(30, read=120), follow_redirects=False, trust_env=True)
    current = url
    try:
        for _ in range(6):
            response = client.send(client.build_request('GET', current, headers=headers), stream=True)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get('location'); response.close()
                if not location:
                    client.close(); raise ValueError('Download redirect was missing a destination. The partial file was kept.')
                current = str(httpx.URL(current).join(location))
                if not host_allowed(current, url):
                    client.close(); raise ValueError('Download redirected to an unexpected server. The partial file was kept.')
                continue
            if not host_allowed(str(response.url), url):
                response.close(); client.close(); raise ValueError('Download used an unexpected server. The partial file was kept.')
            return client, response
        client.close(); raise ValueError('Download had too many redirects. The partial file was kept.')
    except Exception:
        client.close(); raise

def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()

def transfer(url, partial, total, digest, cancel, progress):
    partial.parent.mkdir(parents=True, exist_ok=True)
    existing = partial.stat().st_size if partial.exists() else 0
    if existing == total and _sha256(partial) == digest:
        progress(total); return {'status': 'complete', 'received': total}
    if existing >= total:
        partial.unlink(); existing = 0
    headers = {'User-Agent': 'Luminaria'}
    if 0 < existing < total: headers['Range'] = f'bytes={existing}-'
    client, response = _open_stream(url, headers)
    received = existing
    try:
        if existing and response.status_code == 200:
            existing = 0; mode = 'wb'; received = 0
        elif existing and response.status_code == 206:
            mode = 'ab'
        elif response.status_code == 200:
            mode = 'wb'; received = 0
        elif response.status_code == 416 and existing:
            partial.unlink(); raise ValueError('The partial download could not be resumed. It was discarded. Start the download again.')
        else:
            raise ValueError(f'Download failed ({response.status_code}). The partial file was kept so you can retry.')
        with partial.open(mode) as handle:
            for chunk in response.iter_bytes(32 * 1024):
                if cancel.is_set():
                    return {'status': 'paused', 'received': received}
                handle.write(chunk); handle.flush(); received += len(chunk); progress(received)
    except httpx.HTTPError as exc:
        raise ValueError('The connection failed. The partial file was kept so you can resume.') from exc
    finally:
        response.close(); client.close()
    if cancel.is_set(): return {'status': 'paused', 'received': partial.stat().st_size if partial.exists() else received}
    if not partial.exists() or partial.stat().st_size != total or _sha256(partial) != digest:
        partial.unlink(missing_ok=True)
        raise ValueError('Checksum mismatch. The incomplete file was deleted. Start the download again.')
    return {'status': 'complete', 'received': total}

def _persist_locked():
    visible = []
    for job in _jobs.values():
        visible.append({k: job[k] for k in ('id', 'status', 'received', 'total', 'error', 'filename', 'url', 'sha256') if k in job})
    path = state_path(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'jobs': visible}, indent=2), encoding='utf-8')

def load_state():
    global _loaded
    with _lock:
        if _loaded: return
        _loaded = True
        path = state_path()
        if not path.exists(): return
        try: saved = json.loads(path.read_text(encoding='utf-8')).get('jobs', [])
        except (OSError, json.JSONDecodeError): return
        for job in saved:
            if job.get('id') in _jobs or not quant_by_id(job.get('id', ''))[1]: continue
            if job.get('status') in ('downloading', 'queued'):
                job['status'] = 'paused'
                job['error'] = 'Download stopped when the app closed. The partial file can resume.'
            _jobs[job['id']] = job

def _catalog_spent():
    folder = models_folder(); total = 0
    for item in catalog_files():
        path = folder / item['filename']
        if path.is_file():
            try: total += path.stat().st_size
            except OSError: pass
    return total

def _partial_bytes():
    folder = models_folder() / '.partial'
    if not folder.is_dir(): return 0
    return sum(path.stat().st_size for path in folder.glob('*.part') if path.is_file())

def _reservations(except_id=None):
    full = additional = 0
    for ident, job in _jobs.items():
        if ident == except_id or job.get('status') not in ('queued', 'downloading'): continue
        full += job.get('total') or 0
        additional += max(0, (job.get('total') or 0) - (job.get('received') or 0))
    return full, additional

def _public_job(job, position=None):
    return {'id': job['id'], 'status': job['status'], 'received': job.get('received') or 0,
            'total': job.get('total') or 0, 'error': job.get('error') or '', 'filename': job.get('filename') or '',
            'queue_position': position}

def jobs_view():
    load_state()
    with _lock:
        positions = {ident: index + 1 for index, ident in enumerate(_queue)}
        current = {ident: dict(job) for ident, job in _jobs.items()}
    folder = models_folder() / '.partial'
    if folder.is_dir():
        for part in folder.glob('*.part'):
            ident = part.name[:-5]
            if ident in current or not quant_by_id(ident)[1]: continue
            quant = quant_by_id(ident)[1]
            current[ident] = {'id': ident, 'status': 'paused', 'received': part.stat().st_size, 'total': quant['bytes'],
                              'error': 'Download stopped. The partial file is saved and can resume.', 'filename': quant['filename']}
    return [_public_job(job, positions.get(job['id'])) for job in current.values()]

def _same_file(path, target):
    try: return path.is_file() and path.resolve() == target.resolve()
    except OSError: return False

def _inside_models(path):
    try: path.resolve().relative_to(models_folder().resolve()); return True
    except (OSError, ValueError): return False

def _active(ident, path):
    configured = CONFIG.get('model_file') or ''
    try: same = bool(configured) and Path(configured).resolve() == path.resolve()
    except OSError: same = False
    return CONFIG.get('model') == ident or same

def _projector_active(path):
    configured = CONFIG.get('projector_file') or ''
    try: return bool(configured) and Path(configured).resolve() == path.resolve()
    except OSError: return False

def machine_profile():
    """This PC's memory picture for fit estimates. Never fails the library if detection does."""
    from . import fit
    try:
        from .hardware import cached_information
        info = cached_information()
    except Exception:
        info = {}
    return fit.machine(info, CONFIG.get('hardware_override'))

def fit_for(entry, quant, hw, benchmarks=()):
    """Fit rating for one catalog quantization on this PC, or a size-only guess for local files."""
    from . import fit
    from .model_catalog import cache_bytes
    from .model_catalog_data import REPOS
    facts = REPOS.get(entry.get('repo') or '')
    size = quant.get('bytes') or quant.get('bytes_on_disk')
    if not size: return None
    if facts:
        active, total = fit.parse_billions(entry.get('active_parameters')), fit.parse_billions(entry.get('parameters'))
        model = {'bytes': size, 'layers': facts['layers'], 'architecture': facts['architecture'],
                 'context_supported': facts['context'], 'active_ratio': active / total if active and total else None}
        cache = lambda context: cache_bytes(facts, context)
    else:
        # A file registered from disk: no architecture facts, so assume a typical dense model.
        model = {'bytes': size, 'layers': 40, 'architecture': '', 'context_supported': entry.get('context') or 32768, 'active_ratio': None}
        cache = lambda context: int(size * 0.012 * context / 4096)
    measured = next((b for b in benchmarks or () if isinstance(b, dict) and b.get('tps')), None)
    return fit.public(fit.estimate(model, hw, cache), measured)

def library(store):
    load_state()
    from .benchmark_store import evaluations, history
    from . import fit
    hw = machine_profile()
    folder = models_folder()
    registry = models.registry()
    downloads = {job['id']: job for job in jobs_view()}
    records = list(registry)
    entries = []
    matched = set()
    for entry in CATALOG:
        quants = []
        for quant in entry['quants']:
            path = folder / quant['filename']
            registered = next((item for item in registry if item.get('id') == quant['id'] or _same_file(Path(item.get('model_file', '')), path)), None)
            if registered: matched.add(registered['id'])
            installed = path.is_file()
            if installed and not any(_same_file(Path(item.get('model_file', '')), path) for item in records):
                records.append({'model_file': str(path)})
            verified = installed and _verified(path, quant)
            benchmarks = history(registered['id'], registered.get('benchmarks', [])) if registered else []
            quants.append({**quant, 'installed': installed, 'registered': bool(registered),
                           'registry_id': registered['id'] if registered else quant['id'],
                           'context':registered.get('context') if registered else entry['context'],
                           'verified': verified, 'bytes_on_disk': path.stat().st_size if installed else None,
                           'benchmarks': benchmarks, 'evaluations': evaluations(registered['id']) if registered else [], 'active': bool(registered) and _active(registered['id'], path),
                           'job': downloads.get(quant['id']), 'downloadable': True, 'managed': True})
            quants[-1]['fit'] = fit_for(entry, quant, hw, benchmarks)
            quants[-1]['launch'] = (registered or {}).get('launch') or {}
        projector = None
        if entry['projector']:
            spec = entry['projector']; path = folder / spec['filename']; installed = path.is_file()
            projector = {k: spec[k] for k in ('id', 'label', 'filename', 'bytes', 'note')} | {
                'installed': installed, 'verified': installed and _verified(path, spec), 'active': installed and _projector_active(path),
                'source': f"{spec['repo']}@{spec['revision'][:10]}", 'job': downloads.get(spec['id'])}
        entries.append({k: entry[k] for k in ('id', 'name', 'variant', 'family', 'parameters', 'active_parameters', 'purpose', 'description', 'strengths', 'context', 'context_supported', 'cache_bytes', 'vision', 'license', 'provenance', 'hardware', 'caveat', 'repo', 'architecture')} | {'discovered': bool(entry.get('discovered'))} |
                       {'key': 'catalog:' + entry['id'], 'local': False, 'quants': quants, 'projector': projector,
                        'source': f"{entry['repo']}@{entry['revision'][:10]}", 'source_url': f"https://huggingface.co/{entry['repo']}/tree/{entry['revision']}"})
    for item in registry:
        if item['id'] in matched: continue
        path = Path(item.get('model_file', ''))
        installed = path.is_file()
        benchmarks = history(item['id'], item.get('benchmarks', []))
        variant = item.get('variant') if item.get('variant') in ('standard', 'abliterated') else ('abliterated' if re.search(r'abliterat|huihui', (item.get('name', '') + ' ' + item.get('description', '')), re.I) else 'standard')
        entries.append({'id': item['id'], 'key': 'local:' + item['id'], 'name': item.get('name') or item['id'], 'variant': variant,
                        'parameters': item.get('parameters') or 'Not specified', 'purpose': 'Added from this PC',
                        'description': item.get('description') or 'Local GGUF registered on this PC.',
                        'strengths': item.get('strengths') or ['Local file'], 'context': item.get('context') or 0, 'context_supported': None, 'cache_bytes': None,
                        'vision': bool(item.get('projector_file')), 'projector': None, 'family': 'This PC', 'active_parameters': '', 'repo': '', 'architecture': '',
                        'license': item.get('license') or 'Not recorded', 'provenance': 'Registered from a file already on this PC', 'source': '', 'source_url': '',
                        'hardware': item.get('hardware') or 'Not recorded', 'caveat': '', 'local': True,
                        'quants': [{'id': item['id'], 'label': item.get('quantization') or 'Unknown', 'filename': path.name, 'bytes': path.stat().st_size if installed else None,
                                    'memory': 'Measured only by what this file uses on disk', 'installed': installed, 'registered': True, 'registry_id': item['id'],
                                    'verified': False, 'bytes_on_disk': path.stat().st_size if installed else None, 'benchmarks': benchmarks, 'evaluations': evaluations(item['id']),
                                    'active': _active(item['id'], path) if installed else CONFIG.get('model') == item['id'], 'job': None,
                                    'downloadable': False, 'managed': installed and _inside_models(path), 'sha256': ''}]})
        entries[-1]['quants'][0]['fit'] = fit_for(entries[-1], entries[-1]['quants'][0], hw, benchmarks)
        entries[-1]['quants'][0]['launch'] = item.get('launch') or {}
    storage = models.model_storage(records)
    storage['partial_bytes'] = _partial_bytes()
    spent = _catalog_spent()
    for entry in entries:
        rated = [q['fit'] for q in entry['quants'] if q.get('fit')]
        best = min(rated, key=lambda f: fit.ORDER.index(f['rating']), default=None)
        entry['fit'] = best and {k: best[k] for k in ('rating', 'label', 'meaning')}
        # Highlight the highest-quality quantization that still earns the best rating.
        top = [q for q in entry['quants'] if q.get('fit') and best and q['fit']['rating'] == best['rating']]
        if top: max(top, key=lambda q: q.get('bytes') or 0)['best_fit'] = True
    machine = {k: hw[k] for k in ('gpu', 'vram_total', 'vram_free', 'integrated', 'ram_total', 'source')}
    return {'active': CONFIG.get('model'), 'context': CONFIG.get('context'), 'storage': storage, 'machine': machine,
            'budget': {'limit': BUDGET, 'used': spent, 'remaining': max(0, BUDGET - spent)},
            'downloads': list(downloads.values()), 'models': entries}

def _start_worker():
    global _worker
    if _worker and _worker.is_alive(): return
    generation = _generation
    _worker = threading.Thread(target=_run, args=(generation,), name='model-download', daemon=True)
    _worker.start()

def enqueue(quant_id):
    load_state()
    entry, quant = quant_by_id(quant_id)
    if not quant: raise ValueError('That model is not in the download catalog.')
    final = models_folder() / quant['filename']
    if final.is_file() and final.stat().st_size == quant['bytes']:
        raise ValueError('This quantization is already downloaded.')
    with _lock:
        job = _jobs.get(quant_id)
        if job and job.get('status') in ('queued', 'downloading'): return _public_job(job)
    meta = resolve(entry, quant)
    partial = partial_file(quant_id)
    already = partial.stat().st_size if partial.exists() else 0
    free = shutil.disk_usage(models_folder() if models_folder().exists() else models.BASE_DATA).free
    with _lock:
        reserved_full, reserved_additional = _reservations(quant_id)
        check_room(quant['bytes'], already, free, _catalog_spent(), reserved_additional, reserved_full)
        _jobs[quant_id] = {'id': quant_id, 'status': 'queued', 'received': already, 'total': quant['bytes'], 'error': '',
                           'filename': quant['filename'], 'url': meta['url'], 'sha256': meta['sha256']}
        if quant_id not in _queue: _queue.append(quant_id)
        _persist_locked(); _start_worker()
        return _public_job(_jobs[quant_id], _queue.index(quant_id) + 1)

def cancel(quant_id):
    load_state()
    with _lock:
        job = _jobs.get(quant_id)
        if job and job.get('status') == 'cancelling': return _public_job(job)
        if not job or job.get('status') not in ('queued', 'downloading'):
            raise ValueError('There is no active download to cancel.')
        if job['status'] == 'queued':
            if quant_id in _queue: _queue.remove(quant_id)
            job['status'] = 'paused'
            job['error'] = 'Download stopped before it started. You can resume it.'
            _persist_locked(); return _public_job(job)
        job['status'] = 'cancelling'
        job['error'] = 'Stopping the download. The partial file will be kept.'
        event = _cancels.get(quant_id)
        _persist_locked()
    if event: event.set()
    return {'id': quant_id, 'status': 'cancelling'}

def discard(quant_id):
    load_state()
    with _lock:
        job = _jobs.get(quant_id)
        if job and job.get('status') in ('queued', 'downloading'):
            raise ValueError('Cancel the download before discarding its partial file.')
        _jobs.pop(quant_id, None); _persist_locked()
    partial_file(quant_id).unlink(missing_ok=True)
    return {'discarded': True}

def _progress(quant_id, received):
    with _lock:
        job = _jobs.get(quant_id)
        if not job: return
        job['received'] = received
        now = time.monotonic()
        if now - job.get('_saved', 0) > 0.5:
            job['_saved'] = now; _persist_locked()

def _register(entry, quant, path):
    registry = models.registry()
    previous = next((item for item in registry if item.get('id') == quant['id']), None)
    record = {'id': quant['id'], 'name': f"{entry['name']} · {quant['label']}"[:120], 'description': entry['description'][:1000],
              'model_file': str(path), 'projector_file': projector_path(entry), 'context': entry['context'], 'quantization': quant['label'],
              'strengths': entry['strengths'], 'variant': entry['variant'], 'parameters': entry['parameters'], 'purpose': entry['purpose'],
              'license': entry['license'], 'hardware': entry['hardware'], 'provenance': entry['provenance'], 'catalog_id': entry['id'],
              'sha256': quant['sha256'], 'benchmarks': previous.get('benchmarks', []) if previous else [],
              'benchmark_note': 'Not benchmarked on this machine.'}
    registry = [item for item in registry if item.get('id') != quant['id'] and not _same_file(Path(item.get('model_file', '')), path)]
    registry.append(record); models.save(registry); return record

def _families_using(projector_id):
    return [entry for entry in CATALOG if entry['projector'] and entry['projector']['id'] == projector_id]

def _attach_projector(projector_id, value):
    """Point registered models of every family sharing this projector at it, or detach it."""
    quant_ids = {quant['id'] for entry in _families_using(projector_id) for quant in entry['quants']}
    registry = models.registry(); changed = False
    for item in registry:
        if item.get('id') in quant_ids and item.get('projector_file', '') != value:
            item['projector_file'] = value; changed = True
    if changed: models.save(registry)

def _finish(entry, quant, partial):
    folder = models_folder(); folder.mkdir(parents=True, exist_ok=True)
    final = folder / quant['filename']
    partial.replace(final)
    Path(str(final) + '.sha256').write_text(quant['sha256'] + '\n', encoding='utf-8')
    if is_projector(quant): _attach_projector(quant['id'], str(final))
    else: _register(entry, quant, final)

def _run(generation):
    global _worker
    while True:
        with _lock:
            if generation != _generation or not _queue:
                if _worker and generation == _generation: _worker = None
                return
            quant_id = _queue.pop(0)
            job = _jobs[quant_id]
            job['status'] = 'downloading'; job['error'] = ''
            cancel_event = threading.Event(); _cancels[quant_id] = cancel_event
            url, total, digest = job['url'], job['total'], job['sha256']
            _persist_locked()
        entry, quant = quant_by_id(quant_id)
        partial = partial_file(quant_id)
        try:
            already = partial.stat().st_size if partial.exists() else 0
            probe = partial.parent if partial.parent.exists() else models.BASE_DATA
            free = shutil.disk_usage(probe).free
            with _lock: reserved_full, reserved_additional = _reservations(quant_id)
            check_room(total, already, free, _catalog_spent(), reserved_additional, reserved_full)
            result = transfer(url, partial, total, digest, cancel_event, lambda amount: _progress(quant_id, amount))
            if generation != _generation: return
            if result['status'] == 'complete': _finish(entry, quant, partial)
        except Exception as exc:
            if generation != _generation: return
            message = str(exc) if isinstance(exc, ValueError) else 'The download could not be saved. The partial file was kept so you can retry.'
            with _lock:
                if quant_id in _jobs:
                    _jobs[quant_id]['status'] = 'error'; _jobs[quant_id]['error'] = message
                    _cancels.pop(quant_id, None); _persist_locked()
            continue
        if generation != _generation: return
        with _lock:
            _cancels.pop(quant_id, None)
            if result['status'] == 'complete': _jobs.pop(quant_id, None)
            elif quant_id in _jobs:
                _jobs[quant_id]['status'] = 'paused'; _jobs[quant_id]['received'] = result['received']
                _jobs[quant_id]['error'] = 'Download stopped. The partial file is saved and can resume.'
            _persist_locked()

def prepare(ident):
    entry, quant = quant_by_id(ident)
    if is_projector(quant): raise ValueError('A vision projector is used together with a model. Choose a quantization instead.')
    if quant:
        path = models_folder() / quant['filename']
        if not path.is_file(): raise ValueError('Download this quantization before using it.')
        if path.stat().st_size != quant['bytes']: raise ValueError('The file size does not match the catalog. It was not selected.')
        sidecar = Path(str(path) + '.sha256')
        if sidecar.is_file() and sidecar.read_text(encoding='utf-8').strip() != quant['sha256']:
            raise ValueError('The saved checksum does not match the catalog. It was not selected.')
        record = _register(entry, quant, path)
        return {'id': quant['id'], 'projector_file': record['projector_file']}
    item = next((item for item in models.registry() if item['id'] == ident), None)
    if not item or not Path(item['model_file']).is_file(): raise ValueError('Model file is unavailable')
    return {'id': ident, 'projector_file': item.get('projector_file', '')}

def _remove_projector(projector):
    path = models_folder() / projector['filename']
    if path.is_file() and _projector_active(path):
        raise ValueError('The active model is using this vision projector. Select another model before removing it.')
    deleted = path.is_file()
    if deleted: path.unlink()
    Path(str(path) + '.sha256').unlink(missing_ok=True)
    partial_file(projector['id']).unlink(missing_ok=True)
    with _lock:
        _jobs.pop(projector['id'], None)
        if projector['id'] in _queue: _queue.remove(projector['id'])
        _persist_locked()
    _attach_projector(projector['id'], '')
    return {'deleted': deleted, 'unregistered': False, 'message': 'Vision projector uninstalled.' if deleted else 'No projector file was found.'}

def remove(ident, confirm):
    load_state()
    if confirm is not True: raise ValueError('Confirm removal before deleting a model file.')
    entry, quant = quant_by_id(ident)
    if is_projector(quant): return _remove_projector(quant)
    registry = models.registry()
    if quant:
        path = models_folder() / quant['filename']
        registered = next((item for item in registry if item.get('id') == quant['id'] or _same_file(Path(item.get('model_file', '')), path)), None)
        active_id = registered['id'] if registered else quant['id']
    else:
        registered = next((item for item in registry if item['id'] == ident), None)
        if not registered: raise ValueError('Model not found')
        path = Path(registered.get('model_file', ''))
        active_id = registered['id']
    was_active = bool(path and _active(active_id, path if path else Path()))
    if was_active: _release_active()
    deleted = False
    if path and path.is_file():
        if not _inside_models(path):
            models.save([item for item in registry if item.get('id') != active_id])
            return {'deleted': False, 'unregistered': True, 'message': 'Removed from the library. The file is outside the models folder and was left in place.'}
        path.unlink(); deleted = True
        Path(str(path) + '.sha256').unlink(missing_ok=True)
    if quant: partial_file(quant['id']).unlink(missing_ok=True)
    with _lock:
        _jobs.pop(ident, None)
        if ident in _queue: _queue.remove(ident)
        _persist_locked()
    keep = []
    for item in registry:
        if item.get('id') == active_id: continue
        if path and _same_file(Path(item.get('model_file', '')), path): continue
        keep.append(item)
    models.save(keep)
    switched = _choose_replacement(keep) if was_active else None
    note = f' Switched to {switched}.' if switched else (' No model is installed now. Download one to keep chatting.' if was_active else '')
    return {'deleted': deleted, 'unregistered': True, 'switched': switched,
            'message': ('Model uninstalled.' if deleted else 'Model removed from the library.') + note}

def _release_active():
    """Stop the model server and clear the selection, so the active model's file can be deleted (Windows keeps open files locked)."""
    from . import runtime
    runtime.stop_owned()
    from .config import save_config
    save_config({'model': '', 'model_file': '', 'projector_file': ''})

def _choose_replacement(registry):
    for item in registry:
        if Path(item.get('model_file', '')).is_file():
            try: models.select(item['id']); return item.get('name') or item['id']
            except ValueError: continue
    return None

def remove_all(confirm):
    """Delete every model downloaded into the models folder and cancel downloads. Models you added from elsewhere stay on disk."""
    load_state()
    if confirm is not True: raise ValueError('Confirm removal before deleting model files.')
    with _lock: active = [k for k, j in _jobs.items() if j.get('status') in ('queued', 'downloading')]
    for k in active:
        try: cancel(k)
        except ValueError: pass
    for _ in range(40):  # give a running download a moment to let go of its file
        with _lock:
            if not any(j.get('status') in ('downloading', 'cancelling') for j in _jobs.values()): break
        time.sleep(.25)
    _release_active()
    folder = models_folder(); removed = 0; freed = 0
    if folder.is_dir():
        for f in folder.iterdir():
            if f.is_file() and (f.suffix.lower() == '.gguf' or f.name.endswith('.gguf.sha256')):
                try: freed += f.stat().st_size; f.unlink(); removed += f.suffix.lower() == '.gguf'
                except OSError: pass
        partials = folder / '.partial'
        if partials.is_dir():
            for f in partials.iterdir():
                try: freed += f.stat().st_size; f.unlink()
                except OSError: pass
    keep = [item for item in models.registry() if not _inside_models(Path(item.get('model_file', '')))]
    models.save(keep)
    with _lock:
        _jobs.clear(); _persist_locked()
    return {'removed': removed, 'freed': freed, 'message': f'Removed {removed} model{"s" if removed != 1 else ""} and freed {format_bytes(freed)}.'}

GOOD_FITS = ('recommended', 'good', 'slow')

def remove_selected(ids, confirm):
    """Uninstall several models. Each id is a quant or registry id; one that fails does not stop the rest."""
    if confirm is not True: raise ValueError('Confirm removal before deleting model files.')
    removed, failed = 0, []
    for ident in dict.fromkeys(str(i) for i in ids or []):
        try: remove(ident, True); removed += 1
        except (ValueError, OSError) as error: failed.append(f'{ident}: {error}')
    message = f'Removed {removed} model{"s" if removed != 1 else ""}.' + (f' {len(failed)} could not be removed.' if failed else '')
    return {'removed': removed, 'failed': failed, 'message': message}

def download_all(store, confirm=False, keys=None):
    """Queue the best-fit size of every model that runs on this PC, or only of the chosen models (keys).
    Chosen models may also be ones that only just fit; models too large for this PC are never queued.
    Without confirm, only reports what would happen."""
    lib = library(store)
    chosen = set(keys) if keys else None
    allowed = GOOD_FITS + ('unstable', 'unknown') if chosen else GOOD_FITS
    picks = []
    for entry in lib['models']:
        if chosen is not None and entry.get('key') not in chosen: continue
        quant = next((q for q in entry.get('quants', []) if q.get('best_fit')), None)
        if not quant or quant.get('installed') or is_projector(quant) or not quant.get('downloadable', True): continue
        if (quant.get('fit') or {}).get('rating', 'unknown') not in allowed: continue
        if (quant.get('job') or {}).get('status') in ('queued', 'downloading'): continue
        picks.append((allowed.index((quant.get('fit') or {}).get('rating', 'unknown')), quant.get('bytes') or 0, entry.get('name', ''), quant))
    picks.sort(key=lambda p: (p[0], p[1]))
    free = shutil.disk_usage(models_folder() if models_folder().exists() else models.BASE_DATA).free
    room = min(lib['budget']['remaining'], max(0, free - 1024**3))
    fits, skipped, total = [], [], 0
    for _, size, name, quant in picks:
        if total + size <= room: fits.append(quant); total += size
        else: skipped.append(name)
    summary = {'count': len(fits), 'bytes': total, 'skipped': len(skipped), 'available': room, 'total_models': len(picks)}
    if not confirm: return summary
    queued = 0
    for quant in fits:
        try: enqueue(quant['id']); queued += 1
        except ValueError: pass
    return {**summary, 'queued': queued}
