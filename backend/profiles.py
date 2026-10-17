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
    profile=next((p for p in data['profiles'] if p['id']==id),None)
    if not profile: raise ValueError('Profile not found')
    if data.get('require_sign_in') is True and profile.get('provider')=='local' and not profile.get('account_id'): raise ValueError('Sign-in is required on this PC, so local profiles that are not attached to your account cannot be opened. Attach it in Profile → Local profiles, or turn off Require sign-in first.')
    data['selected']=id; save(data)
    return {'restart_required':True,'message':'Close all Luminaria windows and reopen to use this profile.'}

def identity_profile(user):
    data=registry()
    for item in data['profiles']:
        if item.get('identity_id')==user['id'] and item.get('provider')==user['provider']:return item
    if len(data['profiles'])>=20:raise ValueError('Profile limit reached')
    item={'id':uuid.uuid4().hex,'name':user['name'][:60],'provider':user['provider'],'identity_id':user['id']}
    data['profiles'].append(item);save(data);return item

CHOICES=('attach','separate','untouched')

def migrate(id,choice,account=None):
    """Record an explicit choice for one local profile. Data is never moved or merged."""
    if choice not in CHOICES:raise ValueError('Choose attach, keep separate or leave untouched')
    data=registry()
    profile=next((p for p in data['profiles'] if p['id']==id),None)
    if not profile:raise ValueError('Profile not found')
    if profile.get('provider')!='local':raise ValueError('Only local profiles need a choice; this one already belongs to a sign-in')
    if choice=='attach':
        if not account or not account.get('id'):raise ValueError('Sign in before attaching a profile to your account')
        profile['account_id']=str(account['id']);profile['migration']='attached'
    elif choice=='separate':
        if data.get('require_sign_in') is True and id==PROFILE_ID:raise ValueError('This profile is open and sign-in is required, so keeping it separate would lock you out. Turn off required sign-in first.')
        profile.pop('account_id',None);profile['migration']='separate'
    else:
        profile.pop('account_id',None);profile.pop('migration',None)
    save(data)
    return {'id':id,'choice':choice,'message':{'attach':'Attached to your account. Its chats and files stay exactly where they are.','separate':'Kept separate. It stays a local profile on this PC.','untouched':'No choice recorded. Nothing about this profile changed.'}[choice]}
