"""Curated GGUF catalog. Sizes and SHA256 values match publisher LFS records at
pinned repository revisions.

Nothing here is downloaded until the user chooses a quantization.
Abliteration is labeled as a third-party weight edit, not a quality claim.
"""
import re
from .model_catalog_data import FILES, REPOS
from .model_sources import ABLITERATED, SOURCES
try: from .model_sources_discovered import DISCOVERED
except ImportError: DISCOVERED = []

BUDGET = 100 * 1024 ** 3
HEADROOM = 1024 ** 3
CONTEXT_LIMIT = 32768
# The runtime launches llama-server with -ctk q8_0 -ctv q8_0 and -ub 128.
CACHE_BYTES_PER_VALUE = 34 / 32
UBATCH = 128
# Every Nth layer uses full attention; the rest keep only the sliding window.
SLIDING_PATTERN = {'gemma3': 6, 'gpt-oss': 2}

def cache_bytes(facts, context):
    per_token = facts['kv_heads'] * (facts['key_length'] + facts['value_length']) * CACHE_BYTES_PER_VALUE
    pattern = SLIDING_PATTERN.get(facts['architecture']) if facts.get('sliding_window') else None
    if not pattern: return round(facts['layers'] * context * per_token)
    full = facts['layers'] // pattern
    window = min(context, -(-(facts['sliding_window'] + UBATCH) // 256) * 256)
    return round((full * context + (facts['layers'] - full) * window) * per_token)

def gb(n): return f'{n / 1024 ** 3:.1f} GB'

def slug(label):
    match = re.match(r'Q(\d)', label)
    return 'q' + match.group(1) if match else label.lower()

PUBLISHER_PREFIX = re.compile(r'^(google|qwen|mistralai|meta-llama|microsoft|nvidia|ibm-granite|deepseek-ai|tiiuae|allenai|thudm|zai-org|cohereforai|coherelabs|nousresearch|liquidai|huggingfacetb)_', re.I)

def display_name(repo):
    """Readable name from the repository, e.g. bartowski/google_gemma-3-12b-it-GGUF -> Gemma 3 12b it."""
    name = re.sub(r'[-_.]?gguf$', '', repo.split('/')[-1], flags=re.I)
    name = PUBLISHER_PREFIX.sub('', name)
    name = re.sub(r'[-_]+', ' ', name).strip()
    return (name[:1].upper() + name[1:])[:60] or repo

def size_from(repo, label):
    if re.search(r'\d', label or ''): return label
    m = re.search(r'(\d+(?:\.\d+)?)\s*([bm])\b', repo.split('/')[-1].replace('-', ' ').replace('_', ' '), re.I)
    return (m.group(1) + m.group(2).upper()) if m else (label or '')

def build():
    catalog = []
    taken, ids = {}, set()  # downloads are saved by file name, so a name may only ever mean one file
    def claim(name, digest):
        if taken.get(name, digest) != digest: return False
        taken[name] = digest; return True
    for item in SOURCES + DISCOVERED:
        discovered = bool(item.get('discovered'))
        # Discovered entries whose files could not be verified at the last refresh are left out.
        if item['repo'] not in REPOS or any(f"{item['repo']}/{f}" not in FILES for _, f in item['quants']): continue
        if discovered:
            if item['id'] in ids: continue
            kept = [(label, f) for label, f in item['quants'] if f not in taken and claim(f, FILES[f"{item['repo']}/{f}"][1])]  # a file already listed is the same model
            if not kept: continue
            item = {**item, 'name': display_name(item['repo']), 'parameters': size_from(item['repo'], item.get('parameters')),
                    'family': display_name(item['repo']).split(' ')[0], 'quants': kept, 'caveat': ABLITERATED if item['variant'] == 'abliterated' else item.get('caveat', '')}
            spec = item.get('projector')
            if spec and (f"{spec['repo']}/{spec['filename']}" not in FILES or not claim(spec['filename'], FILES[f"{spec['repo']}/{spec['filename']}"][1])):
                item = {**item, 'projector': None}
        else:
            for _, f in item['quants']: claim(f, FILES[f"{item['repo']}/{f}"][1])
            if item.get('projector'): claim(item['projector']['filename'], FILES[f"{item['projector']['repo']}/{item['projector']['filename']}"][1])
        ids.add(item['id'])
        facts = REPOS[item['repo']]
        supported = facts['context']
        configured = min(CONTEXT_LIMIT, supported)
        cache = cache_bytes(facts, configured)
        quants = []
        for label, filename in item['quants']:
            size, digest = FILES[f"{item['repo']}/{filename}"]
            quants.append({'id': f"{item['id']}-{slug(label)}", 'label': label, 'filename': filename, 'bytes': size, 'sha256': digest,
                           'memory': f'About {gb(size + cache)}: {gb(size)} of weights plus {gb(cache)} of context cache at {configured:,} tokens',
                           'memory_bytes': size + cache})
        projector = None
        if item['projector']:
            spec = item['projector']
            size, digest = FILES[f"{spec['repo']}/{spec['filename']}"]
            plain = re.sub(r'[^a-z0-9]+', '-', spec['filename'].lower().removesuffix('.gguf'))
            projector = {'id': (item['id'] + '-vision')[:60] if item.get('discovered') else plain, 'label': 'Vision projector', 'kind': 'projector', 'filename': spec['filename'],
                         'bytes': size, 'sha256': digest, 'repo': spec['repo'], 'revision': REPOS[spec['repo']]['revision'], 'note': spec['note']}
        catalog.append({'id': item['id'], 'name': item['name'], 'variant': item['variant'], 'family': item['family'],
                        'parameters': item['parameters'], 'active_parameters': item['active_parameters'],
                        'purpose': item['purpose'], 'description': item['description'], 'strengths': item['strengths'],
                        'context': configured, 'context_supported': supported, 'cache_bytes': cache,
                        'vision': bool(projector), 'projector': projector,
                        'repo': item['repo'], 'revision': facts['revision'], 'architecture': facts['architecture'],
                        'license': item['license'], 'provenance': item['provenance'],
                        'hardware': 'Estimate from file size and context cache. It is not a fit guarantee; benchmark on this PC to confirm.',
                        'caveat': item['caveat'], 'quants': quants})
    return catalog

CATALOG = build()

def validate():
    ids, files, projectors = set(), set(), {}
    if not CATALOG: raise ValueError('Model catalog is empty')
    for entry in CATALOG:
        if entry['variant'] not in ('standard','abliterated'): raise ValueError('Invalid catalog variant')
        if entry['variant'] == 'abliterated' and entry['caveat'] != ABLITERATED: raise ValueError('Abliterated entries need the caveat')
        if entry['id'] in ids or not re.fullmatch(r'[a-z0-9-]{1,60}', entry['id']): raise ValueError('Invalid catalog id')
        ids.add(entry['id'])
        if not re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+', entry['repo']): raise ValueError('Invalid catalog repository')
        if not re.fullmatch(r'[a-f0-9]{40}', entry['revision']): raise ValueError('Catalog repository is not pinned')
        projector = entry['projector']
        if projector:
            record = (projector['filename'], projector['sha256'], projector['repo'])
            if projectors.setdefault(projector['id'], record) != record: raise ValueError('Projector id reused for a different file')
        for item in entry['quants'] + ([projector] if projector and projector['filename'] not in files else []):
            if item['id'] in ids or not re.fullmatch(r'[a-z0-9-]{1,60}', item['id']): raise ValueError('Invalid quantization id')
            if item['filename'] in files or not re.fullmatch(r'[A-Za-z0-9._-]{1,180}\.gguf', item['filename']): raise ValueError('Invalid catalog filename')
            if item['bytes'] <= 0 or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']): raise ValueError('Invalid catalog file record')
            ids.add(item['id']); files.add(item['filename'])

validate()
