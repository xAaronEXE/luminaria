"""Local profile registry. Switching takes effect at restart, never during a run."""
import json, uuid
from .config import BASE_DATA, PROFILE_ID

PATH=BASE_DATA/'profiles.json'
def registry():
    return json.loads(PATH.read_text('utf-8')) if PATH.exists() else {'selected':'local','profiles':[{'id':'local','name':'Personal','provider':'local'}]}

def save(data):
    tmp=PATH.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2),encoding='utf-8'); tmp.replace(PATH)

def status():
    data=registry()
    return {**data,'active':PROFILE_ID}

def create(name):
    name=str(name).strip()
    if not name or len(name)>60: raise ValueError('Profile name must contain 1–60 characters')
    data=registry()
    if len(data['profiles'])>=20: raise ValueError('Profile limit reached')
    item={'id':uuid.uuid4().hex,'name':name,'provider':'local'}
    data['profiles'].append(item); save(data); return item

def select(id):
    data=registry()
    if not any(p['id']==id for p in data['profiles']): raise ValueError('Profile not found')
    data['selected']=id; save(data)
    return {'restart_required':True,'message':'Close all Luminaria windows and reopen to use this profile.'}

def identity_profile(user):
    data=registry()
    for item in data['profiles']:
        if item.get('identity_id')==user['id'] and item.get('provider')==user['provider']:return item
    if len(data['profiles'])>=20:raise ValueError('Profile limit reached')
    item={'id':uuid.uuid4().hex,'name':user['name'][:60],'provider':user['provider'],'identity_id':user['id']}
    data['profiles'].append(item);save(data);return item
