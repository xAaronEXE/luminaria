"""Builds Luminaria's built-in catalog of real, openly licensed skills and connectors.

  python scripts/build-catalog.py skills       -> catalog/skills.json.gz      (uses the signed-in gh CLI, or GITHUB_TOKEN)
  python scripts/build-catalog.py connectors   -> catalog/connectors.json.gz  (official MCP Registry, no account needed)
  python scripts/build-catalog.py preinstall DIR -> about 100 vetted skills, with their source licenses, ready to bundle

Only metadata is stored. A skill is downloaded, at the exact commit recorded here, when someone installs it.
"""
import gzip,json,os,re,subprocess,sys,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/'catalog'
LICENSES={'MIT','Apache-2.0','BSD-2-Clause','BSD-3-Clause','ISC','CC0-1.0','CC-BY-4.0','Unlicense','MPL-2.0','0BSD'}
TOPICS=['claude-skills','agent-skills','claude-code-skills','skills','codex-skills','anthropic-skills','claude-skill','ai-skills','agentskills','skill-md','claude-code-plugins','claude-code-subagents']
SEEDS=['anthropics/skills','openai/skills','K-Dense-AI/scientific-agent-skills','coreyhaines31/marketingskills','wshobson/agents','alirezarezvani/claude-skills','VoltAgent/awesome-agent-skills','OthmanAdi/planning-with-files','JimLiu/baoyu-skills']
MIN_STARS=25
PER_REPO=400
TEXT=re.compile(r'\.(md|txt|py|js|mjs|cjs|ts|json|yaml|yml|toml|sh|ps1|html|css|csv|xml|sql|r|ipynb)$',re.I)

def _token():
    token=os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        import shutil
        gh=shutil.which('gh') or next((p for p in (r'C:\Program Files\GitHub CLI\gh.exe',os.path.expandvars(r'%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe')) if os.path.isfile(p)),None)
        if not gh: print('GitHub CLI (gh) was not found',flush=True); return ''
        try:
            p=subprocess.run([gh,'auth','token'],capture_output=True,text=True,timeout=20)
            token=p.stdout.strip()
            if not token: print('gh auth token gave no token: '+(p.stderr or '').strip()[:300],flush=True)
        except (OSError,subprocess.SubprocessError) as e: print(f'gh auth token failed: {e}',flush=True); token=''
    return token
TOKEN=None

def raw_file(repo,sha,path):
    """File contents from raw.githubusercontent.com (no API quota used)."""
    url=f'https://raw.githubusercontent.com/{repo}/{sha}/'+urllib.parse.quote(path)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'luminaria-catalog'}),timeout=40) as r: return r.read().decode('utf-8','replace')
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(3*(attempt+1))
        except Exception: time.sleep(3*(attempt+1))
    return None

def api(path,raw=False):
    """GitHub REST call with the signed-in gh account's token (GITHUB_TOKEN also works)."""
    global TOKEN
    if TOKEN is None: TOKEN=_token()
    token=TOKEN
    for attempt in range(4):
        try:
            if token:
                req=urllib.request.Request('https://api.github.com/'+path,headers={'Authorization':'Bearer '+token,'User-Agent':'luminaria-catalog',
                    'Accept':'application/vnd.github.raw' if raw else 'application/vnd.github+json'})
                with urllib.request.urlopen(req,timeout=40) as r: body=r.read()
            else:
                cmd=['gh','api',path]+(['-H','Accept: application/vnd.github.raw'] if raw else [])
                p=subprocess.run(cmd,capture_output=True,timeout=60)
                if p.returncode:
                    err=p.stderr.decode('utf-8','replace')
                    if '404' in err or 'Not Found' in err or 'too large' in err.lower(): return None
                    raise RuntimeError(err[:200])
                body=p.stdout
            return body.decode('utf-8','replace') if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code in (404,409,451): return None
            time.sleep(5*(attempt+1))
        except Exception:
            time.sleep(3*(attempt+1))
    return None

def frontmatter(text):
    m=re.match(r'^﻿?---\s*\n(.*?)\n---',text,re.S); head=m.group(1) if m else ''
    def field(k):
        f=re.search(r'^'+k+r':\s*(?:[>|][-+]?\s*\n((?:[ \t]+.*\n?)+)|(.+))$',head,re.M)
        if not f: return ''
        v=(f.group(1) or f.group(2) or '').strip()
        return re.sub(r'\s+',' ',v).strip('"\' ')
    body=text[m.end():] if m else text
    first=next((l.strip() for l in body.splitlines() if l.strip() and not l.startswith(('#','<!--','```'))),'')
    return field('name'),(field('description') or first),field('license')

