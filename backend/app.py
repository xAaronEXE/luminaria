import asyncio, base64, contextlib, json, os, re, secrets, time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from .config import ROOT, DATA, CONFIG, save_config, workspace_path
from .store import Store,uid,now
from .connectors import Connector
from .tools import Toolbox
from .engine import Engine
from .usage import Usage

TOKEN=secrets.token_urlsafe(32)
store=Store(DATA/'studio.sqlite3')
usage=Usage(store)
subscribers=set(); connectors={}; engine=None; benchmarking=False

def broadcast(event):
    for queue in tuple(subscribers):
        if not queue.full(): queue.put_nowait(event)

def sync_busy():
    workflow=globals().get('file_workflows')
    return benchmarking or bool(engine and any(not t.done() for t in engine.tasks.values())) or bool(workflow and workflow.busy())
def sync_changed():
    store.set_setting('cloud_sync_updated',time.time())
    if engine:
        for chat,run in list(engine.runs.items()):
            if run.get('finished'):engine.runs.pop(chat,None)
    broadcast({'type':'cloud_sync_updated'})
from .cloud_sync import CloudSync
cloud_sync=CloudSync(store,sync_busy,lambda:{k for k,v in (engine.runs.items() if engine else []) if not v.get('finished')},sync_changed)
async def sync_loop():
    while True:
        await asyncio.sleep(300)
        owner=store.setting('cloud_sync_owner')
        if owner and cloud_sync.state(owner)['enabled']:
            try:await cloud_sync.run()
            except ValueError:pass # visible in Cloud sync status; never discard local work

async def scheduler():
    while True:
        await asyncio.sleep(10)
        if benchmarking: continue
        due=store.rows('SELECT * FROM schedules WHERE enabled=1 AND next_run<=?',(now(),))
        if due:
            from .identity import gate
            if not (await gate())['unlocked']: continue
        for row in due:
            chat=store.create_chat('Scheduled: '+row['title'])
            store.add(chat,{'role':'user','content':row['prompt']})
            store.execute('UPDATE schedules SET next_run=? WHERE id=?',(now()+row['interval'],row['id']))
            engine.start(chat)

@asynccontextmanager
async def lifespan(app):
    global engine
    for name,config in CONFIG.get('mcp',{}).items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,30}',name): continue
        c=Connector(name,config,broadcast); connectors[name]=c; c.start()
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    conn=await aiosqlite.connect(DATA/'checkpoints.sqlite3')
    saver=AsyncSqliteSaver(conn); await saver.setup()
    engine=Engine(store,Toolbox(store,connectors),broadcast,saver)
    async def install_connector(name,config):
        configs=CONFIG.get('mcp',{}).copy(); configs[name]=config
        save_config({'mcp':configs}); await restart_connector(name,config)
        # First start downloads the package; give it time so the assistant can use it in the same task.
        c=connectors.get(name)
        if c:
            with contextlib.suppress(asyncio.TimeoutError): await asyncio.wait_for(c.ready.wait(),180)
            if c.status!='connected': raise ValueError(f'The connector was added but has not started ({c.status}). It may need an account key; check Settings › Integrations.')
    engine.tools.connector_installer=install_connector
    await engine.restore()
    with contextlib.suppress(Exception):
        from .updates import cleanup
        await asyncio.to_thread(cleanup)
    task=asyncio.create_task(scheduler());sync_task=asyncio.create_task(sync_loop())
    from . import sharing
    await sharing.resume()
    yield
    with contextlib.suppress(Exception): await sharing.shutdown()
    sync_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):await sync_task
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError): await task
    if tuning is not None: await tuning.cancel()
    if file_workflows is not None: await file_workflows.close()
    await engine.close()
    await conn.close()
    for c in connectors.values(): await c.close()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

