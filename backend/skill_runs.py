"""Skill lifecycle is separate from reading instructions and requires output evidence."""
import hashlib
from .config import workspace_path
from .store import now

def set_state(store,name,state,reason,run):
    value={'state':state,'reason':reason,'run':run['id'],'updated':now()}
    store.set_setting('skill_run:'+name,value)
    return value

def complete(store,name,outputs,evidence,run):
    prior=store.setting('skill_run:'+name,{})
    if prior.get('run')!=run['id'] or prior.get('state')!='Running':raise ValueError('Load this skill in the current run before completing it.')
    if not isinstance(outputs,list) or not 1<=len(outputs)<=10:raise ValueError('Provide one to ten output file paths to verify.')
    if not isinstance(evidence,list) or not evidence:raise ValueError('Provide successful evidence action IDs from this run.')
    allowed={a['id']:a for a in store.actions(run['chat']) if a['created']>=run['started'] and a['status']=='done'}
    if any(id not in allowed for id in evidence):raise ValueError('Evidence must refer to successful actions in this run.')
    if not any(allowed[id]['name'] in ('read_file','search_files','memory_search','history_read','web_fetch','web_search') or '__' in allowed[id]['name'] for id in evidence):raise ValueError('Retrieve source evidence before completing this workflow.')
    verified=[]
    for value in outputs:
        if not isinstance(value,str):raise ValueError('Output paths must be strings.')
        path=workspace_path(value)
        if not path.is_file() or path.stat().st_size>20_000_000:raise ValueError('Output must be an existing file of at most 20 MB: '+value)
        data=path.read_bytes();verified.append({'path':value,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    state=set_state(store,name,'Completed','Output files read back and hashed; semantic correctness still requires review.',run)
    return {'status':'ok',**state,'outputs':verified,'evidence_actions':evidence}
