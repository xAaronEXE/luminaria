"""Offline-first, end-to-end encrypted sync. Portable data only; never credentials or approvals.
Each record has a revision. Both changed => conflict, never last-writer-wins.
Sync is off until the user sets it up. Data is encrypted on this PC with the sync key (sync_secure.py) and stored
where the user chooses: a folder they already sync (OneDrive, Google Drive, Dropbox, a network share) or a sync service.
"""
import asyncio,contextlib,hashlib,json,os,re,time,uuid,zipfile,io
from pathlib import Path,PurePosixPath
import httpx
from . import identity,config,profiles,preferences,sync_secure
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

    # ---- setup: where encrypted data lives, and the key ----
    def settings(self):
        value=config.CONFIG.get('sync') or {}
        return {'mode':value.get('mode','off'),'folder':value.get('folder',''),'service':value.get('service','')}
    def key(self):
        from .integrations import read_secrets
        text=read_secrets('sync_key').get('key','')
        return sync_secure.parse_key(text) if text else None
    def setup(self,mode,folder='',key_text=''):
        """Choose where synced data lives. A new sync key is made unless the user enters the key from another device."""
        from .integrations import write_secrets
        if mode not in ('folder','service'):raise ValueError('Choose a sync folder or a sync service')
        if mode=='folder':
            target=Path(str(folder or '')).expanduser()
            if not str(folder).strip() or not target.is_dir():raise ValueError('Choose a folder that exists, for example your OneDrive folder')
            target=target.resolve()
            if any(target==p or target.is_relative_to(p) for p in config.protected_roots()):raise ValueError('That folder is off limits. Choose your OneDrive, Google Drive or Dropbox folder.')
        key=sync_secure.parse_key(key_text) if str(key_text or '').strip() else (self.key() or sync_secure.new_key())
        write_secrets('sync_key',{'key':sync_secure.format_key(key)})
        config.save_config({'sync':{'mode':mode,'folder':str(target) if mode=='folder' else '','service':''}})
        space=sync_secure.key_id(key);self.store.set_setting('cloud_sync_owner',space)
        state=self.state(space);state['enabled']=True;self.pause_requested=False;self.save(space,state)
        return {'enabled':True,'mode':mode,'key':sync_secure.format_key(key)}
    def show_key(self):
        key=self.key()
        if not key:raise ValueError('Sync is not set up on this PC')
        return {'key':sync_secure.format_key(key)}
    async def account(self):
        """(space id, None). The space is derived from the sync key, so every device with the key shares it."""
        mode=self.settings()['mode']
        if mode=='off':raise ValueError('Sync is off. Set it up in Settings › Cloud sync.')
        key=self.key()
        if not key:raise ValueError('This PC has no sync key yet. Set up sync again, or enter the key from your other device.')
        return sync_secure.key_id(key),None
    @contextlib.asynccontextmanager
    async def open(self):
        """The encrypted store for the chosen place."""
        settings=self.settings();key=self.key();space=sync_secure.key_id(key)
        if settings['mode']=='folder':
            yield sync_secure.EncryptedStore(key,sync_secure.FolderStore(settings['folder'],space));return
        info=await identity.status();token=identity.read_session()
        if not info.get('signed_in') or not token:raise ValueError('Sign in to your sync service first')
        async with self.client_factory(timeout=60,headers={'Authorization':'Bearer '+token,'User-Agent':'Luminaria-Sync'},follow_redirects=False) as client:
            yield sync_secure.EncryptedStore(key,sync_secure.ServiceStore(client,identity.ORIGIN))

    def state(self,account):return self.store.setting('cloud_sync:'+account,{'enabled':False,'records':{},'conflicts':{},'last_sync':None})
    def save(self,account,state):
        if self.pause_requested:state['enabled']=False
        self.store.set_setting('cloud_sync:'+account,state)
    def check_scope(self,root):
        # A default folder that is a drive root, the home folder, or contains Luminaria's own data or credential folders
        # must never be uploaded wholesale.
        resolved=Path(root).resolve()
        if resolved.parent==resolved or resolved==Path.home().resolve() or any(p==resolved or p.is_relative_to(resolved) for p in config.protected_roots() if p!=resolved and not resolved.is_relative_to(p)):
            raise ValueError('Your default folder is too broad to sync: '+str(resolved)+'. Choose a smaller folder in Settings › Default folder, or leave sync off.')
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
            if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise ValueError('Choose a real default folder; linked folders are not synced')
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
        account,_=await self.account();state=self.state(account);settings=self.settings()
        return {'enabled':state['enabled'],'mode':settings['mode'],'folder':settings['folder'],'last_sync':state.get('last_sync'),'error':self.last.get(account),
                'conflicts':[{'key':k,**v} for k,v in state.get('conflicts',{}).items()],'running':self.lock.locked(),'paused_until':state.get('not_before'),
                'storage':state.get('storage'),'excluded':state.get('excluded',0),'encrypted':True}
    async def enable(self,enabled):
        if not enabled:
            self.pause_requested=True
            account=self.store.setting('cloud_sync_owner')
            if not account:return {'enabled':False,'conflicts':[]}
        else:
            account,_=await self.account();self.pause_requested=False
        state=self.state(account);state['enabled']=bool(enabled);self.save(account,state);self.store.set_setting('cloud_sync_owner',account)
        return {'enabled':state['enabled'],'conflicts':[],'last_sync':state.get('last_sync')}
    async def preview(self):
        await self.account()
        if self.busy():raise ValueError('Finish the current task before preparing sync')
        records,blobs,excluded_count=self.export()
        return {'records':len(records),'files':sum(k.startswith('file:') for k in records),'chats':sum(k.startswith('chat:') for k in records),'memories':sum(k.startswith('memory:') for k in records),'bytes':sum(p.stat().st_size for p in blobs.values()),'excluded':excluded_count}

    def apply(self,key,data,deleted,content=None):
        kind,id=key.split(':',1)
        if kind=='memory':
            if deleted:self.store.execute('DELETE FROM memories WHERE id=?',(id,))
            else:
                if not isinstance(data.get('title'),str) or not isinstance(data.get('content'),str):raise ValueError('Invalid cloud memory')
                self.store.execute('INSERT OR REPLACE INTO memories VALUES(?,?,?,?,?)',(id,data['title'],data['content'],str(data.get('source','synced')),float(data['updated'])))
                from .memory_file import ROW,from_sync
                if id==ROW: from_sync(data['content'])  # MEMORY.md travels as one record and is written back to disk
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
                    self.store.db.execute('INSERT INTO actions(id,chat,name,args,tier,status,result,created) VALUES(?,?,?,?,?,?,?,?)',(action['id'],id,action['name'],action['args'],action['tier'],status,action['result'],action['created']))
            self.store.set_setting('cloud_deleted_chat:'+id,False)
        else:
            if deleted:raise ValueError('Cloud settings/profile deletion requires an explicit local reset')
            raise ValueError('Unknown cloud record')

    async def remote_view(self,store,state,local):
        """Remote records by local key. Records another device added are opened once to learn their local name."""
        rows=await store.records();key=self.key();known={}
        for name in set(local)|set(state['records']):known[sync_secure.remote_name(key,name)]=name
        fetched={}
        for remote,meta in rows.items():
            if remote in known:continue
            row=await store.get(remote)
            if row and sync_secure.remote_name(key,row['key'])==remote:known[remote]=row['key'];fetched[row['key']]=row
        return {known[r]:m for r,m in rows.items() if r in known},fetched
    async def run(self):
        if self.lock.locked():return {'message':'Sync is already running'}
        async with self.lock:
            account,_=await self.account();state=self.state(account);key=self.key()
            if not state['enabled']:return {'message':'Sync is off'}
            if state.get('not_before',0)>time.time():return {'message':'Sync is paused to protect the free-use budget. It will check again later.'}
            if self.busy():return {'message':'Sync waits until the current task is idle'}
            try:
                local,blobs,excluded_count=self.export();changed=0;deferred=False;empty_workspace=not any(k.startswith(('chat:','file:','memory:')) for k in local)
                async with self.open() as store:
                    state['storage']=await store.status();remote,fetched=await self.remote_view(store,state,local)
                    for name in sorted(set(local)|set(remote)|set(state['records'])):
                        if self.busy() or self.pause_requested:deferred=True;break
                        base=state['records'].get(name,{'version':0,'hash':None,'data':{}});present=name in local;data=local.get(name,base.get('data',{}));local_hash=fingerprint(data) if present else None
                        cloud_version=remote.get(name,{}).get('version',0);cloud_changed=cloud_version>base['version'];local_changed=local_hash!=base['hash']
                        if not base['version'] and empty_workspace and name.startswith(('settings:','profile:')):local_changed=False
                        if name in state['conflicts']:continue
                        if cloud_changed:
                            row=fetched.get(name) or await store.get(sync_secure.remote_name(key,name))
                            cloud_data=row['data'];cloud_hash=None if row['deleted'] else fingerprint(cloud_data)
                            if local_hash==cloud_hash:
                                state['records'][name]={'version':row['version'],'hash':cloud_hash,'data':cloud_data};self.save(account,state);continue
                            if local_changed or name.startswith('chat:') and name.split(':',1)[1] in self.protected():
                                state['conflicts'][name]={'version':row['version'],'local_hash':local_hash,'title':str(data.get('title') or data.get('path') or name)[:160]};self.save(account,state);continue
                            prior_changes=self.store.db.total_changes
                            content=await store.get_blob(row) if cloud_data.get('blob') and not row['deleted'] else None
                            if self.busy() or self.pause_requested or prior_changes!=self.store.db.total_changes:raise ValueError('Local data changed during download; sync will retry safely')
                            if name.startswith('file:'):
                                target=safe_path(self.roots()[cloud_data['scope']],cloud_data['path'])
                                if not present and target.exists():raise ValueError('A local file was created during download; sync will preserve it')
                            try:self.apply(name,cloud_data,row['deleted'],content)
                            except SyncConflict:
                                state['conflicts'][name]={'version':row['version'],'local_hash':local_hash,'title':name};self.save(account,state);continue
                            state['records'][name]={'version':row['version'],'hash':cloud_hash,'data':cloud_data};changed+=1;self.save(account,state)
                        elif local_changed:
                            if self.pause_requested:raise ValueError('Sync was turned off. Local changes remain queued.')
                            try:version=await store.put(name,base['version'],data,not present,blobs.get(data.get('blob')) if present else None,lambda:not self.pause_requested)
                            except sync_secure.Conflict:
                                state['conflicts'][name]={'version':cloud_version,'local_hash':local_hash,'title':str(data.get('title') or data.get('path') or name)[:160]};self.save(account,state);continue
                            state['records'][name]={'version':version,'hash':local_hash,'data':data};self.save(account,state)
                    state['last_sync']=state.get('last_sync') if deferred else time.time();state['excluded']=excluded_count;self.save(account,state);self.last.pop(account,None)
                if changed:self.changed()
                return {'message':'Sync paused for the current task' if deferred else 'Sync finished','conflicts':len(state['conflicts']),'downloaded':changed}
            except Exception as error:
                if isinstance(error,BudgetPause) or 'free-use limit' in str(error):state['not_before']=time.time()+3600;self.save(account,state)
                self.last[account]=str(error) if isinstance(error,(ValueError,SyncConflict,sync_secure.Conflict)) else 'Sync is temporarily unavailable. Local data is safe; retry later.'
                raise ValueError(self.last[account]) from None
    async def resolve(self,name,choice):
        if choice not in ('local','cloud'):raise ValueError('Choose which version to keep')
        if self.lock.locked() or self.busy():raise ValueError('Wait for the current task or sync to finish')
        async with self.lock:
            account,_=await self.account();state=self.state(account);conflict=state['conflicts'].get(name);key=self.key()
            if not conflict:raise ValueError('Conflict no longer exists')
            local,blobs,_=self.export();value=local.get(name);current=fingerprint(value) if value is not None else None
            if current!=conflict['local_hash']:raise ValueError('The local copy changed again. Review it before resolving.')
            async with self.open() as store:
                row=await store.get(sync_secure.remote_name(key,name))
                if not row or row['version']!=conflict['version']:
                    state['conflicts'][name]['version']=(row or {}).get('version',0);self.save(account,state);raise ValueError('The synced copy changed again. Review the current versions before choosing.')
                # Keep a durable local recovery copy before an explicit resolution.
                folder=config.DATA/'cloud-sync-conflicts';folder.mkdir(exist_ok=True);backup=folder/(uuid.uuid4().hex+'.json')
                backup.write_bytes(canonical({'key':name,'local':value,'cloud':row}))
                if value and value.get('blob'):
                    import shutil
                    shutil.copy2(blobs[value['blob']],folder/(backup.stem+'.blob'))
                if choice=='local':
                    data=value if value is not None else row['data'];version=await store.put(name,row['version'],data,value is None,blobs.get(data.get('blob')) if value else None);hash_value=current
                else:
                    content=await store.get_blob(row) if row['data'].get('blob') and not row['deleted'] else None
                    self.apply(name,row['data'],row['deleted'],content);data=row['data'];version=row['version'];hash_value=None if row['deleted'] else fingerprint(data)
                state['records'][name]={'version':version,'hash':hash_value,'data':data};del state['conflicts'][name];self.save(account,state);self.changed()
            return {'message':'Conflict resolved; a recovery copy was saved on this PC'}