@app.middleware('http')
async def local_only(request,call_next):
    host=request.headers.get('host',''); port=os.environ.get('STUDIO_PORT','3210')
    hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
    if host not in hosts: return JSONResponse({'error':'Local host required'},403)
    origin=request.headers.get('origin')
    if origin and origin not in {'http://'+h for h in hosts}: return JSONResponse({'error':'Foreign origin blocked'},403)
    if request.url.path.startswith('/api/') and request.url.path!='/api/bootstrap':
        if not secrets.compare_digest(request.headers.get('x-studio-token',''),TOKEN): return JSONResponse({'error':'Session token required'},403)
        from .identity import GATE_OPEN,gate,required
        if required() and request.url.path not in GATE_OPEN and not (await gate())['unlocked']:
            return JSONResponse({'error':'Sign in to use Luminaria','locked':True},423)
    # Base64 adds a third, so a 25 MB document needs about 34 MB of request body.
    path=request.url.path
    limit=35_000_000 if path=='/api/attachments' or (path.startswith('/api/imports/') and path.endswith('/files')) else 12_000_000
    declared=request.headers.get('content-length')
    if declared:
        if not declared.isdigit(): return JSONResponse({'error':'Bad request'},400)
        if int(declared)>limit: return JSONResponse({'error':'Request too large'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
    return response

@app.exception_handler(ValueError)
async def value_error(request,exc): return JSONResponse({'error':str(exc)},400)

def require_chat(id):
    if not store.rows('SELECT id FROM chats WHERE id=?',(id,)): raise HTTPException(404,'Task not found')

@app.get('/api/bootstrap')
async def bootstrap(): return {'token':TOKEN,'version':CONFIG['version'],'name':'Luminaria'}

@app.get('/api/state')
async def state(chat:str=''):
    if chat: require_chat(chat)
    return {'cloud_sync_updated':store.setting('cloud_sync_updated',0),'chats':store.chats(),'chat':chat,'messages':store.messages(chat) if chat else [],'changes':_changes(chat),'actions':store.actions(chat) if chat else [],'summary':store.summary(chat) if chat else None,'summaries':store.rows('SELECT id,through_id,created FROM summaries WHERE chat=? ORDER BY id',(chat,)) if chat else [],'run':engine.public_run(chat),'context':store.setting('context:'+chat,{}),'plan':store.setting('plan:'+chat,None) if chat else None,'brief':brief_summary(chat) if chat else None,'orchestration':{'router':CONFIG.get('orchestrator_model',''),'enabled':bool(CONFIG.get('orchestrator_model')) and CONFIG.get('orchestration_enabled',True)},'memories':memory_entries(),'schedules':store.rows('SELECT * FROM schedules ORDER BY next_run'),'workspace':CONFIG['workspace'],'model':CONFIG['model'],'context_limit':CONFIG['context'],'connectors':{n:{'status':c.status,'tools':len(c.tools)} for n,c in connectors.items()},'tool_count':len(engine.tools.catalog()),'active_runs':[{'chat':k,'phase':v['phase']} for k,v in engine.runs.items() if not v.get('finished')]}

@app.get('/api/chats/{id}/work')
async def work_events(id:str,runs:int=12):
    require_chat(id); return {'chat':id,'events':engine.worklog.events(id,runs),'active_run':(engine.public_run(id) or {}).get('id') if not (engine.public_run(id) or {}).get('finished') else None}

@app.get('/api/chats/{id}/summaries/{summary_id}')
async def summary_evidence(id:str,summary_id:int):
    require_chat(id)
    rows=store.rows('SELECT id,through_id,content,created FROM summaries WHERE chat=? AND id=?',(id,summary_id))
    if not rows:raise HTTPException(404,'Summary not found in this chat')
    return rows[0]

@app.get('/api/events')
async def events(request:Request):
    queue=asyncio.Queue(maxsize=200); subscribers.add(queue)
    async def stream():
        try:
            yield 'data: '+json.dumps({'type':'ready'})+'\n\n'
            while not await request.is_disconnected():
                try: event=await asyncio.wait_for(queue.get(),15)
                except asyncio.TimeoutError: yield ': heartbeat\n\n'; continue
                yield 'data: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        finally: subscribers.discard(queue)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

@app.post('/api/sessions')
@app.post('/api/chats')
async def create_chat(request:Request):
    body=await request.json(); id=store.create_chat(str(body.get('title','New task'))[:160]); broadcast({'type':'changed'}); return {'id':id}

@app.patch('/api/chats/{id}')
async def edit_chat(id:str,request:Request):
    require_chat(id); body=await request.json()
    if 'title' in body: store.execute('UPDATE chats SET title=? WHERE id=?',(str(body['title'])[:160],id))
    if 'archived' in body:
        if id in engine.tasks and not engine.tasks[id].done(): raise ValueError('Stop the task before archiving')
        store.execute('UPDATE chats SET archived=? WHERE id=?',(bool(body['archived']),id))
    broadcast({'type':'changed'}); return {'ok':True}

@app.get('/api/search')
async def search(q:str=''):
    return store.rows('SELECT DISTINCT c.id,c.title FROM chats c LEFT JOIN messages m ON c.id=m.chat WHERE c.archived=0 AND (instr(lower(c.title),?)>0 OR instr(lower(m.payload),?)>0) ORDER BY c.updated DESC LIMIT 50',(q.lower(),q.lower()))

@app.get('/api/chats/hidden')
async def hidden_chats():
    return store.rows('SELECT id,title,archived FROM chats WHERE archived IN (1,2) ORDER BY updated DESC')

@app.post('/api/chats/{id}/organize')
async def organize_chat(id:str,request:Request):
    require_chat(id)
    if id in engine.runs and not engine.runs[id].get('finished'): raise ValueError('Finish or stop this chat before organizing it')
    action=(await request.json()).get('action')
    if action not in ('archive','delete','restore','fork'): raise ValueError('Unknown chat action')
    if action=='fork':
        original=store.rows('SELECT title FROM chats WHERE id=?',(id,))[0]
        target=store.create_chat(original['title']+' (fork)')
        # Copy the full transcript, never executable checkpoints or pending approvals.
        for m in store.messages(id): store.add(target,{k:v for k,v in m.items() if k not in ('id','created')})
        broadcast({'type':'changed'});return {'id':target}
    store.execute('UPDATE chats SET archived=? WHERE id=?',({'archive':1,'delete':2,'restore':0}[action],id))
    broadcast({'type':'changed'});return {'ok':True,'recoverable':True}

async def purge(id):
    require_chat(id)
    if id in engine.tasks and not engine.tasks[id].done(): raise ValueError('Stop this chat before deleting it permanently')
    runs=store.purge_chat(id)
    engine.runs.pop(id,None); engine.tasks.pop(id,None)
    for action,chat in list(engine.approvals.items()):
        if chat==id: engine.approvals.pop(action,None)
    checkpointer=getattr(engine.graph,'checkpointer',None)
    for run in runs:
        if checkpointer: await checkpointer.adelete_thread(run)

@app.delete('/api/chats/{id}')
async def delete_chat(id:str):
    await purge(id); broadcast({'type':'changed'}); return {'ok':True}

@app.post('/api/chats/trash/empty')
async def empty_trash():
    trashed=store.trashed()
    for id in trashed: await purge(id)
    broadcast({'type':'changed'}); return {'deleted':len(trashed)}

@app.post('/api/chats/{id}/run')
async def run_chat(id:str,request:Request):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    require_chat(id); b=await request.json()
    if id in engine.tasks and not engine.tasks[id].done(): raise ValueError('Task already running')
    if id in engine.runs and not engine.runs[id].get('finished'): raise ValueError('Resume or stop the existing task first')
    text=str(b.get('text','')).strip()
    if len(text)>100000: raise ValueError('Message exceeds 100,000 characters; put large material in a file')
    attachments=b.get('attachments',[])
    if not text and not attachments: raise ValueError('Write a message or attach a file')
    content=[{'type':'text','text':text}]
    if len(attachments)>10: raise ValueError('Attach at most ten files per turn')
    for ref in attachments:
        if str(ref.get('id','')).endswith('.txt'):
            from .attachments import text_part
            content.append(text_part(ref['id']));continue
        if not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp)',ref['id']): raise ValueError('Invalid image')
        p=DATA/'attachments'/ref['id']
        if not p.is_file(): raise ValueError('Image no longer exists')
        content.append({'type':'image_ref','id':ref['id'],'mime':{'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[p.suffix[1:]]})
    if not store.messages(id): store.execute('UPDATE chats SET title=? WHERE id=?',(text[:70] or 'Image analysis',id))
    store.add(id,{'role':'user','content':content if attachments else text})
    # Every way of saying "go ahead" carries the saved plan out step by step, never as one long ordinary run.
    from .plan_runner import wants_plan_run
    plan_only=bool(b.get('plan_only',False))
    plan_run=not plan_only and (bool(b.get('plan_run',False)) or (not attachments and wants_plan_run(text,store.setting('plan:'+id,None))))
    return {'run_id':engine.start(id,bool(b.get('reasoning',False)),plan_only=plan_only,plan_run=plan_run)}

MAX_CONTINUATIONS=5

@app.post('/api/chats/{id}/continue')
async def continue_chat(id:str):
    require_chat(id)
    previous=engine.public_run(id)
    if not previous or not previous.get('finished') or not previous.get('checkpoint'): raise ValueError('There is no checkpoint to continue from')
    if previous.get('continuations',0)>=MAX_CONTINUATIONS: raise ValueError(f'This task has already been continued {MAX_CONTINUATIONS} times. Review the results above, then give a new instruction.')
    store.add(id,{'role':'user','content':'Continue the task from the checkpoint above. Steps that already succeeded are listed there; do not repeat them. If the same approach keeps failing, try a different one or explain what is blocking.'})
    return {'run_id':engine.start(id,bool(previous.get('reasoning')),continue_from=previous)}

@app.post('/api/chats/{id}/steer')
async def steer_chat(id:str,request:Request):
    require_chat(id); return {'waiting':engine.steer(id,(await request.json()).get('text'))}

@app.get('/api/chats/{id}/trace')
async def chat_trace(id:str):
    """Everything about this chat's recent runs in one file, for working out what went wrong."""
    require_chat(id)
    from .config import VERSION as version
    from . import changes
    actions=[{k:a.get(k) for k in ('id','name','args','tier','status','created','step')}|{'result':(a['result'].get('text') if isinstance(a.get('result'),dict) and isinstance(a['result'].get('text'),str) else json.dumps(a.get('result'),default=str))[:4000]} for a in store.actions(id)]
    content={'luminaria':version,'exported':time.time(),'chat':id,'plan':store.setting('plan:'+id,None),'run':engine.public_run(id),
             'events':engine.worklog.events(id,12),'actions':actions,'file_changes':changes.summary(store,id),
             'messages':[{k:m.get(k) for k in ('role','content','tool_calls','name','plan_step','steer') if m.get(k) is not None} for m in store.messages(id)][-200:]}
    return Response(json.dumps(content,ensure_ascii=False,indent=1,default=str),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="luminaria-run-{id[:8]}.json"'})

@app.post('/api/chats/{id}/stop')
async def stop_chat(id:str):
    require_chat(id)
    if id in engine.tasks and not engine.tasks[id].done():
        task=engine.tasks[id]; task.cancel()
        with contextlib.suppress(asyncio.CancelledError): await task
    elif id in engine.runs:
        run=engine.runs[id]; run['phase']='Stopped';run['finished']=now();store.save_run(run)
        engine.finish_event(run)
        store.execute("UPDATE actions SET status='denied' WHERE chat=? AND status='pending'",(id,));store.recover_tool_pairs(id)
        for aid,cid in list(engine.approvals.items()):
            if cid==id: engine.approvals.pop(aid,None)
        broadcast({'type':'changed','chat':id})
    return {'ok':True}

@app.post('/api/chats/{id}/compact')
async def compact_chat(id:str):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    require_chat(id); return {'run_id':engine.start(id,compact_only=True)}

@app.get('/api/approvals')
async def pending():
    return [a for id in engine.runs for a in store.actions(id) if a['status']=='pending']

@app.post('/api/approvals/{id}/decision')
@app.post('/api/approvals/{id}')
async def decision(id:str,request:Request):
    body=await request.json(); chat=engine.approvals.get(id)
    if not chat: raise ValueError('Approval is no longer pending')
    approved=body.get('decision')=='allow' or body.get('approved') is True
    if body.get('scope')=='always' and approved:
        a=store.rows('SELECT name,tier FROM actions WHERE id=?',(id,))[0]
        if a['tier']!='approve': raise ValueError('This tool always requires approval for each action')
        store.set_setting('permission:'+a['name'],True)
    engine.resume(chat,{'approved':approved}); return {'ok':True}

@app.post('/api/attachments')
async def upload(request:Request):
    from PIL import Image
    import io
    b=await request.json(); raw=base64.b64decode(b['data'],validate=True)
    from .attachments import DOCUMENT_EXTENSIONS,TEXT_EXTENSIONS,save
    if Path(str(b.get('name',''))).suffix.lower() in TEXT_EXTENSIONS|DOCUMENT_EXTENSIONS:
        try: return await asyncio.to_thread(save,str(b['name']),raw)
        except ValueError:   # too big or not readable as text: keep the file as it is and attach it by location
            from .attachments import save_any
            return await asyncio.to_thread(save_any,str(b['name']),raw)
    if Path(str(b.get('name',''))).suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):
        from .attachments import save_any
        return await asyncio.to_thread(save_any,str(b.get('name','file')),raw)   # any other type is kept as it is and attached by location
    return _save_image(str(b.get('name','Image')),raw)

def _save_image(name,raw):
    from PIL import Image
    import io
    if len(raw)>8_000_000: raise ValueError('Image exceeds 8 MB')
    img=Image.open(io.BytesIO(raw)); img.verify()
    if img.format not in ('PNG','JPEG','WEBP'): raise ValueError('PNG, JPEG or WebP required')
    if img.width*img.height>30_000_000: raise ValueError('Image dimensions too large')
    ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}[img.format]; id=uid()+'.'+ext
    folder=DATA/'attachments'; folder.mkdir(exist_ok=True); (folder/id).write_bytes(raw)
    return {'id':id,'mime':'image/'+('jpeg' if ext=='jpg' else ext),'name':name[:100]}

def _attach_path(path):
    from .attachments import DOCUMENT_EXTENSIONS,TEXT_EXTENSIONS,DOCUMENT_LIMIT,attach_location,save
    from .config import workspace_path
    target=workspace_path(str(path),roam=True)
    if target.is_file():
        suffix,size=target.suffix.lower(),target.stat().st_size
        if suffix in ('.png','.jpg','.jpeg','.webp') and size<=8_000_000: return _save_image(target.name,target.read_bytes())
        if (suffix in TEXT_EXTENSIONS and size<=512000) or (suffix in DOCUMENT_EXTENSIONS and size<=DOCUMENT_LIMIT):
            try: return save(target.name,target.read_bytes())
            except ValueError: pass   # not readable as text: attach it where it is instead
    return attach_location(target)

@app.post('/api/attachments/path')
async def attach_paths(request:Request):
    """Attach files or folders by where they are on this PC: picked in the Windows dialog, dropped on the window, or typed."""
    b=await request.json(); paths=b.get('paths')
    if b.get('pick') in ('files','folder'):
        from .folder_picker import choose
        paths=await asyncio.to_thread(choose,'folder' if b['pick']=='folder' else 'file',CONFIG['workspace'],b['pick']=='files')
    if not isinstance(paths,list) or len(paths)>20: raise ValueError('Choose up to 20 files or folders')
    return {'attachments':[await asyncio.to_thread(_attach_path,str(p)) for p in paths]}

@app.post('/api/imports')
async def import_start(request:Request):
    from .attachments import start_import
    return start_import((await request.json()).get('name',''))

@app.post('/api/imports/{id}/files')
async def import_file(id:str,request:Request):
    from .attachments import add_import_file
    b=await request.json(); raw=base64.b64decode(b['data'],validate=True)
    return await asyncio.to_thread(add_import_file,id,str(b.get('path','')),raw)

@app.post('/api/imports/{id}/finish')
async def import_finish(id:str,request:Request):
    from .attachments import finish_import
    return finish_import(id,int((await request.json()).get('skipped',0)))

@app.get('/api/attachments/{id}')
async def attachment(id:str):
    if not re.fullmatch(r'[a-f0-9]{32}\.(png|jpg|webp)',id): raise HTTPException(404)
    p=DATA/'attachments'/id
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

@app.get('/api/files')
async def files(path:str='.'):
    return await engine.tools.call('list_files',{'path':path},{})

@app.get('/api/file')
async def file(path:str):
    workspace_path(path,roam=True)  # any file on this PC except protected places
    return await engine.tools.call('read_file',{'path':path,'limit':32000},{})

@app.get('/api/file/download')
async def download(path:str):
    p=workspace_path(path,roam=True)
    if not p.is_file(): raise HTTPException(404)
    return FileResponse(p,filename=p.name)

@app.get('/api/actions')
async def action_history(status:str='',q:str='',limit:int=200):
    if status not in ('','problems','done','error','denied','interrupted','pending','running'): raise ValueError('Unknown status filter')
    return store.action_history(status,q[:200],limit)

@app.get('/api/actions/{id}/output')
async def output(id:str):
    if not re.fullmatch('[a-f0-9]{32}',id): raise HTTPException(404)
    p=DATA/'tool-outputs'/(id+'.json')
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p,media_type='application/json',filename=id+'.json')

@app.get('/api/tools')
async def tool_list(): return engine.tools.catalog()

def memory_entries():
    from .memory_file import read,entries
    try: return entries(read(store))
    except OSError: return []

@app.get('/api/memory')
async def memory_get():
    from .memory_file import read,entries,PATH,project_path,project_text,MAX_FILE
    text=read(store); project=project_path()
    return {'content':text,'path':str(PATH),'entries':len(entries(text)),'limit':MAX_FILE,
            'project':{'path':str(project) if project else '','exists':bool(project and project.is_file()),'content':project_text()}}

@app.put('/api/memory')
async def memory_put(request:Request):
    from .memory_file import write,entries
    b=await request.json(); text=write(store,b.get('content'))
    broadcast({'type':'changed'}); return {'ok':True,'entries':len(entries(text))}

@app.put('/api/memory/project')
async def memory_project_put(request:Request):
    """LUMINARIA.md in the default folder: notes about this project, like CLAUDE.md in a code repository."""
    from .memory_file import project_path
    b=await request.json(); content=b.get('content')
    if not isinstance(content,str) or len(content)>200_000: raise ValueError('Project notes must be text under 200,000 characters')
    p=project_path()
    if not p: raise ValueError('Choose a default folder first')
    p.write_text(content.replace('\r\n','\n'),encoding='utf-8'); broadcast({'type':'changed'}); return {'ok':True,'path':str(p)}

@app.post('/api/memories')
async def memory_add(request:Request):
    """Kept for older screens: adds one note to MEMORY.md."""
    from .memory_file import remember
    b=await request.json(); result=remember(store,str(b.get('title','')),str(b.get('content','')))
    broadcast({'type':'changed'}); return result

@app.post('/api/schedules')
async def schedule_create(request:Request):
    b=await request.json(); return await engine.tools.call('create_schedule',{'title':str(b['title'])[:120],'prompt':str(b['prompt'])[:10000],'interval_minutes':int(b['interval_minutes'])},{})

@app.patch('/api/schedules/{id}')
async def schedule_update(id:str,request:Request):
    b=await request.json(); store.execute('UPDATE schedules SET enabled=? WHERE id=?',(bool(b['enabled']),id)); return {'ok':True}

@app.delete('/api/schedules/{id}')
async def schedule_delete(id:str): store.execute('DELETE FROM schedules WHERE id=?',(id,)); return {'ok':True}

@app.post('/api/orchestration/eligibility')
async def orchestration_eligibility(request:Request):
    from .orchestration import eligibility,explain_none,normalize_pool
    from .models import registry
    b=await request.json() if (await request.body()) else {}
    setting=normalize_pool(b.get('pool',CONFIG.get('orchestration_pool')))
    router=b.get('router',CONFIG.get('orchestrator_model',''))
    models=registry();rows=eligibility(models,setting,router=router)
    for r,m in zip(rows,models): r['vision']=bool(m.get('projector_file')) and Path(m['projector_file']).is_file(); r['context']=m.get('context')
    included=[r for r in rows if r['included']]
    selected=CONFIG['model']; inside=any(r['id']==selected for r in included)
    if not included: fallback=explain_none(rows,setting)
    elif inside: fallback=f'If Auto cannot decide, it uses your selected model ({selected}), which is in this selection.'
    else: fallback=f'Your selected model ({selected}) is outside this selection, so if Auto cannot decide the task stops and says why instead of using it.'
    return {'pool':setting,'router':router,'models':rows,'included':len(included),'fallback':fallback,
            'rules':'Auto never downloads a model or routes outside this list. Image tasks also need a model that can read images, and long conversations need enough context.'}

@app.get('/api/settings')
async def settings():
    from .config import access_status
    public={k:v for k,v in CONFIG.items() if k not in ('mcp','model_api_key')}
    public['access_status']=access_status()
    from .config import drive_of
    try:
        import ctypes;mask=ctypes.windll.kernel32.GetLogicalDrives();every=[f'{chr(65+i)}:' for i in range(26) if mask>>i&1]
    except Exception: every=[]
    from .admin_helper import OPERATIONS as admin_jobs
    public['admin_jobs']=admin_jobs; public['admin_grants']=CONFIG.get('admin_grants') or []
    public['drives']=CONFIG.get('drives','all'); public['drives_available']=every; public['drives_required']=sorted({drive_of(CONFIG['workspace']),drive_of(DATA)}-{'/'})
    from .config import WORKSPACE_PROBLEM
    public['workspace_problem']=WORKSPACE_PROBLEM
    public['data_directory']=str(DATA); public['mcp_configured']=list(CONFIG.get('mcp',{})); return public

@app.post('/api/workspace/browse')
async def browse_workspace():
    from .folder_picker import pick
    return await asyncio.to_thread(pick,CONFIG['workspace'])

@app.post('/api/settings')
async def settings_save(request:Request):
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before changing settings')
    b=await request.json(); allowed={'workspace','endpoint','tokenizer','model','context','output_tokens','compact_ratio','python','node','llama_executable','model_file','projector_file','external_tools','ask_reads'}
    allowed.update({'admin_grants','drives','coder_model','planner_model','keep_model_loaded','access_mode','orchestrator_model','compact_keep_turns','orchestration_pool','orchestration_enabled'})
    if 'orchestration_pool' in b:
        from .orchestration import normalize_pool
        b['orchestration_pool']=normalize_pool(b['orchestration_pool'])
    if 'orchestration_enabled' in b and not isinstance(b['orchestration_enabled'],bool): raise ValueError('Boolean setting required')
    if b.get('orchestrator_model'):
        from .models import registry
        if not any(m['id']==b['orchestrator_model'] and Path(m['model_file']).is_file() for m in registry()):raise ValueError('Choose an installed orchestration model')
    if 'access_mode' in b and b['access_mode'] not in ('review','full'): raise ValueError('Choose review or full access')
    for role in ('planner_model','coder_model'):
        if role in b and (not isinstance(b[role],str) or len(b[role])>300): raise ValueError('Choose a model for this role')
    if 'keep_model_loaded' in b and b['keep_model_loaded'] not in (0,300,1800): raise ValueError('Choose how long to keep the model loaded')
    changes={k:v for k,v in b.items() if k in allowed}
    if 'admin_grants' in changes:
        from .admin_helper import OPERATIONS
        g=changes['admin_grants']
        if not isinstance(g,list) or any(x not in OPERATIONS for x in g): raise ValueError('Unknown admin helper job')
        changes['admin_grants']=sorted(set(g))
    if 'drives' in changes:
        d=changes['drives']
        if d!='all' and not (isinstance(d,list) and d and all(isinstance(x,str) and re.fullmatch(r'[A-Za-z]:',x) for x in d)): raise ValueError('Choose all drives or at least one drive')
        if d!='all': changes['drives']=sorted({x.upper() for x in d})
    for key in ('external_tools','ask_reads'):
        if key in changes and not isinstance(changes[key],bool): raise ValueError('Boolean setting required')
    for key in ['endpoint','tokenizer']:
        if key in changes and not re.match(r'^https?://',changes[key]): raise ValueError('HTTP(S) endpoint required')
    if 'context' in changes: changes['context']=max(4096,min(262144,int(changes['context'])))
    if 'output_tokens' in changes: changes['output_tokens']=max(256,min(8192,int(changes['output_tokens'])))
    if 'compact_ratio' in changes: changes['compact_ratio']=max(.4,min(.85,float(changes['compact_ratio'])))
    if 'compact_keep_turns' in changes:
        value=changes['compact_keep_turns']
        if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=12:raise ValueError('Keep between 1 and 12 recent turns')
    if 'workspace' in changes:
        if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop the running task before changing the default folder.')
        target=Path(changes['workspace']).expanduser()
        if target.exists() and not target.is_dir(): raise ValueError(f'{target} is a file, not a folder. Choose a folder.')
        target.mkdir(parents=True,exist_ok=True)
        from . import config as config_module
        config_module.WORKSPACE_PROBLEM=''
    save_config(changes); broadcast({'type':'changed'}); return {'ok':True}

@app.get('/api/model/status')
async def model_status():
    import httpx
    from .runtime import diagnose,manager_state
    try:
        async with httpx.AsyncClient(timeout=3,trust_env=False,headers={'Authorization':'Bearer '+CONFIG.get('model_api_key','local-only')}) as client:
            r=await client.get(CONFIG['endpoint']+'/models'); r.raise_for_status()
            loaded=False
            try: loaded=(await client.get(CONFIG['tokenizer']+'/health')).status_code==200
            except httpx.HTTPError: pass
        busy=engine.busy()
        return {'connected':True,'loaded':loaded,'models':r.json().get('data',[]),'model':CONFIG['model'],'manager':manager_state(),
                'state':'working' if busy else 'loaded' if loaded else 'off','unload_at':None if busy else engine.unload_at,'keep_loaded':engine.keep_loaded()}
    except Exception as e:
        state=manager_state();problem=diagnose() if state['owned'] and not state['running'] else None
        return {'connected':False,'loaded':False,'error':str(e),'model':CONFIG['model'],'manager':state,'problem':problem,'state':'off','unload_at':None,'keep_loaded':engine.keep_loaded()}

@app.post('/api/model/restart')
async def model_restart():
    if any(not t.done() for t in engine.tasks.values()): raise ValueError('Stop running tasks before restarting the model manager')
    from .runtime import stop_owned,start_swap
    await asyncio.to_thread(stop_owned)
    result=await asyncio.to_thread(start_swap)
    engine.client.headers['Authorization']='Bearer '+CONFIG.get('model_api_key','local-only')
    broadcast({'type':'changed'}); return result

@app.post('/api/model/start')
async def model_start():
    from .runtime import start_swap
    result = await asyncio.to_thread(start_swap)
    # Starting the manager can create the local key after Engine's client exists.
    engine.client.headers['Authorization']='Bearer '+CONFIG.get('model_api_key','local-only')
    return result

@app.post('/api/model/unload')
async def unload_model():
    if any(not t.done() for t in engine.tasks.values()): raise ValueError('Stop running tasks before unloading')
    # Fixed local llama-swap control endpoint; never a caller-supplied URL.
    engine.cancel_unload()
    r=await engine.client.post('http://127.0.0.1:8098/models/unload',timeout=20)
    r.raise_for_status(); broadcast({'type':'model_state'}); return {'ok':True}

@app.get('/api/updates')
async def updates():
    from .updates import check
    return await check()

@app.post('/api/updates/install')
async def update_install(background_tasks:BackgroundTasks):
    if any(not r.get('finished') for r in engine.runs.values()):raise HTTPException(409,'Finish or stop active tasks before installing an update.')
    from .updates import install
    result=await install()
    if result.get('closing'):
        from .lifecycle import request_shutdown
        background_tasks.add_task(request_shutdown)
    return result

@app.get('/api/skills')
async def skills():
    from .skills import catalog
    return [{**s,'enabled':store.setting('skill:'+s['name'],True),'last_run':store.setting('skill_run:'+s['name'],None)} for s in catalog(connectors)]

@app.post('/api/skills')
async def skill_import(request:Request):
    from .skills import save_skill
    b=await request.json(); return save_skill(b['name'],b['content'])

@app.get('/api/skills/{name}')
async def skill_instructions(name:str):
    from .skills import load_skill
    skill=load_skill(name)
    with contextlib.suppress(Exception): usage.skill('viewed',name)
    return skill

@app.get('/api/skills/{name}/setup')
async def skill_setup(name:str):
    from .skill_setup import checklist
    return checklist(name,connectors)

@app.post('/api/skills/{name}/setup/connector')
async def skill_setup_connector(name:str,request:Request):
    from .skill_setup import checklist,connector_config
    body=await request.json();need=body.get('connector')
    guide=checklist(name,connectors)
    if not any(s['id']==need and s['action']=='connector' for s in guide['steps']):raise ValueError('This connector is not a declared prerequisite')
    if body.get('approved') is not True:raise ValueError('Review local connector access before starting it')
    if any(not r.get('finished') for r in engine.runs.values()):raise ValueError('Stop active tasks before reconnecting tools')
    config=connector_config(need);configs=CONFIG.get('mcp',{}).copy();configs[need]=config
    save_config({'mcp':configs});await restart_connector(need,config)
    return {'status':'connecting','note':'Use Check again to verify that the live connector loads its tools.'}

@app.delete('/api/skills/{name}')
async def skill_remove(name:str):
    from .skills import remove_skill
    return remove_skill(name)

@app.get('/api/sessions')
async def sessions(): return store.chats()

@app.get('/api/sessions/{id}')
async def session(id:str): return await state(id)

@app.delete('/api/sessions/{id}')
async def delete_session(id:str):
    await stop_chat(id); store.execute('UPDATE chats SET archived=1 WHERE id=?',(id,));return {'archived':True,'history_preserved':True}

def brief_summary(chat):
    from .brief import load
    entries=load(store,chat)['entries']
    return {'entries':len(entries),'pinned':sum(1 for e in entries if e.get('pinned',True))}

@app.get('/api/chats/{id}/brief')
async def chat_brief(id:str):
    from .brief import load,SECTIONS,MAX_ENTRIES,MAX_TEXT
    require_chat(id); return {'brief':load(store,id),'sections':SECTIONS,'max_entries':MAX_ENTRIES,'max_text':MAX_TEXT}

@app.post('/api/chats/{id}/brief')
async def chat_brief_change(id:str,request:Request):
    from .brief import apply
    require_chat(id); b=await request.json()
    brief=apply(store,id,b.get('op'),'user',b.get('id'),b.get('section'),b.get('text'),b.get('pinned'))
    broadcast({'type':'changed','chat':id}); return {'brief':brief}

def _changes(chat):
    if not chat: return None
    from . import changes
    try: found=changes.summary(store,chat)
    except Exception: return None
    return found if found['files'] else None

@app.get('/api/chats/{id}/changes')
async def chat_changes(id:str):
    require_chat(id)
    from . import changes
    return changes.summary(store,id)

@app.post('/api/chats/{id}/undo')
async def chat_undo(id:str):
    require_chat(id)
    if id in engine.runs and not engine.runs[id].get('finished'): raise ValueError('Finish or stop the current task first')
    from . import changes
    from .config import DATA
    result=await asyncio.to_thread(changes.undo,store,DATA,id)
    broadcast({'type':'changed','chat':id}); return result

@app.get('/api/chats/{id}/plan')
async def chat_plan(id:str):
    require_chat(id); return {'plan':store.setting('plan:'+id,None)}

@app.delete('/api/chats/{id}/plan')
async def clear_chat_plan(id:str):
    require_chat(id)
    if id in engine.runs and not engine.runs[id].get('finished'): raise ValueError('Finish or stop the current run first')
    store.execute('DELETE FROM settings WHERE key=?',('plan:'+id,)); broadcast({'type':'changed','chat':id}); return {'ok':True}

@app.post('/api/chats/{id}/resume')
async def resume_chat(id:str): return {'run_id':engine.resume(id)}

@app.post('/api/open-external')
async def open_external(request:Request):
    # Every outside web page opens in the user's default browser, never inside Luminaria's own window.
    from urllib.parse import urlsplit
    import webbrowser
    url=str((await request.json()).get('url',''))
    parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname: raise ValueError('Only web addresses can be opened')
    if parts.hostname in ('127.0.0.1','localhost','::1'): raise ValueError('That address belongs to Luminaria itself')
    return {'opened':bool(await asyncio.to_thread(webbrowser.open,url,new=2,autoraise=True))}

@app.get('/api/catalog')
async def catalog_search(q:str='',kind:str='skills',offset:int=0):
    from .catalog import search
    from .skills import catalog as installed
    data=await asyncio.to_thread(search,q,kind,40,max(0,offset))
    skills={s['name'] for s in installed(connectors)}; mcp=CONFIG.get('mcp',{})
    from .marketplace import connector_for
    for row in data['items']:
        if row['kind']=='skill': row['installed']=row['name'] in skills
        else:
            try: row['installed']=connector_for(row['id'],{'kind':'npm','identifier':'x'})[0] in mcp
            except ValueError: row['installed']=False
    return data

@app.post('/api/catalog/install')
async def catalog_install(request:Request):
    from .catalog import find,install_skill,connector_plan
    b=await request.json()
    if b.get('confirm') is not True: raise ValueError('Confirm the install first')
    kind,item=find(str(b.get('id','')))
    if kind=='skills': return await asyncio.to_thread(install_skill,item)
    name,command,args=connector_plan(item)
    if name in CONFIG.get('mcp',{}): raise ValueError('A connector named '+name+' is already installed')
    await engine.tools.connector_installer(name,{'command':command,'args':args,'cwd':CONFIG['workspace']})
    return {'kind':'connector','name':name}

@app.get('/api/marketplace/skills')
async def market_skills(q:str='',repos:str=''):
    from .marketplace import search_skills
    from .skills import catalog
    extra=[r for r in repos.split(',') if r.strip()]
    data=await asyncio.to_thread(search_skills,q,extra)
    have={s['name'] for s in catalog(connectors)}
    for row in data['items']:row['installed']=row['name'] in have
    return data

@app.post('/api/marketplace/skills/install')
async def market_skill_install(request:Request):
    from .marketplace import install_skill
    b=await request.json()
    return await asyncio.to_thread(install_skill,str(b.get('repo','')),str(b.get('path','')))

@app.get('/api/marketplace/mcp')
async def market_mcp(q:str='',cursor:str=''):
    from .marketplace import search_mcp
    data=await asyncio.to_thread(search_mcp,q,cursor or None)
    have=set(CONFIG.get('mcp',{}))
    from .marketplace import connector_for
    for row in data['items']:
        names=[]
        for pkg in row['packages']:
            try:names.append(connector_for(row['id'],pkg)[0])
            except ValueError:row['installable']=False  # unsafe package name: shown, never installable
        row['installed']=any(n in have for n in names)
    return data

@app.post('/api/marketplace/mcp/install')
async def market_mcp_install(request:Request):
    from .marketplace import connector_for,search_mcp
    b=await request.json()
    if b.get('confirm') is not True: raise ValueError('Confirm that you want to download and run this connector')
    found=await asyncio.to_thread(search_mcp,str(b.get('id','')))
    server=next((i for i in found['items'] if i['id']==b.get('id')),None)
    if not server or not server['packages']:raise ValueError('This connector has no installable package')
    package=server['packages'][min(int(b.get('package',0)),len(server['packages'])-1)]
    if package['needs']:raise ValueError('This connector needs '+', '.join(package['needs'])+' set first. Add it as a custom connector in Settings › Integrations.')
    name,command,args=connector_for(server['id'],package)
    configs=CONFIG.get('mcp',{}).copy()
    if name in configs: raise ValueError('A connector named '+name+' is already installed')
    configs[name]={'command':command,'args':args,'cwd':CONFIG['workspace']}
    save_config({'mcp':configs});await restart_connector(name,configs[name]);return {'ok':True,'name':name}

@app.post('/api/permissions/reset')
async def reset_permissions(): store.execute("DELETE FROM settings WHERE key LIKE 'permission:%'");return {'ok':True}

@app.get('/api/sharing')
async def sharing_status():
    from .sharing import status
    return status()

@app.post('/api/sharing')
async def sharing_change(request:Request):
    from .sharing import apply
    b=await request.json()
    return await apply({k:b[k] for k in ('share_models','lend_gpu','rpc_peers') if k in b})

@app.post('/api/sharing/find')
async def sharing_find():
    from .sharing import find_pcs
    return {'pcs':await find_pcs()}

@app.post('/api/sharing/code')
async def sharing_code():
    from .sharing import open_pairing,status
    if not CONFIG.get('share_models'): raise ValueError('Turn on "Let other PCs pair" first')
    open_pairing(); return status()

@app.post('/api/sharing/pair')
async def sharing_pair(request:Request):
    from .sharing import pair
    b=await request.json(); entry=await pair(b.get('address'),b.get('code'),b.get('port') or 8099)
    broadcast({'type':'changed'}); return entry

@app.post('/api/sharing/split')
async def sharing_split(request:Request):
    from .sharing import set_split
    return await set_split(bool((await request.json()).get('on')))

@app.get('/api/services')
async def list_services():
    from .services import services
    return {'services':[{k:v for k,v in x.items()} for x in services()]}

@app.post('/api/services')
async def add_service(request:Request):
    from .services import add
    result=await add(await request.json()); broadcast({'type':'changed'}); return result

@app.post('/api/services/{sid}/files')
async def service_files(sid:str,request:Request):
    from .services import set_files
    set_files(sid,bool((await request.json()).get('files'))); return {'ok':True}

@app.post('/api/services/{sid}/models')
async def service_models(sid:str,request:Request):
    from .services import set_enabled
    chosen=set_enabled(sid,(await request.json()).get('enabled') or []); broadcast({'type':'changed'}); return {'enabled':chosen}

@app.post('/api/services/{sid}/refresh')
async def service_refresh(sid:str):
    from .services import refresh
    return await refresh(sid)

@app.delete('/api/services/{sid}')
async def remove_service(sid:str):
    from .services import remove
    remove(sid); broadcast({'type':'changed'}); return {'ok':True}

@app.get('/api/models')
async def models():
    from .models import public_models
    return public_models(store)

@app.post('/api/models')
async def add_model(request:Request):
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish active tasks before editing the registry')
    from .models import add_model
    result=add_model(await request.json())
    from .runtime import swap_process,stop_owned
    if swap_process and swap_process.poll() is None: stop_owned()
    return result

@app.post('/api/models/{id:path}/select')
async def select_model(id:str):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before switching models')
    from .models import select
    result=select(id)
    runtime_config=DATA/'llama-swap.yaml'
    configured=json.loads(runtime_config.read_text('utf-8')).get('models',{}) if runtime_config.exists() else {}
    if id not in configured:
        from .runtime import stop_owned,start_swap
        await asyncio.to_thread(stop_owned);await asyncio.to_thread(start_swap)
    engine.client.headers['Authorization']='Bearer '+CONFIG.get('model_api_key','local-only')
    broadcast({'type':'changed'});return result

@app.post('/api/connectors')
async def connector_save(request:Request):
    b=await request.json(); name=b.get('name','')
    if not re.fullmatch('[a-z][a-z0-9_]{0,30}',name): raise ValueError('Invalid connector name')
    if not isinstance(b.get('args'),list) or not all(isinstance(a,str) for a in b['args']): raise ValueError('Arguments must be a JSON array of strings')
    from .integrations import PRESETS
    if name in PRESETS: raise ValueError('That name is used by a built-in integration')
    configs=CONFIG.get('mcp',{}).copy(); configs[name]={'command':str(b['command']),'args':b['args'],'cwd':CONFIG['workspace']}
    save_config({'mcp':configs}); await restart_connector(name,configs[name]); return {'ok':True}

@app.delete('/api/connectors/{name}')
async def connector_remove(name:str):
    from .integrations import PRESETS
    configs=CONFIG.get('mcp',{}).copy()
    if name in PRESETS or name in ('browser','windows') or name not in configs: raise HTTPException(404,'Unknown connector')
    configs.pop(name); save_config({'mcp':configs}); await restart_connector(name,None); return {'ok':True}

@app.get('/api/integrations')
async def integrations_list():
    from .integrations import catalog
    return catalog(CONFIG.get('mcp',{}),connectors)

async def restart_connector(name,config):
    if name in connectors:
        await connectors.pop(name).close()
    if config:
        c=Connector(name,config,broadcast); connectors[name]=c; c.start()
    broadcast({'type':'connectors_changed','connector':name})

@app.post('/api/integrations/{name}')
async def integration_connect(name:str,request:Request):
    from .integrations import config_for,write_secrets
    config,secrets_=config_for(name,await request.json())
    write_secrets(name,secrets_)
    configs=CONFIG.get('mcp',{}).copy(); configs[name]=config; save_config({'mcp':configs})
    await restart_connector(name,config)
    return {'ok':True}

@app.delete('/api/integrations/{name}')
async def integration_disconnect(name:str):
    from .integrations import PRESETS,forget
    if name not in PRESETS: raise HTTPException(404,'Unknown integration')
    configs=CONFIG.get('mcp',{}).copy(); configs.pop(name,None); save_config({'mcp':configs})
    await restart_connector(name,None); forget(name)
    return {'ok':True}

@app.get('/oauth/callback')
async def oauth_callback(request:Request):
    from html import escape
    from .integrations import complete
    ok,message=complete(request.url.query)
    return Response(f'<!doctype html><meta charset="utf-8"><title>Luminaria</title><body style="font:16px system-ui;background:#141A17;color:#EBF0E8;display:grid;place-items:center;height:90vh"><p>{escape(message)}</p></body>',media_type='text/html',status_code=200 if ok else 400)

@app.post('/api/skills/{name}/toggle')
async def skill_toggle(name:str,request:Request):
    b=await request.json();enabled=bool(b['enabled'])
    if store.setting('skill:'+name,True)!=enabled:
        with contextlib.suppress(Exception): usage.skill('enabled' if enabled else 'disabled',name)
    store.set_setting('skill:'+name,enabled);return {'ok':True}

@app.post('/api/chat')
async def chat_stream(request:Request):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    b=await request.json(); id=b.get('session_id') or store.create_chat()
    require_chat(id)
    if id in engine.runs and not engine.runs[id].get('finished'): raise ValueError('Session already active')
    queue=asyncio.Queue(maxsize=500);subscribers.add(queue)
    store.add(id,{'role':'user','content':str(b.get('message',b.get('text','')))})
    engine.start(id,bool(b.get('reasoning',False)),plan_only=bool(b.get('plan_only',False)))
    async def generate():
        yield 'event: session\ndata: '+json.dumps({'session_id':id})+'\n\n'
        try:
            while True:
                try: e=await asyncio.wait_for(queue.get(),1)
                except asyncio.TimeoutError: e=None
                if e and e.get('chat')==id:
                    event={'delta':'token','approval':'approval_requested','compacted':'compaction'}.get(e['type'],e['type'])
                    yield 'event: '+event+'\ndata: '+json.dumps(e)+'\n\n'
                run=engine.runs[id]
                if run.get('finished'):
                    yield 'event: '+('error' if run['phase']=='Error' else 'done')+'\ndata: '+json.dumps(engine.public_run(id))+'\n\n';break
                if await request.is_disconnected(): break
        finally: subscribers.discard(queue)
    return StreamingResponse(generate(),media_type='text/event-stream')

@app.get('/api/voice/status')
async def voice_status():
    from .voice import status
    return status()

@app.post('/api/voice/transcribe')
async def voice_transcribe(request:Request):
    from .voice import transcribe
    raw=await request.body()
    if len(raw)>1_200_000: raise ValueError('Voice recording exceeds 35 seconds')
    return await asyncio.to_thread(transcribe,raw)

@app.post('/api/voice/install')
async def voice_install():
    from .voice import install_models
    return await asyncio.to_thread(install_models)

@app.post('/api/voice/speak')
async def voice_speak(request:Request):
    from .voice import synthesize
    b=await request.json()
    return Response(await asyncio.to_thread(synthesize,b.get('text',''),b.get('voice_id',store.setting('preferences',{}).get('voice_id','lessac'))),media_type='audio/wav')

@app.post('/api/voice/voices/{id}/install')
async def voice_install_choice(id:str):
    from .voice import install_voice
    return await asyncio.to_thread(install_voice,id)

@app.get('/api/preferences')
async def preferences():
    from .preferences import DEFAULTS,migrate,load_shared_appearance
    result=DEFAULTS | migrate(store.setting('preferences',{}))
    shared=load_shared_appearance()
    if shared is not None:result.update(appearance=shared,theme_mode=shared['mode'])
    return result

@app.post('/api/models/{id}/benchmark')
async def benchmark_model(id:str):
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish active tasks before benchmarking')
    benchmarking=True
    try:
        from .benchmark import measure
        return await measure(id)
    finally:
        benchmarking=False

@app.post('/api/models/{id}/context')
async def model_context(id:str,request:Request):
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()):
        raise ValueError('Finish active tasks and benchmarks before changing context')
    from .models import set_context
    from .runtime import stop_owned,start_swap,manager_state
    body=await request.json()
    manager=manager_state()
    if manager.get('running') and not manager.get('owned'):
        raise ValueError('The model manager belongs to another Luminaria process. Close that app and start the manager here before changing context.')
    # Serializes concurrent model-management operations while the manager restarts.
    benchmarking=True
    try:
        model=set_context(id,body.get('context'))
        await asyncio.to_thread(stop_owned)
        await asyncio.to_thread(start_swap)
        broadcast({'type':'changed'})
        return {'context':model['context'],'message':'Context saved. The model reloads on its next request.'}
    finally:benchmarking=False

@app.post('/api/models/{id}/launch')
async def model_launch(id:str,request:Request):
    """Save fine-tuned load settings (GPU layers, experts on CPU, batch size, context) and reload."""
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()):
        raise ValueError('Finish active tasks and benchmarks before changing load settings')
    from .models import set_launch
    from .runtime import stop_owned,start_swap,manager_state
    body=await request.json()
    manager=manager_state()
    if manager.get('running') and not manager.get('owned'):
        raise ValueError('The model manager belongs to another Luminaria process. Close that app first.')
    benchmarking=True
    try:
        model=set_launch(id,body)
        await asyncio.to_thread(stop_owned)
        await asyncio.to_thread(start_swap)
        broadcast({'type':'changed'})
        return {'launch':model.get('launch') or {},'context':model.get('context'),'message':'Load settings saved. The model reloads on its next request.'}
    finally:benchmarking=False

