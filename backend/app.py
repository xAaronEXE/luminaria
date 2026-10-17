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

TOKEN=secrets.token_urlsafe(32)
store=Store(DATA/'studio.sqlite3')
subscribers=set(); connectors={}; engine=None; benchmarking=False

def broadcast(event):
    for queue in tuple(subscribers):
        if not queue.full(): queue.put_nowait(event)

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
    await engine.restore()
    task=asyncio.create_task(scheduler())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError): await task
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
    if request.headers.get('content-length') and int(request.headers['content-length'])>limit: return JSONResponse({'error':'Request too large'},413)
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
    return {'chats':store.chats(),'chat':chat,'messages':store.messages(chat) if chat else [],'actions':store.actions(chat) if chat else [],'summary':store.summary(chat) if chat else None,'summaries':store.rows('SELECT id,through_id,created FROM summaries WHERE chat=? ORDER BY id',(chat,)) if chat else [],'run':engine.public_run(chat),'context':store.setting('context:'+chat,{}),'plan':store.setting('plan:'+chat,None) if chat else None,'orchestration':{'router':CONFIG.get('orchestrator_model',''),'enabled':bool(CONFIG.get('orchestrator_model')) and CONFIG.get('orchestration_enabled',True)},'memories':store.memory(),'schedules':store.rows('SELECT * FROM schedules ORDER BY next_run'),'workspace':CONFIG['workspace'],'model':CONFIG['model'],'context_limit':CONFIG['context'],'connectors':{n:{'status':c.status,'tools':len(c.tools)} for n,c in connectors.items()},'tool_count':len(engine.tools.catalog()),'active_runs':[{'chat':k,'phase':v['phase']} for k,v in engine.runs.items() if not v.get('finished')]}

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
    if len(attachments)>4: raise ValueError('Attach at most four files per turn')
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
    return {'run_id':engine.start(id,bool(b.get('reasoning',False)),plan_only=bool(b.get('plan_only',False)))}

MAX_CONTINUATIONS=5

@app.post('/api/chats/{id}/continue')
async def continue_chat(id:str):
    require_chat(id)
    previous=engine.public_run(id)
    if not previous or not previous.get('finished') or not previous.get('checkpoint'): raise ValueError('There is no checkpoint to continue from')
    if previous.get('continuations',0)>=MAX_CONTINUATIONS: raise ValueError(f'This task has already been continued {MAX_CONTINUATIONS} times. Review the results above, then give a new instruction.')
    store.add(id,{'role':'user','content':'Continue the task from the checkpoint above. Steps that already succeeded are listed there; do not repeat them. If the same approach keeps failing, try a different one or explain what is blocking.'})
    return {'run_id':engine.start(id,bool(previous.get('reasoning')),continue_from=previous)}

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
        return await asyncio.to_thread(save,str(b['name']),raw)
    if len(raw)>8_000_000: raise ValueError('Image exceeds 8 MB')
    img=Image.open(io.BytesIO(raw)); img.verify()
    if img.format not in ('PNG','JPEG','WEBP'): raise ValueError('PNG, JPEG or WebP required')
    if img.width*img.height>30_000_000: raise ValueError('Image dimensions too large')
    ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}[img.format]; id=uid()+'.'+ext
    folder=DATA/'attachments'; folder.mkdir(exist_ok=True); (folder/id).write_bytes(raw)
    return {'id':id,'mime':'image/'+('jpeg' if ext=='jpg' else ext),'name':str(b.get('name','Image'))[:100]}

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
    return await engine.tools.call('read_file',{'path':path,'limit':32000},{})

@app.get('/api/file/download')
async def download(path:str):
    p=workspace_path(path)
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

@app.post('/api/memories')
async def memory_save(request:Request):
    b=await request.json(); title=str(b.get('title','')).strip(); content=str(b.get('content','')).strip()
    if not title or not content: raise ValueError('Title and memory text are required')
    if len(content)>6000: raise ValueError('Keep each memory below 6,000 characters')
    if sum(len(m['content']) for m in store.memory() if m['id']!=b.get('id'))+len(content)>16000: raise ValueError('Pinned memory limit reached. Shorten existing notes to leave room for conversation.')
    id=store.save_memory(title[:120],content,id=b.get('id')); broadcast({'type':'changed'}); return {'id':id}

