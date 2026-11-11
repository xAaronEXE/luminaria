"""End-to-end encrypted sync storage.

Everything synced is encrypted on this PC with a key only the user's own devices hold. The place it is stored
(a sync folder such as OneDrive, or a sync service) sees only scrambled records and files, never their content,
names or paths. Another device joins by entering the same sync key; the key is also the recovery key.

Two places to store the encrypted data:
  FolderStore   a folder the user already syncs (OneDrive, Google Drive, Dropbox, a network share)
  ServiceStore  a Luminaria sync service (the user's own Cloudflare Worker)
Both expose the same small interface, and EncryptedStore adds encryption on top.
"""
import base64, hashlib, hmac, json, os, re, secrets, time, uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_GROUPS = 14          # 32 random bytes + 2 check bytes = 55 base32 characters, shown in groups of four
RECORD = re.compile(r'^(chat|file|memory|settings|profile):([A-Za-z0-9_.-]{1,128})$')


class Conflict(Exception):
    """Another device changed this record first."""


# ---- the sync key ----

def new_key():
    return secrets.token_bytes(32)


def format_key(key):
    """The key as the user sees and types it: groups of four letters and digits, with a built-in check."""
    raw = key + hashlib.sha256(key).digest()[:2]
    text = base64.b32encode(raw).decode().rstrip('=')
    return '-'.join(text[i:i + 4] for i in range(0, len(text), 4))


def parse_key(text):
    """Read a typed sync key. Spaces, dashes and case don't matter; O and 0, I and 1 are forgiven."""
    clean = re.sub(r'[\s-]', '', str(text or '')).upper().replace('0', 'O').replace('1', 'I').replace('8', 'B')
    if not re.fullmatch(r'[A-Z2-7]{50,56}', clean): raise ValueError('That is not a sync key. It looks like ABCD-EFGH-… with 14 groups.')
    try: raw = base64.b32decode(clean + '=' * (-len(clean) % 8))
    except Exception: raise ValueError('That sync key could not be read. Check it for typos.') from None
    key, check = raw[:32], raw[32:34]
    if len(key) != 32 or hashlib.sha256(key).digest()[:2] != check: raise ValueError('That sync key has a typo in it. Check each group.')
    return key


def key_id(key):
    """A public name for the key, the same on every device that has it; reveals nothing about the key."""
    return hmac.new(key, b'luminaria-sync-id', hashlib.sha256).hexdigest()[:20]


def _subkey(key, purpose):
    return hmac.new(key, b'luminaria-sync:' + purpose.encode(), hashlib.sha256).digest()


def encrypt(key, data, context):
    """AES-256-GCM. `context` (the record name) is bound to the ciphertext, so a record can't be swapped for another."""
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(_subkey(key, 'data')).encrypt(nonce, data, context.encode())


def decrypt(key, blob, context):
    try: return AESGCM(_subkey(key, 'data')).decrypt(blob[:12], blob[12:], context.encode())
    except Exception: raise ValueError('Synced data could not be decrypted. Is this device using the same sync key?') from None


def remote_name(key, local_key):
    """The record name the storage sees. Chat titles, file names and paths are never visible to it."""
    kind, _, ident = local_key.partition(':')
    return kind + ':' + hmac.new(_subkey(key, 'names'), local_key.encode(), hashlib.sha256).hexdigest()[:40]


# ---- where the encrypted data lives ----

class FolderStore:
    """Encrypted records and files in an ordinary folder that another program keeps in sync (OneDrive, Google
    Drive, Dropbox, a network share). One file per record, so sync programs never have to merge inside a file.
    Every write goes to a temporary name and is renamed into place, so a half-copied file is never read."""
    def __init__(self, folder, space):
        self.root = Path(folder) / 'Luminaria Sync' / space
        (self.root / 'records').mkdir(parents=True, exist_ok=True); (self.root / 'files').mkdir(parents=True, exist_ok=True)
        readme = self.root.parent / 'README.txt'
        if not readme.exists():
            readme.write_text('Luminaria keeps its end-to-end encrypted sync data here. It cannot be read without your sync key.\n'
                              'Do not edit these files. Deleting this folder deletes your synced copy, not the data on your PCs.\n', encoding='utf-8')

    def _record_path(self, name):
        kind, _, ident = name.partition(':')
        return self.root / 'records' / f'{kind}.{ident}.json'

    @staticmethod
    def _write(path, data):
        temp = path.with_name(path.name + '.' + uuid.uuid4().hex[:8] + '.tmp')
        temp.write_bytes(data); os.replace(temp, path)

    async def status(self):
        files = list((self.root / 'files').glob('*.bin'))
        return {'available': True, 'kind': 'folder', 'usage': {'bytes': sum(f.stat().st_size for f in files), 'blobs': len(files)}}

    async def records(self):
        out = {}
        for p in (self.root / 'records').glob('*.json'):
            m = re.fullmatch(r'(chat|file|memory|settings|profile)\.([0-9a-f]{40})\.json', p.name)
            if not m: continue    # sync programs' conflict copies ("name (1).json", "name-PC.json") are ignored, never merged
            try: row = json.loads(p.read_text(encoding='utf-8'))
            except (OSError, ValueError): continue   # still being copied in; the next sync reads it
            out[m.group(1) + ':' + m.group(2)] = {'version': int(row.get('version', 0)), 'deleted': bool(row.get('deleted'))}
        return out

    async def get(self, name):
        try: return json.loads(self._record_path(name).read_text(encoding='utf-8'))
        except FileNotFoundError: return None

    async def put(self, name, base, payload, deleted):
        path = self._record_path(name)
        current = await self.get(name)
        if (current or {}).get('version', 0) != base: raise Conflict('Another device changed this first')
        version = base + 1
        self._write(path, json.dumps({'version': version, 'deleted': bool(deleted), 'payload': payload, 'updated': time.time()}).encode())
        return version

    async def put_blob(self, digest, content):
        path = self.root / 'files' / (digest + '.bin')
        if not path.exists(): self._write(path, content)

    async def get_blob(self, digest):
        try: return (self.root / 'files' / (digest + '.bin')).read_bytes()
        except FileNotFoundError: raise ValueError('A synced file has not arrived in the sync folder yet; it will retry.') from None