@app.get('/api/hardware/profile')
async def hardware_profile(refresh:bool=False):
    """The memory picture used for fit ratings, re-detected on request."""
    from .hardware import cached_information
    from . import fit
    info=await asyncio.to_thread(cached_information,600,refresh)
    return {'machine':fit.machine(info,CONFIG.get('hardware_override')),'override':CONFIG.get('hardware_override')}

@app.post('/api/hardware/profile')
async def hardware_profile_save(request:Request):
    """Let people correct detection: graphics memory in GB (0 = no usable GPU), or clear to auto-detect."""
    body=await request.json()
    if body.get('auto'):save_config({'hardware_override':None});return await hardware_profile()
    value=body.get('vram_gb')
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=512:raise ValueError('Graphics memory must be a number of GB from 0 to 512')
    save_config({'hardware_override':{'vram_bytes':int(value*1024**3),'integrated':bool(body.get('integrated',False))}})
    return await hardware_profile()

@app.post('/api/models/{id}/evaluate')
async def evaluate_model(id:str):
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish active tasks before running a quality check')
    benchmarking=True
    try:
        from .quality import evaluate
        return await evaluate(id)
    finally:
        benchmarking=False

@app.get('/api/model-library')
async def model_library():
    from .model_library import library
    return await asyncio.to_thread(library, store)

