"""Desktop pairing client. Provider/session secrets never cross the local UI API."""
import asyncio,re,time
import httpx
from .config import BASE_DATA,DATA

ORIGIN='https://luminaria-identity.johnnycox4431836.workers.dev'
PROVIDERS=('google','github','discord')
SESSION=DATA/'identity-session.bin'
pending={}
lock=asyncio.Lock()

def save_session(path,token):
    if not re.fullmatch('[a-f0-9]{64}',token):raise ValueError('Invalid identity session')
    import win32crypt
    encrypted=win32crypt.CryptProtectData(token.encode(),'Luminaria identity session',None,None,None,1)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_bytes(encrypted);tmp.replace(path)

def read_session(path=None):
    path=path or SESSION
    if not path.exists():return None
    try:
        import win32crypt
        token=win32crypt.CryptUnprotectData(path.read_bytes(),None,None,None,1)[1].decode()
        if not re.fullmatch('[a-f0-9]{64}',token):raise ValueError()
        return token
    except Exception:raise ValueError('Saved sign-in could not be unlocked. Sign in again on this Windows account.') from None

def validate_user(user):
    if not isinstance(user,dict) or user.get('provider') not in PROVIDERS or not re.fullmatch(r'[a-f0-9-]{32,36}',str(user.get('id',''))):raise ValueError('Identity server returned an invalid account')
    return {'id':user['id'],'provider':user['provider'],'name':str(user.get('name','Account'))[:120],'expires':user.get('expires')}

async def status():
    result={'providers':[],'signed_in':False,'message':'Sign-in service is unavailable. Try again later.'}
    try:
        async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
            response=await client.get(ORIGIN+'/health');response.raise_for_status()
            available={p['id']:p.get('configured') is True for p in response.json().get('providers',[]) if isinstance(p,dict) and p.get('id') in PROVIDERS}
            result.update(providers=[{'id':p,'configured':available.get(p,False)} for p in PROVIDERS],message='Provider registration is still in progress.' if not any(available.values()) else 'Sign in in your browser. Your chats and files stay on this PC.')
            token=read_session()
            if token:
                response=await client.get(ORIGIN+'/session',headers={'Authorization':'Bearer '+token})
                if response.status_code==401:result['message']='Your sign-in expired or was revoked. Sign in again.'
                else:
                    response.raise_for_status();result.update(signed_in=True,user=validate_user(response.json()['user']),message='Session verified by the identity server.')
    except ValueError as error:result['message']=str(error)
    except (httpx.HTTPError,KeyError,TypeError,AttributeError):result['message']='Cannot verify sign-in right now. Check your connection and try again.'
    return result

async def start(provider):
    if provider not in PROVIDERS:raise ValueError('Choose Google, GitHub or Discord')
    async with lock:
        for key in list(pending):
            if pending[key]['deadline']<time.monotonic():pending.pop(key)
        if len(pending)>=3:raise ValueError('Finish an existing sign-in or wait for it to expire')
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            response=await client.post(ORIGIN+'/device/start',json={'provider':provider})
            if response.status_code==503:raise ValueError('This sign-in provider has not been configured by the publisher yet')
            response.raise_for_status();flow=response.json()
        id=flow.get('device_id','');secret=flow.get('device_secret','')
        if not re.fullmatch('[a-f0-9]{64}',id) or not re.fullmatch('[a-f0-9]{64}',secret) or flow.get('verification_uri')!=ORIGIN+'/authorize?device='+id:raise ValueError('Identity server returned an invalid sign-in link')
        expires=int(flow.get('expires_in',600))
        if not 1<=expires<=600:raise ValueError('Identity server returned an invalid expiry')
        pending[id]={'device_id':id,'device_secret':secret,'provider':provider,'deadline':time.monotonic()+expires,'next_poll':0}
        return {'flow_id':id,'url':flow['verification_uri'],'expires_in':expires,'interval':5}

async def poll(id):
    if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{64}',id):raise ValueError('Invalid sign-in request')
    async with lock:
        flow=pending.get(id)
        if not flow or flow['deadline']<time.monotonic():pending.pop(id,None);raise ValueError('Sign-in request expired. Start again.')
        if flow['next_poll']>time.monotonic():return {'status':'pending'}
        flow['next_poll']=time.monotonic()+5
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            response=await client.post(ORIGIN+'/device/poll',json={k:flow[k] for k in ('device_id','device_secret')})
            if response.status_code==202:return {'status':'pending'}
            if response.status_code==400:pending.pop(id,None);raise ValueError('Sign-in request expired or was already used. Start again.')
            response.raise_for_status();token=response.json().get('access_token','')
            if not re.fullmatch('[a-f0-9]{64}',token):raise ValueError('Identity server returned an invalid session')
            try:
                checked=await client.get(ORIGIN+'/session',headers={'Authorization':'Bearer '+token});checked.raise_for_status()
                if pending.get(id) is not flow:raise ValueError('Sign-in was cancelled')
                user=validate_user(checked.json()['user'])
                if user['provider']!=flow['provider']:raise ValueError('Sign-in provider did not match the request')
                from .profiles import identity_profile,select
                profile=identity_profile(user)
                save_session(BASE_DATA/'profiles'/profile['id']/'identity-session.bin',token)
                select(profile['id'])
            except Exception:
                try:await client.post(ORIGIN+'/logout',headers={'Authorization':'Bearer '+token})
                except httpx.HTTPError:pass
                raise
            finally:pending.pop(id,None)
        return {'status':'complete','profile':profile,'restart_required':True,'message':'Signed in. Restart Luminaria to open your account profile. Existing local chats remain in their original profile.'}

