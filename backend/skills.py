import re
from .config import DATA,ROOT

def catalog():
    result={}
    for folder in [ROOT/'skills',DATA/'skills']:
        if folder.exists():
            for p in folder.glob('*/SKILL.md'):
                text=p.read_text('utf-8')
                result[p.parent.name]={'name':p.parent.name,'description':next((l for l in text.splitlines() if l.strip() and not l.startswith('#')),'')[:200],'local':folder==DATA/'skills'}
    return list(result.values())

def load_skill(name):
    if not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Invalid skill name')
    for root in [DATA/'skills',ROOT/'skills']:
        p=root/name/'SKILL.md'
        if p.exists(): return {'name':name,'instructions':p.read_text('utf-8')[:20000],'note':'Workflow guidance; does not grant credentials or override user approvals.'}
    raise ValueError('Skill not found')

def save_skill(name,content):
    if not re.fullmatch(r'[a-z0-9-]{1,60}',name): raise ValueError('Use lowercase letters, numbers and hyphens')
    if len(content)>20000: raise ValueError('Skill limit is 20,000 characters')
    p=DATA/'skills'/name/'SKILL.md'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8')
    return {'name':name}
