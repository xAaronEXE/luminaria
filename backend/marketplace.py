"""Free marketplace: public skill repositories on GitHub and the official MCP Registry. Nothing is paid, nothing is run until installed."""
import json,os,re,time
import httpx
from .config import DATA

REGISTRY='https://registry.modelcontextprotocol.io/v0/servers'
# Public repositories that hold SKILL.md folders. Users can add more by owner/name.
SKILL_REPOS=['anthropics/skills','openai/skills']
TTL=6*3600
CACHE=DATA/'marketplace-cache'

def _cached(key,fetch):
    CACHE.mkdir(exist_ok=True)
    path=CACHE/(re.sub(r'[^a-z0-9._-]','_',key.lower())[:120]+'.json')
    if path.is_file() and time.time()-path.stat().st_mtime<TTL:
        try:return json.loads(path.read_text('utf-8'))
        except ValueError:pass
    try:
        data=fetch()
    except httpx.HTTPError:
        if path.is_file():return json.loads(path.read_text('utf-8'))  # offline: last good copy
        raise
    path.write_text(json.dumps(data),encoding='utf-8');return data

def _get(url,**params):
    r=httpx.get(url,params=params or None,timeout=20,follow_redirects=True,headers={'Accept':'application/json','User-Agent':'Luminaria'})
    r.raise_for_status();return r.json()

def valid_repo(repo):
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}',repo):raise ValueError('Use owner/name, for example anthropics/skills')
    return repo

def repo_skills(repo):
    repo=valid_repo(repo)
    def fetch():
        tree=_get(f'https://api.github.com/repos/{repo}/git/trees/HEAD',recursive=1).get('tree',[])
        return [t['path'] for t in tree if t.get('type')=='blob' and t['path'].endswith('/SKILL.md') or t.get('path')=='SKILL.md']
    out=[]
    for path in _cached('skills-'+repo,fetch):
        folder=path.rsplit('/',1)[0] if '/' in path else ''
        name=(folder.rsplit('/',1)[-1] if folder else repo.split('/')[1]).lower()
        name=re.sub(r'[^a-z0-9-]+','-',name).strip('-')[:60]
        if name:out.append({'id':repo+':'+path,'name':name,'repo':repo,'path':path,'folder':folder})
    return out

def search_skills(query='',extra=()):
    query=query.strip().lower();rows=[];errors=[]
    for repo in [*SKILL_REPOS,*extra]:
        try:rows+=repo_skills(repo)
        except (httpx.HTTPError,ValueError) as e:errors.append(f'{repo}: {type(e).__name__}')
    if query:rows=[r for r in rows if query in r['name'] or query in r['repo'].lower() or query in r['folder'].lower()]
    return {'items':rows[:200],'total':len(rows),'errors':errors}

def skill_text(repo,path):
    repo=valid_repo(repo)
    if not re.fullmatch(r'[A-Za-z0-9_./ -]{1,200}',path) or '..' in path or not path.endswith('SKILL.md'):raise ValueError('Invalid skill path')
    r=httpx.get(f'https://raw.githubusercontent.com/{repo}/HEAD/{path}',timeout=20,follow_redirects=True,headers={'User-Agent':'Luminaria'})
    r.raise_for_status();return r.text

def describe(text):
    body=re.sub(r'^---.*?---\s*','',text,flags=re.S)
    m=re.search(r'^description:\s*(.+)$',text,re.M)
    return (m.group(1).strip('"\' ') if m else next((l.strip() for l in body.splitlines() if l.strip() and not l.startswith('#')),''))[:240]

def install_skill(repo,path,name=None):
    from .skills import save_skill
    text=skill_text(repo,path)
    folder=path.rsplit('/',1)[0] if '/' in path else repo.split('/')[1]
    name=name or re.sub(r'[^a-z0-9-]+','-',folder.rsplit('/',1)[-1].lower()).strip('-')[:60]
    if len(text)>20000:text=text[:20000]
    return save_skill(name,text)

def _server(item):
    s=item.get('server',item);meta=item.get('_meta',{})
    packages=[]
    for p in s.get('packages',[]) or []:
        kind=(p.get('registryType') or p.get('registry_type') or '').lower()
        ident=p.get('identifier') or p.get('name')
        if kind in ('npm','pypi') and ident:
            needs=[e.get('name') for e in (p.get('environmentVariables') or []) if e.get('isRequired') or e.get('is_required')]
            packages.append({'kind':kind,'identifier':ident,'version':p.get('version'),'needs':needs})
    remotes=[r.get('url') for r in (s.get('remotes') or []) if r.get('url')]
    return {'id':s.get('name',''),'title':s.get('title') or s.get('name',''),'description':(s.get('description') or '')[:300],'packages':packages,'remotes':remotes,'repo':(s.get('repository') or {}).get('url'),'installable':bool(packages)}

def search_mcp(query='',cursor=None):
    params={'limit':30}
    if query.strip():params['search']=query.strip()
    if cursor:params['cursor']=cursor
    data=_cached('mcp-'+json.dumps(params,sort_keys=True),lambda:_get(REGISTRY,**params))
    items=[_server(i) for i in data.get('servers',[])]
    return {'items':items,'next':(data.get('metadata') or {}).get('nextCursor') or (data.get('metadata') or {}).get('next_cursor')}

def connector_for(server_id,package):
    # Registry names look like io.github.owner/server; connector names are short, lowercase, unique.
    base=re.sub(r'[^a-z0-9_]+','_',server_id.split('/')[-1].lower()).strip('_') or 'connector'
    name=('m_'+base)[:30]
    ident=str(package['identifier']);version=str(package.get('version') or '')
    # A package name must never be able to smuggle a command-line flag or a shell character.
    if not re.fullmatch(r'(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*',ident,re.I):raise ValueError('Unsafe package name')
    if version and not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+_-]*',version):raise ValueError('Unsafe package version')
    package={**package,'identifier':ident,'version':version or None}
    if package['kind']=='npm':command,args=('npx.cmd' if os.name=='nt' else 'npx'),['-y',ident+('@'+package['version'] if package.get('version') else '')]
    else:command,args=('uvx.exe' if os.name=='nt' else 'uvx'),[ident+('=='+package['version'] if package.get('version') else '')]
    return name,command,args
