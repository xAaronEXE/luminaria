"""Opt-in releases from the user's configured GitHub repository; no silent installs."""
import hashlib, os, re, subprocess
from pathlib import Path
import httpx
from packaging.version import Version
from .config import CONFIG,DATA

async def check():
    repo=CONFIG.get('release_repo','')
    if not repo: return {'configured':False,'current':CONFIG['version'],'message':'Updates will be available when the publisher enables the release channel.'}
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo): raise ValueError('Invalid release repository')
    async with httpx.AsyncClient(timeout=25,follow_redirects=True) as c:
        r=await c.get(f'https://api.github.com/repos/{repo}/releases/latest',headers={'Accept':'application/vnd.github+json','User-Agent':'LocalAIStudio-Updater'})
        if r.status_code==404: return {'configured':True,'available':False,'current':CONFIG['version'],'message':'No public stable release has been published yet.'}
        r.raise_for_status(); release=r.json()
    tag=release['tag_name']; assets=release.get('assets',[])
    installer=next((a for a in assets if a['name'].startswith(('Luminaria-','LocalAIStudio-')) and a['name'].endswith('-Setup.exe')),None)
    hashes=next((a for a in assets if a['name']=='SHA256SUMS.txt'),None)
    return {'configured':True,'available':Version(tag.lstrip('v'))>Version(CONFIG['version']),'current':CONFIG['version'],'version':tag,'notes':release.get('body','')[:12000],'url':release['html_url'],'installer':installer,'checksums':hashes,'installable':bool(installer and hashes),'signing':'Checksum-verified. Code signing depends on the release publisher.'}

async def install():
    info=await check()
    if not info.get('available') or not info.get('installable'): raise ValueError('No newer complete release is available')
    repo=CONFIG['release_repo']; prefix=f'https://github.com/{repo}/releases/download/'
    asset=info['installer']; checksum=info['checksums']
    for a in [asset,checksum]:
        if not a['browser_download_url'].startswith(prefix): raise ValueError('Unexpected release asset origin')
    folder=DATA/'updates'; folder.mkdir(exist_ok=True)
    name=Path(asset['name']).name
    if not re.fullmatch(r'LocalAIStudio-[A-Za-z0-9.-]+-Setup\.exe',name): raise ValueError('Invalid installer filename')
    target=folder/name; partial=folder/(name+'.partial')
    async with httpx.AsyncClient(timeout=120,follow_redirects=True) as c:
        r=await c.get(checksum['browser_download_url']); r.raise_for_status()
        rows=[line.split() for line in r.text.splitlines()]
        digest=next((p[0].lower() for p in rows if len(p)==2 and p[1].lstrip('*')==name),None)
        if not digest or not re.fullmatch('[a-f0-9]{64}',digest): raise ValueError('Installer checksum missing')
        h=hashlib.sha256(); size=0
        try:
            async with c.stream('GET',asset['browser_download_url']) as stream:
                stream.raise_for_status()
                with partial.open('wb') as f:
                    async for chunk in stream.aiter_bytes():
                        size+=len(chunk)
                        if size>1_000_000_000: raise ValueError('Installer exceeds 1 GB')
                        h.update(chunk); f.write(chunk)
            if h.hexdigest()!=digest: raise ValueError('Checksum mismatch. Installer was not executed.')
            partial.replace(target)
        finally:
            if partial.exists(): partial.unlink()
    subprocess.Popen([str(target)],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    return {'launched':True,'message':'Verified installer opened. Close Studio when the installer requests it. Your history is retained.'}
