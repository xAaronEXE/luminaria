"""Account-scoped offline-first sync. Portable data only; never credentials or approvals.
Each record uses a server revision. Both changed => conflict, never last-writer-wins.
"""
import asyncio,hashlib,json,os,re,time,uuid,zipfile,io
from pathlib import Path,PurePosixPath
import httpx
from . import identity,config,profiles,preferences
MAX_BLOB=20*1024*1024
PORTABLE_PREFS=set(preferences.DEFAULTS)-{'microphone'}
PORTABLE_CONFIG={'output_tokens','compact_ratio','compact_keep_turns'}
EXCLUDED={'.git','.env','.venv','node_modules','__pycache__','identity-session.bin','webview','sign-in-browser','.wrangler','cloud-sync-cache','cloud-sync-trash','cloud-sync-conflicts'}
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def fingerprint(value):return hashlib.sha256(canonical(value)).hexdigest()
def safe_path(root,name):
    if not isinstance(name,str) or not name or '\\' in name or len(name)>1024:raise ValueError('Unsafe synced file path')
    parts=PurePosixPath(name).parts
    if PurePosixPath(name).as_posix()!=name:raise ValueError('Synced paths must be canonical')
    if PurePosixPath(name).is_absolute() or any(p in ('..','.') or not p or ':' in p or p.endswith((' ','.')) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',p,re.I) for p in parts):raise ValueError('Unsafe synced file path')
    original_root=Path(root)
    if original_root.is_symlink() or getattr(original_root,'is_junction',lambda:False)():raise ValueError('Synced folders cannot be links')
    root=original_root.resolve();target=root.joinpath(*parts)
    for candidate in [target,*target.parents]:
        if candidate==root:break
        if candidate.is_symlink() or getattr(candidate,'is_junction',lambda:False)():raise ValueError('Synced files cannot follow links or junctions')
    if not target.resolve().is_relative_to(root):raise ValueError('Synced file escaped its folder')
    return target

def excluded(name):
    p=PurePosixPath(name)
    return any(part.lower() in EXCLUDED or part.lower().startswith('.env.') for part in p.parts) or p.suffix.lower() in {'.pem','.key','.pfx','.p12','.gguf','.safetensors','.sqlite','.sqlite3','.bin'} or p.name.lower() in {'credentials.json','token.json','secrets.json','config.json','profiles.json'}

class SyncConflict(Exception):pass
class BudgetPause(ValueError):pass
class CloudSync:
    def __init__(self,store,busy=lambda:False,protected=lambda:set(),changed=lambda:None):
        self.store=store;self.busy=busy;self.protected=protected;self.changed=changed;self.lock=asyncio.Lock();self.last={};self.pause_requested=False;self.client_factory=httpx.AsyncClient
    async def account(self):
        info=await identity.status()
        if not info.get('signed_in') or not info.get('account'):raise ValueError('Sign in online before syncing')
        account=info['account']['id'];entry=next((p for p in profiles.registry()['profiles'] if p['id']==config.PROFILE_ID),{})
        members={c['id'] for c in info.get('connections',[])}
        if entry.get('account_id')!=account and entry.get('identity_id') not in members:raise ValueError('Attach this local profile to your account before enabling sync')
        token=identity.read_session()
        if not token:raise ValueError('A valid sign-in session is required')
        return account,token
    def state(self,account):return self.store.setting('cloud_sync:'+account,{'enabled':False,'records':{},'conflicts':{},'last_sync':None})
    def save(self,account,state):
        if self.pause_requested:state['enabled']=False
        self.store.set_setting('cloud_sync:'+account,state)
    def check_scope(self,root):
        # A working folder that is a drive root, the home folder, or contains Luminaria's own data or credential folders
        # must never be uploaded wholesale.
        resolved=Path(root).resolve()
        if resolved.parent==resolved or resolved==Path.home().resolve() or any(p==resolved or p.is_relative_to(resolved) for p in config.protected_roots() if p!=resolved and not resolved.is_relative_to(p)):
            raise ValueError('Your working folder is too broad to sync: '+str(resolved)+'. Choose a smaller folder in Settings › Working folder, or leave sync off.')
    def roots(self):return {'workspace':Path(config.CONFIG['workspace']),'attachments':config.DATA/'attachments','tool-outputs':config.DATA/'tool-outputs'}
    def export(self):
        records={};blobs={};excluded_count=0;cache=config.DATA/'cloud-sync-cache';cache.mkdir(exist_ok=True)
        for chat in self.store.rows('SELECT * FROM chats'):
            if chat['archived']==2 and self.store.setting('cloud_deleted_chat:'+chat['id'],False):continue
            messages=self.store.rows('SELECT * FROM messages WHERE chat=? ORDER BY id',(chat['id'],));indices={m['id']:i for i,m in enumerate(messages)}
            summaries=[]
            for row in self.store.rows('SELECT * FROM summaries WHERE chat=? ORDER BY id',(chat['id'],)):
                if row['through_id'] in indices:summaries.append({'through':indices[row['through_id']],'content':row['content'],'created':row['created']})
            value={'chat':chat,'messages':[{'payload':json.loads(m['payload']),'created':m['created']} for m in messages],'summaries':summaries,'actions':self.store.rows('SELECT * FROM actions WHERE chat=? ORDER BY created,id',(chat['id'],))}
            # Compression bounds uploads; a canonical representation makes retries stable.
            import zlib
            content=zlib.compress(canonical(value),6)
            if len(content)>MAX_BLOB:raise ValueError('A conversation exceeds the current 20 MiB sync limit')
            digest=hashlib.sha256(content).hexdigest();cached=cache/digest
            if not cached.exists():cached.write_bytes(content)
            blobs[digest]=cached
            records['chat:'+chat['id']]={'blob':digest,'title':chat['title'],'messages':len(messages),'format':'chat-zlib-v1'}
        for memory in self.store.memory():records['memory:'+memory['id']]=memory
        prefs=self.store.setting('preferences',{});shared=preferences.load_shared_appearance()
        if shared is not None:prefs={**prefs,'appearance':shared,'theme_mode':shared['mode']}
        records['settings:portable']={'preferences':{k:v for k,v in prefs.items() if k in PORTABLE_PREFS},'config':{k:config.CONFIG[k] for k in PORTABLE_CONFIG if k in config.CONFIG}}
        entry=next((p for p in profiles.registry()['profiles'] if p['id']==config.PROFILE_ID),{})
        records['profile:workspace']={'name':entry.get('name','My workspace')}
        for scope,root in self.roots().items():
            if not root.exists():continue
            if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise ValueError('Choose a real working folder; linked folders are not synced')
            if scope=='workspace':self.check_scope(root)
            for directory,dirs,files in os.walk(root,followlinks=False):
                dirs[:]=[d for d in dirs if not excluded((Path(directory)/d).relative_to(root).as_posix()) and not (Path(directory)/d).is_symlink() and not getattr(Path(directory)/d,'is_junction',lambda:False)()]
                for filename in files:
                    path=Path(directory)/filename;relative=path.relative_to(root).as_posix()
                    if excluded(relative) or path.is_symlink():excluded_count+=1;continue
                    safe_path(root,relative)
                    if path.stat().st_size>MAX_BLOB:raise ValueError('File exceeds the current 20 MiB sync limit: '+relative)
                    before=path.stat();hashing=hashlib.sha256()
                    with path.open('rb') as stream:
                        while chunk:=stream.read(1024*1024):hashing.update(chunk)
                    after=path.stat()
                    if before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size:raise ValueError('A file changed during sync; it will retry when idle')
                    digest=hashing.hexdigest();blobs[digest]=path
                    key=hashlib.sha256((scope+':'+relative.casefold()).encode()).hexdigest()
                    if 'file:'+key in records:raise ValueError('Two file names differ only by case; resolve them before syncing')
                    records['file:'+key]={'scope':scope,'path':relative,'blob':digest,'size':after.st_size}
        for old in cache.iterdir():
            if old.is_file() and re.fullmatch('[a-f0-9]{64}',old.name) and old.name not in blobs and time.time()-old.stat().st_mtime>86400:old.unlink()
        return records,blobs,excluded_count
    async def status(self):
        account,token=await self.account();state=self.state(account)
        return {'enabled':state['enabled'],'last_sync':state.get('last_sync'),'error':self.last.get(account),'conflicts':[{'key':k,**v} for k,v in state.get('conflicts',{}).items()],'running':self.lock.locked(),'paused_until':state.get('not_before'),'storage':state.get('storage'),'max_file_bytes':MAX_BLOB,'excluded':'Credentials, environment files, key files, installed model weights, dependencies, links and device permissions stay local.'}
    async def enable(self,enabled):
        if not enabled:self.pause_requested=True
        if enabled:
            account,token=await self.account()
            async with self.client_factory(timeout=15,headers={'Authorization':'Bearer '+token,'User-Agent':'Luminaria-Sync'},follow_redirects=False) as client:cloud_status=(await self.request(client,'GET','status')).json()
        else:
            account=self.store.setting('cloud_sync_owner')
            if not account:return {'enabled':False,'conflicts':[]}
        if enabled:self.pause_requested=False
        state=self.state(account);state['enabled']=bool(enabled)
        if enabled:state['storage']=cloud_status
        self.save(account,state);self.store.set_setting('cloud_sync_owner',account)
        return {'enabled':state['enabled'],'conflicts':[],'last_sync':state.get('last_sync')}

    async def request(self,client,method,path,**kwargs):
        r=await client.request(method,identity.ORIGIN+'/sync/'+path,**kwargs)
        if r.status_code==409:raise SyncConflict('Another device changed this record')
        if r.status_code in (401,403):raise ValueError('Your cloud session expired or was revoked. Sign in again.')
        if r.status_code==429:raise BudgetPause('Cloud sync reached a free-use request budget and is paused. Your local data is safe.')
        if r.status_code==413:raise ValueError('The cloud storage or file-size limit was reached. Sync stopped; local data is safe. There is no paid fallback.')
        if r.status_code==503:
            try:disabled=r.json().get('code')=='sync_disabled'
            except (ValueError,AttributeError):disabled=False
            raise ValueError('Cloud uploads are paused by the service owner pending the free-plan check.' if disabled else 'Cloud sync storage is not configured yet')
        if not r.is_success:raise ValueError('Cloud sync request failed ('+str(r.status_code)+')')
        return r
    async def upload_blob(self,client,digest,content):
        async def chunks():
            with Path(content).open('rb') as stream:
                while chunk:=stream.read(1024*1024):yield chunk
        await self.request(client,'PUT','blobs/'+digest,content=chunks(),headers={'Content-Type':'application/octet-stream','Content-Length':str(Path(content).stat().st_size)})
    async def download_blob(self,client,data):
        digest=data.get('blob','')
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid cloud file reference')
        async with client.stream('GET',identity.ORIGIN+'/sync/blobs/'+digest) as r:
            if r.status_code!=200:raise ValueError('Could not download synced file')
            parts=[];size=0
            async for part in r.aiter_bytes():
                size+=len(part)
                if size>MAX_BLOB:raise ValueError('Cloud file exceeds download limit')
                parts.append(part)
        content=b''.join(parts)
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Cloud file failed integrity verification')
        return content
    def apply(self,key,data,deleted,content=None):
        kind,id=key.split(':',1)
        if kind=='memory':
            if deleted:self.store.execute('DELETE FROM memories WHERE id=?',(id,))
            else:
                if not isinstance(data.get('title'),str) or not isinstance(data.get('content'),str):raise ValueError('Invalid cloud memory')
                self.store.execute('INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?)',(id,data['title'],data['content'],str(data.get('source','synced')),float(data['updated'])))
        elif kind=='file':
            roots=self.roots()
            if data.get('scope') not in roots or excluded(data.get('path','')):raise ValueError('Cloud file is outside the permitted sync folders')
            expected=hashlib.sha256((data['scope']+':'+data['path'].casefold()).encode()).hexdigest()
            if expected!=id:raise ValueError('Cloud file identity does not match its path')
            path=safe_path(roots[data['scope']],data['path'])
            if path.is_dir():raise ValueError('Cloud file cannot replace a folder')
            if deleted:
                if path.exists():
                    trash=config.DATA/'cloud-sync-trash';trash.mkdir(exist_ok=True);os.replace(path,trash/(uuid.uuid4().hex+'-'+path.name))
            else:
                if len(content)!=data.get('size'):raise ValueError('Cloud file size mismatch')
                path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name('.'+path.name+'.sync-'+uuid.uuid4().hex)
                try:temp.write_bytes(content);os.replace(temp,path)
                finally:temp.unlink(missing_ok=True)
        elif kind=='settings' and not deleted:
            prefs=data.get('preferences',{});cfg=data.get('config',{})
            if set(prefs)-PORTABLE_PREFS or set(cfg)-PORTABLE_CONFIG:raise ValueError('Cloud settings contain device-only values')
            prefs=preferences.validate(prefs)
            for k,v in cfg.items():
                if isinstance(v,bool) or not isinstance(v,(int,float)):raise ValueError('Invalid cloud context setting')
                low,high={'output_tokens':(256,8192),'compact_ratio':(.4,.85),'compact_keep_turns':(1,32)}[k]
                if not low<=v<=high:raise ValueError('Cloud context setting is out of range')
            self.store.set_setting('preferences',self.store.setting('preferences',{})|prefs)
            if 'appearance' in prefs:preferences.save_shared_appearance(prefs['appearance'])
            updated=config.CONFIG|cfg;temp=config.CONFIG_PATH.with_suffix('.sync-tmp');temp.write_text(json.dumps(updated,indent=2),encoding='utf-8');os.replace(temp,config.CONFIG_PATH);config.CONFIG.update(cfg)
        elif kind=='profile' and not deleted:
            name=data.get('name')
            if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise ValueError('Invalid cloud profile name')
            registry=profiles.registry()
            for p in registry['profiles']:
                if p['id']==config.PROFILE_ID:p['name']=name.strip()
            profiles.save(registry)
        elif kind=='chat':
            if id in self.protected():raise SyncConflict('This conversation has a paused or active task; keep its local copy until finished')
            if deleted:
                # Cloud deletion is recoverable locally and never purges messages.
                self.store.execute('UPDATE chats SET archived=2 WHERE id=?',(id,));self.store.set_setting('cloud_deleted_chat:'+id,True);return
            import zlib
            decoder=zlib.decompressobj();raw=decoder.decompress(content,64*1024*1024+1)
            if len(raw)>64*1024*1024 or not decoder.eof:raise ValueError('Cloud conversation exceeds expansion limit')
            value=json.loads(raw);chat=value['chat']
            if chat['id']!=id or not isinstance(value.get('messages'),list):raise ValueError('Invalid cloud conversation')
            # Validate before touching the local transaction.
            for m in value['messages']:
                if not isinstance(m.get('payload'),dict) or m['payload'].get('role') not in ('user','assistant','tool','system'):raise ValueError('Invalid cloud message')
            with self.store.db:
                self.store.db.execute('INSERT INTO chats VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,created=excluded.created,updated=excluded.updated,archived=excluded.archived',(id,chat['title'],chat['created'],chat['updated'],chat['archived']))
                for table in ('messages','summaries','actions'):self.store.db.execute('DELETE FROM '+table+' WHERE chat=?',(id,))
                mapping=[]
                for m in value['messages']:mapping.append(self.store.db.execute('INSERT INTO messages(chat,payload,created) VALUES(?,?,?)',(id,json.dumps(m['payload']),m['created'])).lastrowid)
                for summary in value.get('summaries',[]):self.store.db.execute('INSERT INTO summaries(chat,through_id,content,created) VALUES(?,?,?,?)',(id,mapping[summary['through']],summary['content'],summary['created']))
                for action in value.get('actions',[]):
                    if action['chat']!=id:raise ValueError('Invalid cloud action scope')
                    status=action['status'] if action['status'] in ('done','error','denied','interrupted','cancelled','skipped') else 'interrupted'
                    self.store.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(action['id'],id,action['name'],action['args'],action['tier'],status,action['result'],action['created']))
            self.store.set_setting('cloud_deleted_chat:'+id,False)
        else:
            if deleted:raise ValueError('Cloud settings/profile deletion requires an explicit local reset')
            raise ValueError('Unknown cloud record')

    async def remote_records(self,client):
        rows={};after=''
        while True:
            result=(await self.request(client,'GET','records',params={'after':after})).json()
            for row in result['records']:rows[row['kind']+':'+row['id']]=row
            after=result.get('next')
            if not after:return rows
    async def preview(self):
        await self.account()
        if self.busy():raise ValueError('Finish the current task before preparing sync')
        records,blobs,excluded_count=self.export()
        return {'records':len(records),'files':sum(k.startswith('file:') for k in records),'chats':sum(k.startswith('chat:') for k in records),'memories':sum(k.startswith('memory:') for k in records),'bytes':sum(p.stat().st_size for p in blobs.values()),'excluded':excluded_count,'folders':[str(p) for p in self.roots().values()]}
    async def push(self,client,key,data,deleted,base,blobs):
        if data.get('blob') and not deleted:
            await self.upload_blob(client,data['blob'],blobs[data['blob']])
        if self.pause_requested:raise ValueError('Sync was turned off. Local changes remain queued.')
        value={'base':base,'mutation':fingerprint([key,base,data,deleted]),'data':data,'deleted':bool(deleted)}
        return (await self.request(client,'PUT','records/'+key.replace(':','/',1),json=value)).json()['version']
    async def run(self):
        if self.lock.locked():return {'message':'Sync is already running'}
        async with self.lock:
            account,token=await self.account();state=self.state(account)
            if not state['enabled']:return {'message':'Cloud sync is off'}
            if state.get('not_before',0)>time.time():return {'message':'Sync is paused to protect the free-use budget. It will check again later.'}
            if self.busy():return {'message':'Sync waits until the current task is idle'}
            try:
                # Export is bounded to the selected folders, with no model/credential state.
                local,blobs,excluded_count=self.export();changed=0;deferred=False;empty_workspace=not any(k.startswith(('chat:','file:','memory:')) for k in local)
                async with self.client_factory(timeout=60,headers={'Authorization':'Bearer '+token,'User-Agent':'Luminaria-Sync'},follow_redirects=False) as client:
                    cloud_status=(await self.request(client,'GET','status')).json();state['storage']=cloud_status;remote=await self.remote_records(client)
                    for key in sorted(set(local)|set(remote)|set(state['records'])):
                        if self.busy() or self.pause_requested:deferred=True;break
                        base=state['records'].get(key,{'version':0,'hash':None,'data':{}});present=key in local;data=local.get(key,base.get('data',{}));local_hash=fingerprint(data) if present else None
                        cloud_version=remote.get(key,{}).get('version',0);cloud_changed=cloud_version>base['version'];local_changed=local_hash!=base['hash']
                        if not base['version'] and empty_workspace and key.startswith(('settings:','profile:')):local_changed=False
                        if key in state['conflicts']:continue
                        if cloud_changed:
                            row=(await self.request(client,'GET','records/'+key.replace(':','/',1))).json();cloud_data=row['data'];cloud_hash=None if row['deleted'] else fingerprint(cloud_data)
                            if local_hash==cloud_hash:
                                state['records'][key]={'version':row['version'],'hash':cloud_hash,'data':cloud_data};self.save(account,state);continue
                            if local_changed or key.startswith('chat:') and key.split(':',1)[1] in self.protected():
                                state['conflicts'][key]={'version':row['version'],'local_hash':local_hash,'title':str(data.get('title') or data.get('path') or key)[:160]};self.save(account,state);continue
                            prior_changes=self.store.db.total_changes
                            content=await self.download_blob(client,cloud_data) if cloud_data.get('blob') and not row['deleted'] else None
                            if self.busy() or self.pause_requested or prior_changes!=self.store.db.total_changes:raise ValueError('Local data changed during download; sync will retry safely')
                            if key.startswith('file:'):
                                target=safe_path(self.roots()[cloud_data['scope']],cloud_data['path'])
                                if not present and target.exists():raise ValueError('A local file was created during download; sync will preserve it')
                                if present:
                                    path=blobs.get(local[key].get('blob'))
                                    if not path or not path.is_file() or path.stat().st_size>MAX_BLOB or hashlib.sha256(path.read_bytes()).hexdigest()!=local[key]['blob']:raise ValueError('A local file changed during sync; retrying will preserve both versions')
                            try:self.apply(key,cloud_data,row['deleted'],content)
                            except SyncConflict:
                                state['conflicts'][key]={'version':row['version'],'local_hash':local_hash,'title':key};self.save(account,state);continue
                            state['records'][key]={'version':row['version'],'hash':cloud_hash,'data':cloud_data};changed+=1;self.save(account,state)
                        elif local_changed:
                            try:version=await self.push(client,key,data,not present,base['version'],blobs)
                            except SyncConflict:
                                state['conflicts'][key]={'version':cloud_version,'local_hash':local_hash,'title':str(data.get('title') or data.get('path') or key)[:160]};self.save(account,state);continue
                            state['records'][key]={'version':version,'hash':local_hash,'data':data};self.save(account,state)
                    state['last_sync']=state.get('last_sync') if deferred else time.time();state['excluded']=excluded_count;self.save(account,state);self.last.pop(account,None)
                if changed:self.changed()
                return {'message':'Sync paused for the current task' if deferred else 'Sync finished','conflicts':len(state['conflicts']),'downloaded':changed}
            except Exception as error:
                if isinstance(error,BudgetPause):state['not_before']=time.time()+3600;self.save(account,state)
                self.last[account]=str(error) if isinstance(error,(ValueError,SyncConflict)) else 'Cloud sync is temporarily unavailable. Local data is safe; retry later.'
                raise ValueError(self.last[account]) from None
    async def resolve(self,key,choice):
        if choice not in ('local','cloud'):raise ValueError('Choose which version to keep')
        if self.lock.locked() or self.busy():raise ValueError('Wait for the current task or sync to finish')
        async with self.lock:
            account,token=await self.account();state=self.state(account);conflict=state['conflicts'].get(key)
            if not conflict:raise ValueError('Conflict no longer exists')
            local,blobs,_=self.export();value=local.get(key);current=fingerprint(value) if value is not None else None
            if current!=conflict['local_hash']:raise ValueError('The local copy changed again. Review it before resolving.')
            async with self.client_factory(timeout=60,headers={'Authorization':'Bearer '+token,'User-Agent':'Luminaria-Sync'},follow_redirects=False) as client:
                row=(await self.request(client,'GET','records/'+key.replace(':','/',1))).json()
                if row['version']!=conflict['version']:
                    state['conflicts'][key]['version']=row['version'];self.save(account,state);raise ValueError('The cloud copy changed again. Review the current versions before choosing.')
                # Keep a durable local recovery copy before an explicit resolution.
                folder=config.DATA/'cloud-sync-conflicts';folder.mkdir(exist_ok=True);backup=folder/(uuid.uuid4().hex+'.json')
                backup.write_bytes(canonical({'key':key,'local':value,'cloud':row}))
                if value and value.get('blob'):
                    import shutil
                    shutil.copy2(blobs[value['blob']],folder/(backup.stem+'.blob'))
                if choice=='local':
                    data=value if value is not None else row['data'];version=await self.push(client,key,data,value is None,row['version'],blobs);hash_value=current
                else:
                    content=await self.download_blob(client,row['data']) if row['data'].get('blob') and not row['deleted'] else None
                    self.apply(key,row['data'],row['deleted'],content);data=row['data'];version=row['version'];hash_value=None if row['deleted'] else fingerprint(data)
                state['records'][key]={'version':version,'hash':hash_value,'data':data};del state['conflicts'][key];self.save(account,state);self.changed()
            return {'message':'Conflict resolved; a recovery copy was saved on this PC'}