@app.post('/api/model-library/{id}/download')
async def model_download(id:str):
    from .model_library import enqueue, library
    await asyncio.to_thread(enqueue, id)
    return await asyncio.to_thread(library, store)

@app.post('/api/model-library/{id}/cancel')
async def model_download_cancel(id:str):
    from .model_library import cancel, library
    await asyncio.to_thread(cancel, id)
    return await asyncio.to_thread(library, store)

@app.post('/api/model-library/{id}/discard')
async def model_download_discard(id:str):
    from .model_library import discard, library
    await asyncio.to_thread(discard, id)
    return await asyncio.to_thread(library, store)

@app.post('/api/model-library/{id}/use')
async def model_use(id:str):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before switching models')
    from .model_library import prepare
    from .models import select
    prepared=await asyncio.to_thread(prepare, id)
    result=select(prepared['id'])
    runtime_config=DATA/'llama-swap.yaml'
    configured=json.loads(runtime_config.read_text('utf-8')).get('models',{}) if runtime_config.exists() else {}
    command=configured.get(prepared['id'],{}).get('cmd','')
    if prepared['id'] not in configured or ('--mmproj' in command)!=bool(prepared.get('projector_file')):
        from .runtime import stop_owned, start_swap
        await asyncio.to_thread(stop_owned); await asyncio.to_thread(start_swap)
    engine.client.headers['Authorization']='Bearer '+CONFIG.get('model_api_key','local-only')
    broadcast({'type':'changed'}); return result