def discover():
    repos={}
    def take(item):
        lic=((item.get('license') or {}).get('spdx_id')) or ''
        if item.get('archived') or item.get('fork') or lic not in LICENSES or item.get('stargazers_count',0)<MIN_STARS: return
        repos[item['full_name']]={'repo':item['full_name'],'stars':item['stargazers_count'],'license':lic,'branch':item.get('default_branch','main')}
    for seed in SEEDS:
        item=api('repos/'+seed)
        if item: take(item)
    for topic in TOPICS:
        for page in (1,2,3):
            q=urllib.parse.quote(f'topic:{topic} stars:>={MIN_STARS}')
            res=api(f'search/repositories?q={q}&sort=stars&per_page=100&page={page}')
            time.sleep(2.2)  # search allows 30 requests a minute
            if not res or not res.get('items'): break
            for item in res['items']: take(item)
    return repos

PREVIOUS={}

def repo_skills(info):
    repo=info['repo']
    head=api(f"repos/{repo}/commits/{info['branch']}")
    if not head: return []
    sha=head['sha']
    old=PREVIOUS.get(repo)
    if old and old[0]['sha']==sha:  # unchanged since the last catalog: reuse it without downloading again
        return [{**i,'stars':info['stars'],'reuse':True} for i in old]
    tree=api(f'repos/{repo}/git/trees/{sha}?recursive=1') or {}
    blobs={t['path']:t.get('size',0) for t in tree.get('tree',[]) if t.get('type')=='blob'}
    paths=[p for p in blobs if p.endswith('SKILL.md') and not re.search(r'(^|/)(node_modules|\.git|test|tests|fixtures|examples?/templates)/',p)][:PER_REPO]
    rows=[]
    for path in paths:
        folder=path.rsplit('/',1)[0] if '/' in path else ''
        files=[{'path':p,'size':s} for p,s in blobs.items() if (p.startswith(folder+'/') if folder else '/' not in p) and p!=path and TEXT.search(p) and s<=200_000][:40]
        rows.append({'repo':repo,'path':path,'folder':folder,'sha':sha,'stars':info['stars'],'license':info['license'],'files':files})
    return rows

def fill(row):
    if row.get('reuse'): return {k:v for k,v in row.items() if k!='reuse'}
    text=raw_file(row['repo'],row['sha'],row['path'])
    if not text or len(text)>60_000: return None
    name,desc,own=frontmatter(text)
    # A skill can carry its own terms (for example "Proprietary. LICENSE.txt has complete terms").
    lic=row['license']
    if own: lic=own if own in LICENSES else 'See source'
    if any(re.search(r'/(LICENSE|LICENCE|COPYING)[^/]*$',f['path'],re.I) for f in row['files']) and not own: lic='See source'
    row={**row,'license':lic}
    slug=re.sub(r'[^a-z0-9-]+','-',(name or (row['folder'].rsplit('/',1)[-1] if row['folder'] else row['repo'].split('/')[1])).lower()).strip('-')[:60]
    if not slug or not desc or len(desc)<20: return None
    return {'id':row['repo']+':'+row['path'],'name':slug,'description':desc[:400],'repo':row['repo'],'path':row['path'],'sha':row['sha'],
            'license':row['license'],'stars':row['stars'],'files':row['files'],'size':len(text)}

def skills():
    existing=OUT/'skills.json.gz'
    if existing.is_file() and time.time()-existing.stat().st_mtime<7*86400 and not os.environ.get('LUMINARIA_REFRESH_CATALOG'):
        print('Skill catalog is less than 7 days old; keeping it (set LUMINARIA_REFRESH_CATALOG=1 to refresh).',flush=True); return
    if not _token(): raise SystemExit('Sign in with "gh auth login" (or set GITHUB_TOKEN) to build the skill catalog')
    if existing.is_file():
        try:
            with gzip.open(existing,'rt',encoding='utf-8') as f:
                for i in json.load(f)['items']: PREVIOUS.setdefault(i['repo'],[]).append(i)
        except (OSError,ValueError): PREVIOUS.clear()
    repos=discover(); print(f'{len(repos)} openly licensed repositories',flush=True)
    with ThreadPoolExecutor(8) as pool: found=[r for rows in pool.map(repo_skills,repos.values()) for r in rows]
    print(f'{len(found)} SKILL.md files',flush=True)
    with ThreadPoolExecutor(12) as pool: items=[i for i in pool.map(fill,found) if i]
    seen=set(); unique=[]
    for i in sorted(items,key=lambda i:-i['stars']):
        key=(i['name'],i['description'][:80])
        if key in seen: continue
        seen.add(key); unique.append(i)
    write('skills',unique,{'repositories':len(repos)})

