"""Built-in catalog of thousands of real skills and connectors, searchable offline.

Only metadata ships with the app. A skill is downloaded from its GitHub repository at the exact
commit recorded in the catalog, and only when the user (or the assistant, with the user's approval)
installs it. Connectors run third-party code, so installing one always goes through the same approval.
"""
import gzip,json,math,re,shutil
from pathlib import Path
import httpx
from .config import ROOT,DATA

_CACHE={}
SKILLS=DATA/'skills'
MAX_FILES=40; MAX_TOTAL=2_000_000

def load(kind):
    if kind not in _CACHE:
        path=ROOT/'catalog'/f'{kind}.json.gz'
        try:
            with gzip.open(path,'rt',encoding='utf-8') as f: _CACHE[kind]=json.load(f)
        except (OSError,ValueError): _CACHE[kind]={'items':[],'count':0}
    return _CACHE[kind]

def counts():
    return {k:load(k).get('count',0) for k in ('skills','connectors')}

def _public(kind,item):
    row={k:item.get(k) for k in ('id','name','description','repo','license','stars') if item.get(k) is not None}
    row['kind']='skill' if kind=='skills' else 'connector'
    if kind=='connectors':
        ready=[p for p in item.get('packages',[]) if not p.get('needs') and p.get('version')]
        row['installable']=bool(ready)
        if ready:
            row['package']={k:ready[0][k] for k in ('identifier','version')}
        row['needs']=sorted({n for p in item.get('packages',[]) for n in p.get('needs',[])})
        row['hosted']=bool(item.get('remotes'))
    else:
        row['installable']=True
    return row

def search(query='',kind=None,limit=10,offset=0):
    words=[w for w in re.findall(r'[a-z0-9]+',(query or '').lower()) if len(w)>1]
    kinds=[kind] if kind in ('skills','connectors') else ['skills','connectors']
    scored=[]
    for k in kinds:
        for item in load(k)['items']:
            name=(item.get('name') or '').lower(); desc=(item.get('description') or '').lower(); where=(item.get('repo') or item.get('id') or '').lower()
            score=0.0
            for w in words:
                if w in name: score+=6
                if re.search(r'\b'+re.escape(w),desc): score+=3
                elif w in desc: score+=1
                if w in where: score+=1
            if words and score<=0: continue
            if words and sum(1 for w in words if w in name or w in desc)<max(1,math.ceil(len(words)*0.5)): continue
            popularity=math.log10((item.get('stars') or 0)+10)
            scored.append((score+popularity,k,item))
    scored.sort(key=lambda s:-s[0])
    page=scored[offset:offset+limit]
    return {'items':[_public(k,i) for _,k,i in page],'total':len(scored),'counts':counts()}

def find(item_id):
    for k in ('skills','connectors'):
        for item in load(k)['items']:
            if item['id']==item_id: return k,item
    raise ValueError('That item is not in the catalog')

def _raw(repo,sha,path):
    if not re.fullmatch(r'[0-9a-f]{40}',sha or ''): raise ValueError('Catalog entry has no pinned commit')
    r=httpx.get(f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',timeout=30,follow_redirects=False,headers={'User-Agent':'Luminaria'})
    r.raise_for_status(); return r.content

def _safe_rel(base,path):
    rel=path[len(base)+1:] if base else path
    if not rel or rel.startswith(('/','\\')) or '..' in Path(rel).parts or ':' in rel: raise ValueError('Unsafe file path in skill')
    return rel

def install_skill(item):
    name=re.sub(r'[^a-z0-9-]+','-',item['name'].lower()).strip('-')[:60] or 'skill'
    target=SKILLS/name
    source=f"{item['repo']}:{item['path']}@{item['sha']}"
    if target.exists():
        meta=target/'SOURCE.json'
        same=meta.is_file() and json.loads(meta.read_text('utf-8')).get('id')==item['id']
        if not same:
            n=2
            while (SKILLS/f'{name[:56]}-{n}').exists(): n+=1
            name=f'{name[:56]}-{n}'; target=SKILLS/name
    folder=item['path'].rsplit('/',1)[0] if '/' in item['path'] else ''
    staging=SKILLS/('.installing-'+name)
    if staging.exists(): shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        total=0
        text=_raw(item['repo'],item['sha'],item['path'])
        (staging/'SKILL.md').write_bytes(text); total+=len(text)
        for f in item.get('files',[])[:MAX_FILES]:
            rel=_safe_rel(folder,f['path'])
            if total+f.get('size',0)>MAX_TOTAL: break
            data=_raw(item['repo'],item['sha'],f['path']); total+=len(data)
            dest=staging/rel; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
        (staging/'SOURCE.json').write_text(json.dumps({'id':item['id'],'source':source,'license':item.get('license'),
            'url':f"https://github.com/{item['repo']}/tree/{item['sha']}/{folder}"},indent=1),encoding='utf-8')
        if target.exists(): shutil.rmtree(target)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True); raise
    return {'kind':'skill','name':name,'files':sum(1 for p in target.rglob('*') if p.is_file()),'license':item.get('license'),'source':source}

def connector_plan(item):
    from .marketplace import connector_for
    package=next((p for p in item.get('packages',[]) if not p.get('needs') and p.get('version')),None)
    if not package:
        needs=sorted({n for p in item.get('packages',[]) for n in p.get('needs',[])})
        if needs: raise ValueError('This connector needs '+', '.join(needs)+' first. Add it in Settings › Integrations.')
        if item.get('packages'):
            raise ValueError('This connector has no exact package version to install.')
        raise ValueError('This connector is hosted online only. Add its address in Settings › Integrations.')
    return connector_for(item['id'],package)