@app.post('/api/model-library/remove-all')
async def model_remove_all(request:Request):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before removing models')
    from .model_library import remove_all
    result=await asyncio.to_thread(remove_all,(await request.json()).get('confirm'))
    broadcast({'type':'changed'}); return result

@app.post('/api/model-library/download-all')
async def model_download_all(request:Request):
    from .model_library import download_all
    body=await request.json()
    keys=[str(k) for k in body.get('keys') or []] or None
    result=await asyncio.to_thread(download_all,store,body.get('confirm') is True,keys)
    broadcast({'type':'changed'}); return result

@app.post('/api/model-library/remove-selected')
async def model_remove_selected(request:Request):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before removing models')
    from .model_library import remove_selected
    body=await request.json()
    result=await asyncio.to_thread(remove_selected,body.get('ids'),body.get('confirm'))
    broadcast({'type':'changed'}); return result

@app.post('/api/model-library/{id}/remove')
async def model_remove(id:str, request:Request):
    if benchmarking: raise ValueError('Wait for the model benchmark to finish')
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before removing a model')
    from .model_library import remove, library
    await asyncio.to_thread(remove, id, (await request.json()).get('confirm'))
    broadcast({'type':'changed'})
    return await asyncio.to_thread(library, store)

@app.post('/api/preferences')
async def preferences_save(request:Request):
    from .preferences import validate,save_shared_appearance
    values=validate(await request.json())
    if 'appearance' in values:
        save_shared_appearance(values['appearance'])
        values['theme_mode']=values['appearance']['mode']
    values=store.setting('preferences',{}) | values
    store.set_setting('preferences',values); return {'ok':True}