OFFLINE_GRACE=7*86400
GATE_OPEN=['/api/bootstrap','/api/gate','/api/events','/api/accounts','/api/identity/start','/api/identity/poll','/api/identity/cancel']
_gate={'checked':0.0,'result':None}

def required():
    from .profiles import registry
    return registry().get('require_sign_in') is True

def _verified_path():return DATA/'identity-verified.json'

def _last_verified():
    try:
        import json
        data=json.loads(_verified_path().read_text('utf-8'));return float(data['at']),str(data.get('name','your account'))
    except Exception:return None,None

def locked_now():
    """Synchronous view for background work: locked unless a recent check unlocked the app."""
    return required() and not (_gate['result'] or {}).get('unlocked')

def forget_gate():_gate.update(checked=0.0,result=None)

async def gate(force=False):
    if not required():return {'required':False,'unlocked':True}
    cached=_gate['result']
    if cached and not force and time.monotonic()-_gate['checked']<(600 if cached['unlocked'] else 15):return cached
    from .config import PROFILE_ID
    from .profiles import registry
    profile=next((p for p in registry()['profiles'] if p['id']==PROFILE_ID),None)
    result={'required':True,'unlocked':False,'profile':PROFILE_ID}
    if not profile or profile.get('provider')=='local':
        result['reason']='Sign in with Google, GitHub or Discord to use Luminaria on this PC.'
    else:
        try:token=read_session()
        except ValueError as error:token=None;result['reason']=str(error)
        if not token:result.setdefault('reason','Your sign-in for this profile is missing. Sign in again.')
        else:
            try:
                async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
                    response=await client.get(ORIGIN+'/session',headers={'Authorization':'Bearer '+token})
                if response.status_code==401:
                    _verified_path().unlink(missing_ok=True);result['reason']='Your sign-in expired or was revoked. Sign in again.'
                else:
                    response.raise_for_status();user=validate_user(response.json()['user'])
                    if user['id']!=profile.get('identity_id') or user['provider']!=profile.get('provider'):result['reason']='This sign-in belongs to a different account. Sign in again.'
                    else:
                        import json
                        _verified_path().write_text(json.dumps({'at':time.time(),'name':user['name']}),encoding='utf-8')
                        result.update(unlocked=True,user=user)
            except (httpx.HTTPError,KeyError,TypeError,ValueError,AttributeError):
                at,name=_last_verified()
                if at and 0<=time.time()-at<OFFLINE_GRACE:
                    days=int((time.time()-at)//86400)
                    result.update(unlocked=True,offline=True,reason=f'Offline. Signed in as {name}, last verified {"today" if days==0 else str(days)+" day"+("s" if days>1 else "")+" ago"}. Luminaria needs to verify again within 7 days.')
                else:result['reason']='Luminaria cannot reach the sign-in service to verify your account. Connect to the internet and try again.'
    _gate.update(checked=time.monotonic(),result=result)
    return result

async def set_required(enabled):
    from .profiles import registry,save
    data=registry()
    if enabled:
        data['require_sign_in']=True;save(data);forget_gate()
        check=await gate(force=True)
        if not check['unlocked'] or check.get('offline'):
            data.pop('require_sign_in',None);save(data);forget_gate()
            raise ValueError('Sign in and open your account profile first, while online, so you cannot be locked out. '+check.get('reason',''))
        return {'required':True}
    data.pop('require_sign_in',None);save(data);forget_gate()
    return {'required':False}

async def logout():
    forget_gate()
    token=read_session()
    if token:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            response=await client.post(ORIGIN+'/logout',headers={'Authorization':'Bearer '+token})
            if response.status_code!=401:response.raise_for_status()
        SESSION.unlink(missing_ok=True)
    _verified_path().unlink(missing_ok=True)
    return {'signed_out':True,'locked':required()}

def cancel(id):
    if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{64}',id):raise ValueError('Invalid sign-in request')
    pending.pop(id,None)
    return {'cancelled':True}
