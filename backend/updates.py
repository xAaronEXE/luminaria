"""Checks Luminaria's release channel; installs only after the user confirms."""
import hashlib, os, re, subprocess
from pathlib import Path
import httpx
from packaging.version import InvalidVersion, Version
from .config import CONFIG, DATA
from .identity import ORIGIN

CHANNEL = ORIGIN + '/releases'
HEADERS = {'User-Agent': 'Luminaria-Updater', 'Accept': 'application/json'}
MAX_INSTALLER = 2_000_000_000
SIGNING = 'The installer is checked against its published SHA256 before it opens. It is not code-signed yet, so Windows may show a SmartScreen warning.'

def _status(message, **extra):
    return {'current': CONFIG['version'], 'available': False, 'installable': False, 'message': message} | extra

def _manifest(data):
    installer = data.get('installer') if isinstance(data, dict) else None
    if not isinstance(installer, dict): raise ValueError('The update service returned an incomplete release.')
    version = str(data.get('version', ''))
    name = str(installer.get('name', ''))
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or name != f'Luminaria-{version}-Setup.exe':
        raise ValueError('The update service returned an invalid release.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(installer.get('sha256', ''))):
        raise ValueError('The release is missing a valid checksum.')
    size = installer.get('size')
    if not isinstance(size, int) or not 0 < size <= MAX_INSTALLER:
        raise ValueError('The release installer has an invalid size.')
    if installer.get('url') != f"{CHANNEL}/download/v{version}/{name}":
        raise ValueError('The release installer comes from an unexpected address.')
    return version, installer

async def check():
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            response = await client.get(CHANNEL + '/latest', headers=HEADERS)
    except httpx.HTTPError:
        return _status('Could not reach the update service. Check your connection and try again.', reachable=False)
    if response.status_code == 503:
        return _status('The update service is not set up yet. Your installed version keeps working.', configured=False)
    if response.status_code == 404:
        return _status('No release has been published yet.', configured=True)
    if response.status_code == 409:
        return _status('The latest release is missing its installer or checksum, so it cannot be installed.', configured=True)
    if response.status_code != 200:
        return _status(f'The update service returned an error ({response.status_code}). Try again later.', configured=True)
    data = response.json()
    version, installer = _manifest(data)
    try: available = Version(version) > Version(CONFIG['version'])
    except InvalidVersion: raise ValueError('The release version could not be compared.') from None
    return {'configured': True, 'reachable': True, 'current': CONFIG['version'], 'version': version, 'available': available,
            'installable': available, 'notes': str(data.get('notes', ''))[:12000], 'published_at': data.get('published_at'),
            'installer': {k: installer[k] for k in ('name', 'size', 'sha256', 'url')}, 'signing': SIGNING,
            'message': f'Version {version} is available.' if available else f'You have the latest version ({CONFIG["version"]}).'}

def cleanup():
    """After an update has installed, remove what it left behind: the downloaded installer for this or any
    older version, unfinished downloads, and the one-time handoff script. A newer installer is kept so an
    update that has not run yet still can. Logs stay for troubleshooting."""
    folder = DATA / 'updates'
    if not folder.is_dir(): return []
    removed = []
    try: current = Version(CONFIG['version'])
    except InvalidVersion: return []
    for p in folder.iterdir():
        if not p.is_file(): continue
        m = re.fullmatch(r'Luminaria-(\d+\.\d+\.\d+)-Setup\.exe', p.name)
        stale = p.name.endswith('.partial') or p.name == 'update-handoff.ps1' or (m and Version(m.group(1)) <= current)
        if stale:
            try: p.unlink(); removed.append(p.name)
            except OSError: pass
    return removed

async def install():
    info = await check()
    if not info.get('installable'): raise ValueError(info.get('message') or 'No newer release is available.')
    installer = info['installer']
    folder = DATA / 'updates'; folder.mkdir(exist_ok=True)
    name = Path(installer['name']).name
    target = folder / name; partial = folder / (name + '.partial')
    digest = hashlib.sha256(); size = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=300), follow_redirects=False) as client:
            async with client.stream('GET', installer['url'], headers={'User-Agent': HEADERS['User-Agent']}) as stream:
                if stream.status_code != 200: raise ValueError(f'The installer download failed ({stream.status_code}). Nothing was opened.')
                with partial.open('wb') as handle:
                    async for chunk in stream.aiter_bytes():
                        size += len(chunk)
                        if size > installer['size']: raise ValueError('The installer is larger than the release says. Nothing was opened.')
                        digest.update(chunk); handle.write(chunk)
        if size != installer['size'] or digest.hexdigest() != installer['sha256']:
            raise ValueError('Checksum mismatch. The installer was deleted and not opened.')
        partial.replace(target)
    except httpx.HTTPError:
        raise ValueError('The installer download was interrupted. Nothing was opened. Try again.') from None
    finally:
        if partial.exists(): partial.unlink()
    from .update_handoff import launch
    closing=launch(target)
    return {'launched': True, 'version': info['version'],
            'closing':closing,'message': 'Update verified. Luminaria is closing before Setup starts.' if closing else 'Verified installer opened. Close Luminaria before continuing Setup.'}