class EncryptedStore:
    """Encryption on top of any store. Local record names and content go in; only ciphertext goes out."""
    def __init__(self, key, store):
        self.key, self.store = key, store

    async def status(self): return await self.store.status()

    async def records(self):
        """Remote records by remote name. The local name is inside each record, read with get()."""
        return await self.store.records()

    async def get(self, remote):
        row = await self.store.get(remote)
        if row is None: return None
        payload = row.get('payload') or {}
        if not payload.get('enc'): raise ValueError('A synced record is not encrypted. It was written by an older Luminaria; sync it again from that PC after updating.')
        plain = json.loads(decrypt(self.key, base64.b64decode(payload['enc']), remote))
        data = dict(plain['data']); stored_at = data.pop('remote_blob', None)   # where the file is stored is not part of the record itself
        return {'version': row['version'], 'deleted': row.get('deleted', False), 'key': plain['key'], 'data': data, 'remote_blob': stored_at}

    async def put(self, local_key, base, data, deleted, blob_path=None, still_wanted=lambda: True):
        remote = remote_name(self.key, local_key)
        stored = dict(data or {})
        if blob_path and not deleted:
            content = encrypt(self.key, Path(blob_path).read_bytes(), 'file:' + stored['blob'])
            stored['remote_blob'] = hashlib.sha256(content).hexdigest()
            await self.store.put_blob(stored['remote_blob'], content)
            if not still_wanted(): raise ValueError('Sync was turned off. Local changes remain queued.')
        payload = {'enc': base64.b64encode(encrypt(self.key, json.dumps({'key': local_key, 'data': stored}).encode(), remote)).decode()}
        if stored.get('remote_blob'): payload['blob'] = stored['remote_blob']   # lets a service check the file arrived; reveals nothing
        return await self.store.put(remote, base, payload, deleted)

    async def get_blob(self, row):
        """The decrypted file for a record returned by get()."""
        data, stored_at = row['data'], row.get('remote_blob')
        if not stored_at: raise ValueError('This synced file has no stored content')
        content = await self.store.get_blob(stored_at)
        if hashlib.sha256(content).hexdigest() != stored_at: raise ValueError('A synced file failed its integrity check')
        plain = decrypt(self.key, content, 'file:' + data['blob'])
        if hashlib.sha256(plain).hexdigest() != data['blob']: raise ValueError('A synced file failed its integrity check')
        return plain


class ServiceStore:
    """A Luminaria sync service (a Cloudflare Worker running Luminaria's sync code). Same interface as FolderStore."""
    def __init__(self, client, base):
        self.client, self.base = client, base.rstrip('/') + '/sync/'

    async def _request(self, method, path, **kwargs):
        r = await self.client.request(method, self.base + path, **kwargs)
        if r.status_code == 409: raise Conflict('Another device changed this first')
        if r.status_code in (401, 403): raise ValueError('The sync service refused this device. Set up sync again in Settings › Cloud sync.')
        if r.status_code == 429: raise ValueError('The sync service reached its free-use limit and is paused. Your local data is safe.')
        if r.status_code == 413: raise ValueError('The sync service storage or file-size limit was reached. Your local data is safe.')
        if not r.is_success: raise ValueError(f'The sync service could not be reached ({r.status_code}). Your local data is safe.')
        return r

    async def status(self): return {**(await self._request('GET', 'status')).json(), 'kind': 'service'}

    async def records(self):
        rows, after = {}, ''
        while True:
            result = (await self._request('GET', 'records', params={'after': after})).json()
            for row in result['records']: rows[row['kind'] + ':' + row['id']] = {'version': row['version'], 'deleted': bool(row.get('deleted'))}
            after = result.get('next')
            if not after: return rows

    async def get(self, name):
        kind, _, ident = name.partition(':')
        r = await self.client.get(self.base + f'records/{kind}/{ident}')
        if r.status_code == 404: return None
        if not r.is_success: await self._request('GET', f'records/{kind}/{ident}')
        row = r.json()
        return {'version': row['version'], 'deleted': bool(row.get('deleted')), 'payload': row.get('data') or {}}

    async def put(self, name, base, payload, deleted):
        kind, _, ident = name.partition(':')
        mutation = hashlib.sha256(json.dumps([name, base, payload, bool(deleted)], sort_keys=True).encode()).hexdigest()
        return (await self._request('PUT', f'records/{kind}/{ident}', json={'base': base, 'mutation': mutation, 'data': payload, 'deleted': bool(deleted)})).json()['version']

    async def put_blob(self, digest, content):
        await self._request('PUT', 'blobs/' + digest, content=content, headers={'Content-Type': 'application/octet-stream', 'Content-Length': str(len(content))})

    async def get_blob(self, digest):
        return (await self._request('GET', 'blobs/' + digest)).content
