import json,re
from .config import DATA,ROOT,CONFIG,external_tools_enabled

NEEDS={'execution':'Computer and command tools (Settings → Tools & permissions)',
       'github':'GitHub integration','browser':'Browser connector','windows':'Windows desktop connector'}

def describe(text):
    """Description from SKILL.md frontmatter, else the first line of prose."""
    m=re.match(r'^\ufeff?---\s*\n(.*?)\n---',text,re.S)
    if m:
        d=re.search(r'^description:\s*(?:[>|][-+]?\s*\n((?:[ \t]+.*\n?)+)|(.+))$',m.group(1),re.M)
        if d: return re.sub(r'\s+',' ',(d.group(1) or d.group(2) or '')).strip('"\' ')
        text=text[m.end():]
    return next((l.strip() for l in text.splitlines() if l.strip() and not l.startswith(('#','<!--','```'))),'')

def inventory():
    path=ROOT/'skills'/'inventory.json'
    return json.loads(path.read_text('utf-8')) if path.is_file() else {'categories':[],'skills':{}}

def missing(requires,connectors):
    gaps=[]
    for need in requires:
        if need!='execution':
            c=(connectors or {}).get(need)
            if not (c and c.status=='connected'):gaps.append(NEEDS.get(need,need))
        if not external_tools_enabled() and NEEDS['execution'] not in gaps:gaps.append(NEEDS['execution'])
    return gaps

def catalog(connectors=None):
    meta=inventory()['skills'];result={}
    for folder in [ROOT/'skills',DATA/'skills']:
        if folder.exists():
            for p in folder.glob('*/SKILL.md'):
                text=p.read_text('utf-8');name=p.parent.name;local=folder==DATA/'skills';info=meta.get(name,{}) if not local else {}
                requires=info.get('requires',[]);gaps=missing(requires,connectors)
                result[name]={'name':name,'description':describe(text)[:200],'local':local,
                              'category':info.get('category','Imported' if local else ('Community' if (p.parent/'SOURCE.json').is_file() else 'Other')),'requires':[NEEDS.get(r,r) for r in requires],'missing':gaps,'available':not gaps,
                              'state':'Needs setup' if gaps else 'Ready','reason':'; '.join(gaps) if gaps else 'Declared dependencies are available; instructions do not grant permissions.',
                              'permissions':'Uses the same per-action permissions as the chat.',
                              'inputs':info.get('inputs','User task and explicitly provided sources'),
                              'outputs':info.get('outputs','Follow the workflow instructions; verify its output before completion.')}
    return sorted(result.values(),key=lambda s:s['name'])

def preflight(name,connectors=None):
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Invalid skill name')
    row=next((s for s in catalog(connectors) if s['name']==name),None)
    if row is None:raise ValueError('Skill not found')
    from pathlib import Path
    try:next(Path(CONFIG['workspace']).iterdir(),None)
    except (OSError,ValueError):
        row={**row,'available':False,'state':'Needs setup','missing':[*row['missing'],'Readable working folder'],'reason':'The configured working folder is missing or cannot be read. Choose an accessible folder in Settings.'}
    return row

def load_skill(name):
    if not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Invalid skill name')
    for root in [DATA/'skills',ROOT/'skills']:
        p=root/name/'SKILL.md'
        if p.exists():
            extra=sorted(str(f.relative_to(p.parent)) for f in p.parent.rglob('*') if f.is_file() and f.name not in ('SKILL.md','SOURCE.json'))[:40]
            return {'name':name,'folder':str(p.parent),'files':extra,'instructions':p.read_text('utf-8')[:20000],'note':'Workflow guidance; does not grant credentials or override user approvals.'}
    raise ValueError('Skill not found')

def save_skill(name,content):
    if not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Use lowercase letters, numbers and hyphens')
    if len(content)>20000: raise ValueError('Skill limit is 20,000 characters')
    p=DATA/'skills'/name/'SKILL.md'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8')
    return {'name':name}

def remove_skill(name):
    if not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Invalid skill name')
    p=DATA/'skills'/name/'SKILL.md'
    if not p.is_file(): raise ValueError('Only skills you imported can be removed')
    import shutil
    shutil.rmtree(p.parent)
    return {'name':name}