@app.get('/api/cloud-sync')
async def cloud_sync_status():
    try:return await cloud_sync.status()
    except ValueError as error:
        owner=store.setting('cloud_sync_owner');state=cloud_sync.state(owner) if owner else {}
        return {'enabled':bool(state.get('enabled')),'last_sync':state.get('last_sync'),'conflicts':[],'error':str(error),'unavailable':True}
@app.post('/api/cloud-sync/preview')
async def cloud_sync_preview():return await cloud_sync.preview()
@app.post('/api/cloud-sync/enable')
async def cloud_sync_enable(request:Request):
    payload=await request.json()
    if type(payload.get('enabled')) is not bool:raise ValueError('Choose whether to enable sync')
    return await cloud_sync.enable(payload['enabled'])
@app.post('/api/cloud-sync/run')
async def cloud_sync_run():return await cloud_sync.run()
@app.post('/api/cloud-sync/resolve')
async def cloud_sync_resolve(request:Request):
    payload=await request.json();return await cloud_sync.resolve(str(payload.get('key','')),payload.get('choice'))

@app.get('/api/accounts')
async def accounts():
    from .profiles import status
    from .identity import status as identity_status
    return {**status(),'identity':await identity_status()}

@app.post('/api/identity/start')
async def identity_start(request:Request):
    from .identity import start
    payload=await request.json()
    return await identity_call(start(payload.get('provider'),open_browser=payload.get('open_browser') is True,link=payload.get('link') is True,enter_workspace=payload.get('enter_workspace') is True))

