"""First-use setup scoped to a server-verified account and local profile."""
from pathlib import Path
from . import identity,profiles,config,preferences

async def verified():
    info=await identity.status()
    if not info.get('signed_in'):raise ValueError('Sign in before setting up your workspace')
    account=(info.get('account') or info['user'])['id']
    return info,account

async def status(store):
    info,account=await verified()
    saved=store.setting('onboarding_accounts',{})
    profile=next((p for p in profiles.registry()['profiles'] if p['id']==config.PROFILE_ID),{})
    return {'completed':saved.get(account) is True,'name':profile.get('name') or info['user']['name'],
            'workspace':config.CONFIG['workspace'],'model':config.CONFIG.get('model'),
            'appearance':preferences.load_shared_appearance() or store.setting('preferences',{}).get('appearance',preferences.DEFAULTS['appearance'])}

async def complete(store,payload):
    _,account=await verified()
    name=str(payload.get('name','')).strip()
    if not name or len(name)>60:raise ValueError('Workspace name must contain 1–60 characters')
    mode=payload.get('mode')
    if mode not in ('light','dark','system'):raise ValueError('Choose light, dark or follow system')
    workspace=Path(str(payload.get('workspace',''))).expanduser().resolve()
    if not workspace.is_dir():raise ValueError('Choose an existing working folder')
    data=profiles.registry();profile=next(p for p in data['profiles'] if p['id']==config.PROFILE_ID)
    appearance=preferences.load_shared_appearance() or store.setting('preferences',{}).get('appearance',preferences.DEFAULTS['appearance'])
    appearance=preferences.appearance({**appearance,'mode':mode})
    config.save_config({'workspace':str(workspace)})
    prefs=store.setting('preferences',{});prefs['appearance']=appearance
    store.set_setting('preferences',prefs);preferences.save_shared_appearance(appearance)
    profile['name']=name;profiles.save(data)
    saved=store.setting('onboarding_accounts',{});saved[account]=True
    store.set_setting('onboarding_accounts',saved)
    return {'completed':True}
