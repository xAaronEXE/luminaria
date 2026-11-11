"""Screenshots of pages the assistant built, so a model that can see images can check its own work.

Only local pages: files on this PC, and servers on this PC (localhost). Other websites are read with the
research tools instead. The page is opened in a headless browser that is already on Windows (Microsoft Edge),
without the user's profile, cookies or sign-ins.
"""
import asyncio, os, shutil, subprocess, tempfile, uuid
from pathlib import Path
from urllib.parse import urlparse

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', '[::1]'}


def browser():
    names = []
    if os.name == 'nt':
        for env in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
            base = os.environ.get(env)
            if base: names.append(Path(base) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe')
    found = next((p for p in names if p.is_file()), None)
    if found: return str(found)
    for name in ('msedge', 'chromium', 'chromium-browser', 'google-chrome'):
        path = shutil.which(name)
        if path: return path
    return None


def target(address, resolve):
    """A file path or a localhost address, as a URL the browser can open. Anything else is refused."""
    text = str(address or '').strip()
    if not text: raise ValueError('Give a file path or a localhost address')
    parsed = urlparse(text)
    if parsed.scheme in ('http', 'https'):
        if (parsed.hostname or '').lower() not in LOCAL_HOSTS:
            raise ValueError('Screenshots are only for pages on this PC (a file or localhost). Read other websites with research or web_fetch.')
        return text
    path = Path(resolve(text[7:] if text.startswith('file://') else text))
    if not path.is_file(): raise ValueError(f'{text} does not exist')
    return path.resolve().as_uri()


async def take(address, resolve, folder, width=1280, height=900):
    exe = browser()
    if not exe: raise ValueError('No browser for screenshots was found (Microsoft Edge comes with Windows).')
    url = target(address, resolve)
    width, height = max(320, min(int(width or 1280), 2560)), max(240, min(int(height or 900), 2400))
    Path(folder).mkdir(parents=True, exist_ok=True)
    out = Path(folder) / (uuid.uuid4().hex + '.png')
    profile = tempfile.mkdtemp(prefix='luminaria-shot-')   # a throwaway profile: no cookies, sign-ins or history
    args = [exe, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--disable-extensions', '--mute-audio',
            f'--user-data-dir={profile}', f'--window-size={width},{height}', '--virtual-time-budget=4000', f'--screenshot={out}', url]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    if os.name != 'nt' and hasattr(os, 'geteuid') and os.geteuid() == 0: args.insert(1, '--no-sandbox')   # Linux test machines running as root
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE, creationflags=flags)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), 60)
    except asyncio.TimeoutError:
        proc.kill(); raise ValueError('The page did not finish loading within 60 seconds.') from None
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not out.is_file() or out.stat().st_size == 0:
        raise ValueError('The screenshot could not be taken: ' + (err or b'').decode('utf-8', 'replace').strip()[-300:])
    return out