async def identity_call(operation):
    import httpx
    try:return await operation
    except httpx.HTTPError:raise HTTPException(503,'Sign-in service is unavailable. Check your connection and try again.') from None

@app.post('/api/identity/poll')
async def identity_poll(request:Request,background_tasks:BackgroundTasks):
    from .identity import poll,pending
    flow_id=(await request.json()).get('flow_id','')
    # Linking another provider does not switch workspaces or restart the app.
    # Only account entry needs the task-safety guard.
    if pending.get(flow_id,{}).get('enter_workspace') and any(not r.get('finished') and not r.get('resume_available') for r in engine.runs.values()):
        raise ValueError('Finish or stop active tasks before completing sign-in')
    result=await identity_call(poll(flow_id))
    if result.get('restart_required'):
        from .lifecycle import request_restart
        background_tasks.add_task(request_restart)
    return result

@app.get('/api/gate')
async def gate_status(force:bool=False):
    from .identity import gate
    return await gate(force)

@app.get('/api/onboarding')
async def onboarding_status():
    from .onboarding import status
    return await status(store)

@app.post('/api/onboarding')
async def onboarding_complete(request:Request):
    if any(not r.get('finished') for r in engine.runs.values()):raise ValueError('Finish or stop active tasks before setting up your workspace')
    from .onboarding import complete
    return await complete(store,await request.json())

@app.post('/api/identity/require')
async def identity_require(request:Request):
    from .identity import set_required
    return await identity_call(set_required(bool((await request.json()).get('enabled'))))

@app.post('/api/identity/logout')
async def identity_logout():
    from .identity import logout
    return await identity_call(logout())

@app.post('/api/identity/cancel')
async def identity_cancel(request:Request):
    from .identity import cancel
    return cancel((await request.json()).get('flow_id',''))

@app.get('/api/identity/devices')
async def identity_devices():
    from .identity import devices
    return await identity_call(devices())

@app.post('/api/identity/devices/{id}/revoke')
async def identity_revoke(id:str):
    from .identity import revoke_device
    return await identity_call(revoke_device(id))

@app.post('/api/identity/devices/revoke-others')
async def identity_revoke_others():
    from .identity import revoke_others
    return await identity_call(revoke_others())

@app.post('/api/accounts/{id}/migration')
async def account_migration(id:str,request:Request):
    from .profiles import migrate
    from .identity import status as identity_status
    choice=(await request.json()).get('choice')
    account=None
    if choice=='attach':
        info=await identity_status()
        if not info.get('signed_in'):raise ValueError('Sign in before attaching a profile to your account')
        account=info.get('account') or {'id':info['user']['id']}
    return migrate(id,choice,account)

@app.post('/api/accounts')
async def account_create(request:Request):
    from .profiles import create
    return create((await request.json()).get('name',''))

@app.post('/api/accounts/{id}/select')
async def account_select(id:str):
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before switching profiles')
    from .profiles import select
    return select(id)

def insights_zone(): return str(store.setting('insights_timezone','') or '')

def insights_sync_public():
    from .usage import sync_state
    state=sync_state(store)
    return {k:state.get(k) for k in ('enabled','last_sync','last_error','days_sent')}|{'enabled':bool(state.get('enabled'))}

@app.get('/api/compaction/metrics')
async def compaction_metrics(): return usage.compaction()

@app.get('/api/insights')
async def insights():
    from .identity import status as identity_status
    return {**usage.summary(insights_zone()),'sync':insights_sync_public(),'account':profile_account_snapshot(await identity_status())}

