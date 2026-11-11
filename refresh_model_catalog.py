"""Regenerate backend/model_catalog_data.py from Hugging Face.

Run deliberately when adding or updating catalog entries:
    python refresh_model_catalog.py              # refresh pinned facts for every entry
    python refresh_model_catalog.py --discover   # also find new local models on Hugging Face first

Hand-picked entries live in backend/model_sources.py. --discover writes backend/model_sources_discovered.py:
chat-ready, single-file GGUF models from official publishers and well-known quantizers, one entry per model.

Each repository is pinned to its current commit. File sizes and SHA256 values come
from the LFS records at that commit. Context and attention facts come from the GGUF
header, read with a ranged request; no weights are downloaded.
"""
import json, pprint, struct, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.model_sources import SOURCES
try: from backend.model_sources_discovered import DISCOVERED
except ImportError: DISCOVERED = []

API = 'https://huggingface.co/api/models/'
SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
FORMATS = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i', 6: '<f', 7: '<?', 10: '<Q', 11: '<q', 12: '<d'}

def _hf_token():
    import os
    token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGING_FACE_HUB_TOKEN')
    if not token:
        try: token = (Path.home() / '.cache' / 'huggingface' / 'token').read_text().strip()
        except OSError: token = ''
    return token
HF_TOKEN = _hf_token()