@app.delete('/api/memories/{id}')
async def memory_delete(id:str): store.execute('DELETE FROM memories WHERE id=?',(id,)); broadcast({'type':'changed'}); return {'ok':True}

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
    public['data_directory']=str(DATA); public['mcp_configured']=list(CONFIG.get('mcp',{})); return public

@app.post('/api/workspace/browse')
async def browse_workspace():
    from .folder_picker import pick
    return await asyncio.to_thread(pick,CONFIG['workspace'])

@app.post('/api/settings')
async def settings_save(request:Request):
    if any(not r.get('finished') for r in engine.runs.values()): raise ValueError('Finish or stop active tasks before changing settings')
    b=await request.json(); allowed={'workspace','endpoint','tokenizer','model','context','output_tokens','compact_ratio','python','node','llama_executable','model_file','projector_file','external_tools','ask_reads'}
    allowed.update({'access_mode','orchestrator_model','compact_keep_turns','orchestration_pool','orchestration_enabled'})
    if 'orchestration_pool' in b:
        from .orchestration import normalize_pool
        b['orchestration_pool']=normalize_pool(b['orchestration_pool'])
    if 'orchestration_enabled' in b and not isinstance(b['orchestration_enabled'],bool): raise ValueError('Boolean setting required')
    if b.get('orchestrator_model'):
        from .models import registry
        if not any(m['id']==b['orchestrator_model'] and Path(m['model_file']).is_file() for m in registry()):raise ValueError('Choose an installed orchestration model')
    if 'access_mode' in b and b['access_mode'] not in ('review','full'): raise ValueError('Choose review or full access')
    changes={k:v for k,v in b.items() if k in allowed}
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
    if 'workspace' in changes: Path(changes['workspace']).mkdir(parents=True,exist_ok=True)
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
        return {'connected':True,'loaded':loaded,'models':r.json().get('data',[]),'model':CONFIG['model'],'manager':manager_state()}
    except Exception as e:
        state=manager_state();problem=diagnose() if state['owned'] and not state['running'] else None
        return {'connected':False,'loaded':False,'error':str(e),'model':CONFIG['model'],'manager':state,'problem':problem}

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
    r=await engine.client.post('http://127.0.0.1:8098/models/unload',timeout=20)
    r.raise_for_status(); return {'ok':True}

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
    return [{**s,'enabled':store.setting('skill:'+s['name'],True)} for s in catalog(connectors)]

@app.post('/api/skills')
async def skill_import(request:Request):
    from .skills import save_skill
    b=await request.json(); return save_skill(b['name'],b['content'])

@app.get('/api/skills/{name}')
async def skill_instructions(name:str):
    from .skills import load_skill
    return load_skill(name)

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

@app.post('/api/permissions/reset')
async def reset_permissions(): store.execute("DELETE FROM settings WHERE key LIKE 'permission:%'");return {'ok':True}

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

@app.post('/api/models/{id}/select')
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
    b=await request.json();store.set_setting('skill:'+name,bool(b['enabled']));return {'ok':True}

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

@app.get('/api/accounts')
async def accounts():
    from .profiles import status
    from .identity import status as identity_status
    return {**status(),'identity':await identity_status()}

@app.post('/api/identity/start')
async def identity_start(request:Request):
    from .identity import start
    return await identity_call(start((await request.json()).get('provider')))

async def identity_call(operation):
    import httpx
    try:return await operation
    except httpx.HTTPError:raise HTTPException(503,'Sign-in service is unavailable. Check your connection and try again.') from None

@app.post('/api/identity/poll')
async def identity_poll(request:Request):
    if any(not r.get('finished') for r in engine.runs.values()):raise ValueError('Finish or stop active tasks before completing sign-in')
    from .identity import poll
    return await identity_call(poll((await request.json()).get('flow_id','')))

@app.get('/api/gate')
async def gate_status(force:bool=False):
    from .identity import gate
    return await gate(force)

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

app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='ui')