def profile_account_snapshot(identity):
    from .usage import account_view,activity_grid
    saved=store.setting('insights_account',None)
    if not(identity.get('signed_in') and saved and saved.get('account_id')==identity.get('account',{}).get('id') and insights_sync_public().get('enabled')):return None
    account=account_view({'account_id':saved['account_id'],'devices':saved.get('devices',0),'days':saved.get('daily',[])},insights_zone())
    account['grid']=activity_grid(account['daily'],account['first_day'],insights_zone())
    account['busiest_day']=max(({'day':d['day'],'tokens':d['metrics'].get('tokens_in',0)+d['metrics'].get('tokens_out',0)} for d in account['daily']),key=lambda d:d['tokens'],default=None)
    return account

@app.get('/api/profile-overview')
async def profile_overview():
    from .usage import activity_grid,account_view,zone
    from .identity import status as identity_status
    identity=await identity_status();tz_name=insights_zone();summary=usage.summary(tz_name)
    tz,_=zone(tz_name);grid=activity_grid(usage.days(tz),summary.get('coverage_start'),tz_name)
    account=profile_account_snapshot(identity)
    from .profiles import status as profile_status
    return {'identity':identity,'profiles':profile_status(),'local':summary,'grid':grid,'account':account,'sync':insights_sync_public()}

@app.post('/api/insights/timezone')
async def insights_timezone(request:Request):
    from .usage import zone
    name=str((await request.json()).get('timezone') or '').strip()[:64]
    if name and (not re.fullmatch(r'[A-Za-z_]+(/[A-Za-z0-9_+-]+){0,2}|UTC',name) or zone(name)[1]!=name): raise ValueError('Unknown time zone. Use a name such as Europe/Amsterdam or America/New_York, or leave it empty for this PC.')
    store.set_setting('insights_timezone',name); return {'timezone':name}

async def insights_upload():
    import httpx
    from .usage import sync,sync_state
    try:
        result=await sync(store,usage,insights_zone())
        store.set_setting('insights_account',result['account']); return result
    except (ValueError,httpx.HTTPError) as error:
        state=sync_state(store); state['last_error']=str(error)[:200] if isinstance(error,ValueError) else 'Sign-in service is unavailable. Try again later.'
        store.set_setting('insights_sync',state); raise ValueError(state['last_error']) from None

@app.post('/api/insights/sync-setting')
async def insights_sync_setting(request:Request):
    from .usage import sync_state
    enabled=bool((await request.json()).get('enabled'))
    state=sync_state(store)
    if enabled:
        from .identity import status as identity_status
        if not (await identity_status()).get('signed_in'): raise ValueError('Sign in before turning on insights sync')
    state['enabled']=enabled; store.set_setting('insights_sync',state)
    if enabled: await insights_upload()
    return insights_sync_public()

@app.post('/api/insights/sync')
async def insights_sync_now():
    from .usage import sync_state
    if not sync_state(store).get('enabled'): raise ValueError('Turn on insights sync first')
    result=await insights_upload()
    return {'sent':result['sent'],'account':result['account'],'sync':insights_sync_public()}

@app.get('/api/insights/export')
async def insights_export():
    body=json.dumps(usage.export(insights_zone()),ensure_ascii=False,indent=1)
    return Response(body,media_type='application/json',headers={'Content-Disposition':'attachment; filename="luminaria-insights.json"'})

@app.post('/api/insights/delete')
async def insights_delete(request:Request):
    import httpx
    from .usage import service,sync_state
    scope=(await request.json()).get('scope')
    if scope not in ('local','synced','all'): raise ValueError('Choose what to delete')
    result={}
    if scope in ('synced','all'):
        try: result['synced']=(await service('POST','/insights/delete',{})).get('deleted',0)
        except httpx.HTTPError: raise ValueError('Sign-in service is unavailable, so synced insights were not deleted. Nothing was removed.') from None
        state=sync_state(store); state['enabled']=False; store.set_setting('insights_sync',state); store.set_setting('insights_account',None)
    if scope in ('local','all'): result['local']=usage.delete()
    return result

tuning=None
file_workflows=None

def workflow_service():
    global file_workflows
    if file_workflows is None:
        from .file_workflows import Workflows
        file_workflows=Workflows(store)
    return file_workflows

@app.get('/api/file-workflows')
async def workflow_list():
    from .config import full_access
    service=workflow_service()
    return {'workflows':service.list(),'active':service.active,'full_access':full_access()}

@app.post('/api/file-workflows')
async def workflow_create(request:Request):
    from .file_workflows import create
    return create(store,await request.json())

@app.post('/api/file-workflows/{id}/run')
async def workflow_run(id:str,request:Request):
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()):raise ValueError('Finish active work before starting a file workflow.')
    body=await request.json()
    if body.get('approved') is not True:raise ValueError('Review the saved steps and explicitly approve execution.')
    result=workflow_service().start(id,body.get('all_steps') is True)
    # Reuse the existing inference/model-management exclusion while files are changing.
    benchmarking=True
    def finished(task):
        global benchmarking
        benchmarking=False;broadcast({'type':'changed'})
    workflow_service().task.add_done_callback(finished)
    return result

@app.post('/api/file-workflows/{id}/stop')
async def workflow_stop(id:str):
    if workflow_service().active not in (None,id):raise ValueError('A different workflow is active.')
    return workflow_service().stop()

@app.post('/api/file-workflows/{id}/inspect')
async def workflow_inspect(id:str):
    if workflow_service().busy():raise ValueError('Stop or finish the active workflow before inspecting recovery.')
    from .file_workflows import get
    return workflow_service().recover(get(store,id))

@app.post('/api/file-workflows/{id}/accept')
async def workflow_accept(id:str):return workflow_service().accept(id)

@app.post('/api/file-workflows/{id}/restore')
async def workflow_restore(id:str,request:Request):
    body=await request.json()
    if body.get('approved') is not True:raise ValueError('Explicit restoration approval is required.')
    return workflow_service().restore(id,body.get('step'))

def tuning_service():
    global tuning
    if tuning is None:
        from .hardware import Tuning
        tuning=Tuning(store)
    return tuning

@app.get('/api/hardware')
async def hardware_info():
    from .hardware import information
    from .models import registry
    return {**await asyncio.to_thread(information),'models':[{'id':m['id'],'name':m['name']} for m in registry() if Path(m.get('model_file','')).is_file()]}

@app.get('/api/tuning')
async def tuning_status():
    return {'job':tuning_service().public(),'history':store.setting('tuning_history',[]),'rollback_available':bool(store.setting('tuning_rollback',None))}

@app.post('/api/tuning/start')
async def tuning_start(request:Request):
    global benchmarking
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish active work before starting a tuning benchmark.')
    body=await request.json()
    if body.get('consent') is not True:raise ValueError('Explicit benchmark consent is required.')
    from .models import registry
    from .hardware import information
    model=next((m for m in registry() if m['id']==body.get('model') and Path(m.get('model_file','')).is_file()),None)
    if not model:raise ValueError('Select an installed model; no weights are downloaded.')
    hardware=await asyncio.to_thread(information)
    if body.get('smart'):
        # Measure around this PC's estimated fit point instead of fixed guesses.
        from .hardware import smart_candidates
        from .model_library import fit_for,machine_profile
        from .model_catalog import CATALOG
        from .model_catalog_data import REPOS
        from . import fit
        name=Path(model['model_file']).name
        entry=next((e for e in CATALOG if any(q['filename']==name for q in e['quants'])),None)
        quant=next((q for q in entry['quants'] if q['filename']==name),None) if entry else {'bytes':Path(model['model_file']).stat().st_size}
        plan=fit_for(entry or {'context':model.get('context')},quant,fit.machine(hardware,CONFIG.get('hardware_override')))
        layers=(REPOS.get(entry['repo']) or {}).get('layers',40) if entry else 40
        body={**body,**smart_candidates(plan and {**plan,**plan['settings']},layers,hardware.get('physical_cores')),'ubatch':(plan or {}).get('settings',{}).get('ubatch',128)}
    benchmarking=True
    try:
        result=tuning_service().start(model,body,hardware)
        def finished(task):
            global benchmarking
            benchmarking=False
            broadcast({'type':'changed'})
        tuning_service().task.add_done_callback(finished)
        return result
    except BaseException:
        benchmarking=False;raise

@app.post('/api/tuning/stop')
async def tuning_stop():return await tuning_service().cancel()

@app.post('/api/tuning/apply')
async def tuning_apply(request:Request):
    if benchmarking or any(not r.get('finished') for r in engine.runs.values()):raise ValueError('Finish active work before selecting tuning settings.')
    from .hardware import information,apply_profile
    body=await request.json()
    return apply_profile(store,body.get('job'),await asyncio.to_thread(information),body.get('rollback') is True)

app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='ui')