def fetch(url, headers=None):
    """GET with patience: Hugging Face rate-limits bursts, so wait and retry instead of failing the whole refresh."""
    import time, urllib.error
    auth = {'Authorization': 'Bearer ' + HF_TOKEN} if HF_TOKEN and url.startswith('https://huggingface.co/') else {}
    for attempt in range(8):
        request = urllib.request.Request(url, headers={'User-Agent': 'Luminaria catalog refresh', **auth, **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=60) as response: return response.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 7: raise
            wait = int(e.headers.get('Retry-After') or 0) or min(300, 15 * 2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 7: raise
            wait = 10 * (attempt + 1)
        print(f'  waiting {wait}s for Hugging Face', file=sys.stderr); time.sleep(wait)

class Short(Exception): pass

class Reader:
    def __init__(self, data): self.data, self.at = data, 0
    def take(self, n):
        if self.at + n > len(self.data): raise Short()
        chunk = self.data[self.at:self.at + n]; self.at += n; return chunk
    def unpack(self, fmt): return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]
    def string(self): return self.take(self.unpack('<Q')).decode('utf-8', 'replace')
    def value(self, kind):
        if kind == 8: return self.string()
        if kind == 9:
            inner, count = self.unpack('<I'), self.unpack('<Q')
            if inner in SIZES:
                if count > 4096: self.take(SIZES[inner] * count); return None
                return [self.unpack(FORMATS[inner]) for _ in range(count)]
            items = [self.value(inner) for _ in range(count)]
            return items if count <= 4096 else None
        return self.unpack(FORMATS[kind])

def header(url):
    for size in (4 << 20, 16 << 20, 64 << 20):
        data = fetch(url, {'Range': f'bytes=0-{size - 1}'})
        reader = Reader(data)
        try:
            if reader.take(4) != b'GGUF': raise ValueError(f'{url} is not a GGUF file')
            reader.unpack('<I'); reader.unpack('<Q'); count = reader.unpack('<Q')
            meta = {}
            for _ in range(count):
                key = reader.string(); meta[key] = reader.value(reader.unpack('<I'))
            return meta
        except Short:
            continue
    raise ValueError(f'GGUF header of {url} is larger than 64 MB')

def facts(repo, revision, filename):
    return facts_from(header(f'https://huggingface.co/{repo}/resolve/{revision}/{filename}'))

def facts_from(meta):
    arch = meta['general.architecture']
    get = lambda name, default=None: meta.get(f'{arch}.{name}', default)
    heads = get('attention.head_count')
    heads = max(heads) if isinstance(heads, list) else heads
    kv = get('attention.head_count_kv', heads)
    kv = max(kv) if isinstance(kv, list) else kv
    width = get('embedding_length')
    key = get('attention.key_length', width // heads)
    value = get('attention.value_length', key)
    return {'architecture': arch, 'context': get('context_length'), 'layers': get('block_count'),
            'kv_heads': kv, 'key_length': key, 'value_length': value,
            'sliding_window': get('attention.sliding_window') or 0}

# --- Discovery -------------------------------------------------------------------------------------------
import re, urllib.parse
OFFICIAL = ['ggml-org', 'Qwen', 'google', 'mistralai', 'microsoft', 'ibm-granite', 'HuggingFaceTB', 'LiquidAI', 'nvidia',
            'allenai', 'openai', 'meta-llama', 'deepseek-ai', 'CohereLabs', 'tiiuae', 'zai-org', 'THUDM', 'moonshotai',
            'baidu', 'tencent', 'internlm', 'swiss-ai', 'ServiceNow-AI', 'NousResearch', 'arcee-ai']
QUANTIZERS = ['unsloth', 'bartowski', 'lmstudio-community']
QUANT_ORDER = ['Q4_K_M', 'Q5_K_M', 'Q6_K', 'Q8_0']
SKIP_WORDS = re.compile(r'embed|rerank|reward|draft|-base(?:-|$)|whisper|tts|speech|audio|asr|voxtral|ocr|-mtp|eagle|lora|clip|siglip|retriev|classif|guard|test|tiny|stories|debug|dummy|random|mlx|onnx|awq|gptq|exl2', re.I)
AUX_FILE = re.compile(r'mmproj|draft|mtp|eagle|vision|audio|projector|adapter', re.I)
MIN_BYTES = 250 * 1024 ** 2  # anything smaller is a toy or test model
MAX_BYTES = 100 * 1024 ** 3
MIN_DOWNLOADS = 2000
LIMIT = 400

def base_key(name):
    name = name.split('/')[-1].lower()
    name = re.sub(r'[-_.](gguf|i1|imat|imatrix)$', '', name)
    name = re.sub(r'-gguf$', '', name)
    return re.sub(r'[^a-z0-9]+', '', name)

def listing(author):
    query = urllib.parse.urlencode({'author': author, 'library': 'gguf', 'sort': 'downloads', 'direction': -1, 'limit': 150, 'full': 'false'})
    try: return json.loads(fetch('https://huggingface.co/api/models?' + query))
    except Exception as e: print('skip', author, e, file=sys.stderr); return []

def pick_quants(tree):
    files = {item['path']: item for item in tree if item.get('lfs') and item['path'].lower().endswith('.gguf') and '/' not in item['path']}
    out = []
    for label in QUANT_ORDER:
        match = [p for p in files if re.search(r'[-_.]' + label + r'\.gguf$', p, re.I) and not re.search(r'-\d{5}-of-\d{5}', p) and not AUX_FILE.search(p)]
        match.sort(key=lambda p: -files[p]['lfs']['size'])  # the model itself, not a helper file that shares the suffix
        if match and MIN_BYTES <= files[match[0]]['lfs']['size'] <= MAX_BYTES: out.append((label, match[0]))
    projectors = sorted((p for p in files if p.lower().startswith('mmproj')), key=lambda p: (0 if 'f16' in p.lower() and 'bf16' not in p.lower() else 1 if 'bf16' in p.lower() else 2, p))
    return out[:3], (projectors[0] if projectors else None)

def params(text):
    """'27B' -> 27e9, '128x2.4B' -> 307e9, '430M' -> 4.3e8; None when unknown."""
    m = re.search(r'(?:(\d+)x)?(\d+(?:\.\d+)?)\s*([BM])\b', text, re.I)
    if not m: return None
    n = float(m.group(2)) * (1e9 if m.group(3).upper() == 'B' else 1e6)
    return n * int(m.group(1)) if m.group(1) else n

def plausible(repo, size_label):
    """A repo named '...-31B-...' whose chosen file says 1.5B picked a helper file, not the model."""
    named = params(re.sub(r'A\d+(?:\.\d+)?B', '', repo.split('/')[-1], flags=re.I).replace('-', ' '))
    found = params(size_label)
    return not (named and found and found < named * 0.5)

def describe_model(name, repo, card, tags, vision):
    low = (name + ' ' + repo).lower()
    strengths, purpose = [], 'General chat model'
    if 'coder' in low or 'code' in low or 'devstral' in low: strengths += ['Coding', 'Tools']; purpose = 'Coding model'
    if vision or 'vl' in re.split(r'[^a-z]+', low) or 'vision' in low: strengths.append('Vision'); purpose = 'Vision and language model' if purpose == 'General chat model' else purpose
    if re.search(r'\br1\b|reason|think|qwq|magistral', low): strengths.append('Reasoning'); purpose = 'Reasoning model' if purpose == 'General chat model' else purpose
    for extra in ('Writing', 'Reasoning'):
        if len(strengths) < 2 and extra not in strengths: strengths.append(extra)
    return purpose, strengths

def discover():
    curated = {base_key(e['repo']) for e in SOURCES} | {base_key(e['name'].replace(' ', '-')) for e in SOURCES}
    seen, out = set(curated), []
    for author in OFFICIAL + QUANTIZERS:
        for item in listing(author):
            repo = item.get('id') or item.get('modelId') or ''
            tags = set(item.get('tags') or [])
            if item.get('downloads', 0) < MIN_DOWNLOADS or SKIP_WORDS.search(repo) or not ('gguf' in tags or 'gguf' in repo.lower()): continue
            if not ('conversational' in tags or item.get('pipeline_tag') in ('text-generation', 'image-text-to-text')): continue
            key = base_key(repo)
            if key in seen: continue
            try:
                info = json.loads(fetch(API + repo))
                if info.get('gated') or info.get('private') or info.get('disabled'): continue
                card = info.get('cardData') or {}
                bases = card.get('base_model') or []
                bases = [bases] if isinstance(bases, str) else bases
                keys = {key} | {base_key(b) for b in bases if isinstance(b, str)}
                if keys & seen: continue
                tree = json.loads(fetch(f"{API}{repo}/tree/{info['sha']}?recursive=1"))
                quants, projector_file = pick_quants(tree)
                if not quants: continue
                meta = header(f"https://huggingface.co/{repo}/resolve/{info['sha']}/{quants[0][1]}")
            except Exception as e:
                print('skip', repo, type(e).__name__, file=sys.stderr); continue
            arch = meta.get('general.architecture')
            if not arch or not meta.get(f'{arch}.context_length') or meta.get('general.type') in ('mmproj', 'adapter'): continue
            if not plausible(repo, str(meta.get('general.size_label') or '')): print('skip', repo, 'size mismatch', file=sys.stderr); continue
            try: model_facts = facts_from(meta)
            except (KeyError, TypeError, ZeroDivisionError): print('skip', repo, 'incomplete header', file=sys.stderr); continue
            from backend.model_catalog import display_name
            name = display_name(repo)  # the name inside a GGUF file is often a hash or a training path
            if not re.search(r'[A-Za-z]{2,}', name): name = repo.split('/')[0] + ' ' + name   # 'D1 3B' alone says nothing
            size_label = str(meta.get('general.size_label') or '')
            low = repo.lower()
            variant = 'abliterated' if ('abliterat' in low or 'uncensored' in low) else 'standard'
            purpose, strengths = describe_model(name, repo, card, tags, bool(projector_file))
            licence = card.get('license') or 'See the model card'
            if isinstance(licence, list): licence = ', '.join(map(str, licence))
            official = repo.split('/')[0] in OFFICIAL
            slug = re.sub(r'[^a-z0-9]+', '-', repo.split('/')[-1].lower().replace('-gguf', '')).strip('-')[:44]
            ident = slug; n = 2
            while any(e['id'] == ident for e in out): ident = f'{slug[:40]}-{n}'; n += 1
            out.append({'id': ident, 'name': name, 'variant': variant, 'parameters': size_label, 'purpose': purpose,
                        'description': f"{name}, published on Hugging Face by {repo.split('/')[0]}. Added automatically: read the model card for what it is best at and how it was trained.",
                        'strengths': strengths, 'repo': repo, 'license': str(licence)[:120] + (', per the model card' if licence != 'See the model card' else ''),
                        'provenance': f"{repo.split('/')[0]}, {'official GGUF' if official else 'GGUF quantization'}", 'quants': quants,
                        'caveat': 'Abliteration is a third-party weight edit intended to reduce refusals. It does not guarantee unrestricted answers.' if variant == 'abliterated' else '',
                        'projector': {'repo': repo, 'filename': projector_file, 'note': 'Vision projector from the same repository.'} if projector_file else None,
                        'family': name.split(' ')[0], 'active_parameters': '', 'discovered': True,
                        'pinned': {'revision': info['sha'], 'files': {f: [r['lfs']['size'], r['lfs']['oid']] for r in tree if r.get('lfs') for f in [r['path']] if f in [q[1] for q in quants] + ([projector_file] if projector_file else [])},
                                   'facts': model_facts}})
            seen |= keys
            print('added', repo, size_label, [q for q, _ in quants], file=sys.stderr)
            if len(out) >= LIMIT: break
        if len(out) >= LIMIT: break
    target = Path(__file__).resolve().parent / 'backend' / 'model_sources_discovered.py'
    target.write_text('"""Generated by refresh_model_catalog.py --discover. Do not edit by hand; curate in model_sources.py instead."""\n\n'
                      f'DISCOVERED = {pprint.pformat(out, width=140, sort_dicts=False)}\n', encoding='utf-8')
    print(f'Discovered {len(out)} models', file=sys.stderr)
    return out

def main():
    discovered = discover() if '--discover' in sys.argv else DISCOVERED
    repos, files = {}, {}
    wanted, optional = {}, set()
    for entry in SOURCES + discovered:
        if entry in discovered: optional.add(entry['repo'])
        wanted.setdefault(entry['repo'], set()).update(name for _, name in entry['quants'])
        if entry['projector']: wanted.setdefault(entry['projector']['repo'], set()).add(entry['projector']['filename'])
    for entry in discovered:
        pin = entry.get('pinned')
        if pin and all(f in pin['files'] for f in wanted[entry['repo']]):
            repos[entry['repo']] = {'revision': pin['revision'], **pin['facts']}
            for f in wanted[entry['repo']]: files[f"{entry['repo']}/{f}"] = tuple(pin['files'][f])
    for repo, names in sorted(wanted.items()):
        if repo in repos: continue
        try:
            info = json.loads(fetch(API + repo))
            if info.get('gated'): raise ValueError(f'{repo} is gated; Luminaria cannot download it without an account')
            revision = info['sha']
            tree = json.loads(fetch(f'{API}{repo}/tree/{revision}?recursive=1'))
            records = {item['path']: item for item in tree}
            found = {}
            for name in sorted(names):
                item = records.get(name)
                if not item or not item.get('lfs'): raise ValueError(f'{repo}/{name} is missing or not an LFS file')
                found[f'{repo}/{name}'] = (item['lfs']['size'], item['lfs']['oid'])
        except Exception:
            if repo in optional: print('skip', repo, file=sys.stderr); continue  # a discovered model that changed or vanished
            raise
        files.update(found); repos[repo] = {'revision': revision}
        print(repo, revision[:10], file=sys.stderr)
    for entry in SOURCES + discovered:
        repo = entry['repo']
        if repo in repos and 'context' not in repos[repo]:
            try: repos[repo].update(facts(repo, repos[repo]['revision'], entry['quants'][0][1]))
            except Exception:
                if repo in optional: repos.pop(repo); print('skip', repo, file=sys.stderr); continue
                raise
    target = Path(__file__).resolve().parent / 'backend' / 'model_catalog_data.py'
    target.write_text('"""Generated by refresh_model_catalog.py. Do not edit by hand."""\n\n'
                      f'REPOS = {pprint.pformat(repos, width=120, sort_dicts=True)}\n\n'
                      f'FILES = {pprint.pformat(files, width=160, sort_dicts=True)}\n', encoding='utf-8')
    print(f'Wrote {len(files)} files from {len(repos)} repositories', file=sys.stderr)

if __name__ == '__main__':
    main()