def connectors():
    url='https://registry.modelcontextprotocol.io/v0/servers'; cursor=None; items={}
    while True:
        q={'limit':100,**({'cursor':cursor} if cursor else {})}
        req=urllib.request.Request(url+'?'+urllib.parse.urlencode(q),headers={'Accept':'application/json','User-Agent':'luminaria-catalog'})
        data=None
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req,timeout=60) as r: data=json.loads(r.read()); break
            except (OSError,ValueError) as e:
                print(f'MCP Registry page failed ({type(e).__name__}); retrying',flush=True); time.sleep(5*(attempt+1))
        if data is None:
            if items: print(f'MCP Registry stopped responding; keeping the {len(items)} connectors read so far',flush=True); break
            raise SystemExit('The MCP Registry did not respond')
        for entry in data.get('servers',[]):
            s=entry.get('server',entry); meta=(entry.get('_meta') or {}).get('io.modelcontextprotocol.registry/official') or {}
            if meta.get('status') not in (None,'active') or meta.get('isLatest') is False: continue
            packages=[]
            for p in s.get('packages') or []:
                kind=(p.get('registryType') or '').lower(); ident=p.get('identifier')
                if kind in ('npm','pypi') and ident and (p.get('transport') or {}).get('type','stdio')=='stdio':
                    packages.append({'kind':kind,'identifier':ident,'version':p.get('version'),
                        'needs':[e.get('name') for e in (p.get('environmentVariables') or []) if e.get('isRequired')]})
            remotes=[r.get('url') for r in s.get('remotes') or [] if r.get('url')]
            if not packages and not remotes: continue
            items[s['name']]={'id':s['name'],'name':s.get('title') or s['name'].split('/')[-1],'description':(s.get('description') or '')[:400],
                'version':s.get('version'),'packages':packages,'remotes':remotes,'repo':(s.get('repository') or {}).get('url','')}
        cursor=(data.get('metadata') or {}).get('nextCursor')
        if not cursor: break
    write('connectors',list(items.values()),{})

TRUSTED=['anthropics/skills','openai/skills','K-Dense-AI/scientific-agent-skills','coreyhaines31/marketingskills','wshobson/agents',
         'alirezarezvani/claude-skills','OthmanAdi/planning-with-files']
PREINSTALL=100; PER_TRUSTED=25

def preinstall(target):
    target=Path(target); builtin={p.name for p in (OUT.parent/'skills').iterdir() if p.is_dir()}
    with gzip.open(OUT/'skills.json.gz','rt',encoding='utf-8') as f: items=json.load(f)['items']
    picked=[]; per={}
    for repo in TRUSTED:
        for i in sorted((i for i in items if i['repo']==repo and i['license'] in LICENSES),key=lambda i:i['path']):
            if per.get(repo,0)>=PER_TRUSTED or len(picked)>=PREINSTALL: break
            if i['name'] in builtin or any(p['name']==i['name'] for p in picked): continue
            picked.append(i); per[repo]=per.get(repo,0)+1
    if target.exists():
        import shutil; shutil.rmtree(target)
    target.mkdir(parents=True,exist_ok=True); licenses={}
    for i in picked:
        folder=i['path'].rsplit('/',1)[0] if '/' in i['path'] else ''
        dest=target/i['name']; dest.mkdir(parents=True)
        text=raw_file(i['repo'],i['sha'],i['path'])
        if text is None: import shutil; shutil.rmtree(dest); continue
        (dest/'SKILL.md').write_text(text,encoding='utf-8')
        for f in i['files']:
            rel=f['path'][len(folder)+1:] if folder else f['path']
            if '..' in Path(rel).parts: continue
            data=raw_file(i['repo'],i['sha'],f['path'])
            if data is None: continue
            (dest/rel).parent.mkdir(parents=True,exist_ok=True); (dest/rel).write_text(data,encoding='utf-8')
        if i['repo'] not in licenses:
            meta=api(f"repos/{i['repo']}/license") or {}
            import base64
            licenses[i['repo']]=base64.b64decode(meta.get('content','')).decode('utf-8','replace') if meta.get('content') else f"{i['license']} licence: https://github.com/{i['repo']}"
        (dest/'LICENSE-SOURCE.txt').write_text(licenses[i['repo']],encoding='utf-8')
        (dest/'SOURCE.json').write_text(json.dumps({'id':i['id'],'source':f"{i['repo']}:{i['path']}@{i['sha']}",'license':i['license'],
            'url':f"https://github.com/{i['repo']}/tree/{i['sha']}/{folder}",'preinstalled':True},indent=1),encoding='utf-8')
    print(f'Pre-installed {sum(1 for p in target.iterdir())} skills from {len(per)} repositories',flush=True)

def write(kind,items,extra):
    OUT.mkdir(exist_ok=True)
    data={'kind':kind,'generated':time.strftime('%Y-%m-%d'),'count':len(items),**extra,'items':items}
    with gzip.open(OUT/f'{kind}.json.gz','wt',encoding='utf-8') as f: json.dump(data,f,separators=(',',':'))
    print(f'Wrote {len(items)} {kind}',flush=True)

if __name__=='__main__':
    if sys.argv[1]=='preinstall': preinstall(sys.argv[2])
    else: {'skills':skills,'connectors':connectors}[sys.argv[1]]()
