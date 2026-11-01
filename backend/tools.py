import asyncio, base64, json, os, re, subprocess
from pathlib import Path
from .config import CONFIG, DATA, workspace_path as _wp, full_access, external_tools_enabled, find_runtime, runtime_missing_message, runtime_path_dirs
def workspace_path(path='.',write=False): return _wp(path,roam=True,write=write)

def schema(name,description,properties,required=(),tier='auto',group='workspace'):
    return {'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False},'tier':tier,'group':group}
S={'type':'string'}; I={'type':'integer'}
BUILTINS=[
 schema('list_skills','List installed reusable workflow skills.',{},[],'auto','skills'),
 schema('find_capability','Search Luminaria\'s built-in catalog of thousands of real skills (workflows) and connectors (tools for other apps and services) when no installed skill or tool fits the task. Returns IDs to pass to install_capability.',{'query':S,'kind':{'type':'string','enum':['any','skills','connectors']}},['query'],'auto','skills'),
 schema('install_capability','Install a skill or connector from find_capability by its ID so you can use it in this task. Skills are downloaded at a pinned commit; connectors run third-party code. Requires user approval.',{'id':S},['id'],'approve','skills'),
 schema('load_skill','Read a named workflow skill before using it.',{'name':S},['name'],'auto','skills'),
 schema('finish_skill','Finish a loaded skill by checking its output files exist. Optionally list the action IDs of sources you used.',{'name':S,'outputs':{'type':'array','items':S,'minItems':1,'maxItems':10},'evidence_actions':{'type':'array','items':S,'maxItems':30}},['name','outputs'],'auto','skills'),
 schema('create_file_workflow','Only when the user explicitly asks for a reviewable plan of changes to many existing files: saves a plan for review in Tools → File workflows and does not execute it. Never use this to create documents; make those with run_code. Declare the user objective, allowed workspace locations, completion criteria, and read/create/edit/trash steps. No shell, permanent deletion, or application control.',{'objective':S,'completion_criteria':S,'allowed_locations':{'type':'array','items':S,'minItems':1,'maxItems':10},'steps':{'type':'array','minItems':1,'maxItems':50,'items':{'type':'object','properties':{'action':{'type':'string','enum':['read','create','edit','trash']},'path':S,'content':S,'old_text':S,'new_text':S},'required':['action','path'],'additionalProperties':False}}},['objective','completion_criteria','allowed_locations','steps'],'approve','planning'),
 schema('list_files','List a workspace directory.',{'path':S}),
 schema('read_file','Read a UTF-8 workspace file, with optional offset and limit in characters.',{'path':S,'offset':I,'limit':I},['path']),
 schema('write_file','Create or replace a UTF-8 workspace file. Requires user approval.',{'path':S,'content':S},['path','content'],'approve'),
 schema('edit_file','Replace exactly one occurrence of old_text in a workspace file.',{'path':S,'old_text':S,'new_text':S},['path','old_text','new_text'],'approve'),
 schema('delete_file','Delete one workspace file (never directories). Always asks.',{'path':S},['path'],'always'),
 schema('search_files','Search text files in the workspace for a literal string.',{'query':S},['query']),
 schema('run_command','Run a PowerShell command in the workspace. Full PC access after approval; not a sandbox. python, pip, node and npx are available.',{'command':S,'timeout':I},['command'],'always','execution'),
 schema('run_code','Execute a Python or JavaScript script in the workspace. Saved as a file; no hidden REPL state.',{'language':{'type':'string','enum':['python','javascript']},'code':S,'timeout':I},['language','code'],'always','execution'),
 schema('web_search','Search the public web. Returns status, titles, snippets and source URLs. An empty result means no matches for these words, not that the information does not exist.',{'query':S},['query'],'auto','research'),
 schema('web_fetch','Fetch a public HTTP(S) page or PDF. Network request requires approval. browser_fallback explicitly authorizes navigation and snapshot in the connected browser if JavaScript or sign-in is needed; never completes login dialogs or bypasses blocks. Public cache is bypassed for sensitive responses.',{'url':S,'refresh':{'type':'boolean'},'browser_fallback':{'type':'boolean'}},['url'],'approve','research'),
 schema('discover_tools','Load more tools. more: delete files, schedules, the working brief, conversation history, file workflows. browser or windows: those connectors. all: every connected app.',{'category':{'type':'string','enum':['more','browser','windows','all']}},['category'],'auto','system'),
 schema('inspect_file','Check that a file you made is real and valid: Word, Excel, PowerPoint, PDF, HTML, JSON, CSV, Markdown, code or image. Returns its type, size, a short preview and any problem found.',{'path':S},['path']),
 schema('memory_search','Search the user\'s memory (MEMORY.md) and earlier conversations by literal text.',{'query':S},['query'],'auto','memory'),
 schema('history_read','Retrieve bounded verbatim saved message or tool-output JSON by ID, offset and limit in characters. Small results include parsed original data; large results return excerpts with stable references. Original history remains on disk.',{'message_id':I,'action_id':S,'offset':I,'limit':I},[],'auto','memory'),
 schema('remember','Add a lasting fact or preference to the user\'s memory (MEMORY.md, under Notes). title is a short label. Requires approval.',{'title':S,'content':S},['title','content'],'approve','memory'),
 schema('update_plan','Share or revise your plan for a multi-step task. The user sees it as your stated plan, separate from executed actions, and it is saved with the chat. Send the full plan each time. Mark one step active while you work on it; list depends_on only for real dependencies.',{'goal':{'type':'string','description':'One sentence: what the finished work achieves.'},'steps':{'type':'array','minItems':1,'maxItems':24,'items':{'type':'object','properties':{'id':S,'title':S,'detail':{'type':'string','description':'What will be done and how it will be checked.'},'status':{'type':'string','enum':['pending','active','done','blocked','skipped']},'depends_on':{'type':'array','items':S}},'required':['id','title','status'],'additionalProperties':False}}},['steps'],'auto','planning'),
 schema('update_brief','Propose changes to the pinned working brief for this chat when the user states a goal, constraint, decision, pending item or reference to keep. The user sees and can edit it. You cannot add permissions or change entries the user wrote. Never copy passwords, keys or tokens; record where they are kept instead.',{'changes':{'type':'array','minItems':1,'maxItems':8,'items':{'type':'object','properties':{'op':{'type':'string','enum':['add','replace','remove']},'id':{'type':'string','description':'Entry id for replace or remove.'},'section':{'type':'string','enum':['goals','constraints','decisions','pending','references']},'text':{'type':'string','description':'One short sentence, under 300 characters.'}},'required':['op'],'additionalProperties':False}}},['changes'],'auto','planning'),
 schema('create_schedule','Schedule a recurring prompt while Studio is running. Every side effect still needs its normal approval. Minimum interval 5 minutes.',{'title':S,'prompt':S,'interval_minutes':I},['title','prompt','interval_minutes'],'approve','automation'),
]

# Shown only after discover_tools(more), or unlocked by the step that needs them, so small local models see a short,
# clear menu. They can still be called at any time; approvals apply as usual.
EXTRA_TOOLS=frozenset({'delete_file','history_read','update_brief','create_schedule','create_file_workflow','finish_skill','install_capability'})

RETRIEVAL={'web_search':'web search','web_fetch':'web','memory_search':'memory','search_files':'workspace files','read_file':'workspace file','history_read':'history'}

def host_of(url):
    from urllib.parse import urlsplit
    try: return urlsplit(url).hostname or ''
    except ValueError: return ''

def mcp_tier(group,name):
    # Only an explicit read-only allowlist is automatic. Dynamic/unknown tools always ask.
    if group=='windows' and name in ['ControlStatus','DisplayInventory','Snapshot','Screenshot']: return 'auto'
    if group=='browser' and name in ['browser_snapshot','browser_tabs','browser_console_messages','browser_network_requests','browser_take_screenshot']: return 'auto' if name!='browser_tabs' else 'approve'
    if re.search(r'delete|remove|install|send|powershell|filesystem|registry|process|evaluate|run_code',name,re.I): return 'always'
    return 'approve'

class Toolbox:
    def __init__(self,store,connectors): self.store=store; self.connectors=connectors; self.connector_installer=None
    def catalog(self):
        result=[dict(t) for t in BUILTINS if external_tools_enabled() or t['group']!='execution']
        if CONFIG.get('ask_reads',False):
            for t in result:
                if t['tier']=='auto' and t['group']!='planning': t['tier']='approve'
        for group,c in self.connectors.items():
            if not external_tools_enabled(): continue
            for t in c.tools:
                result.append({'name':group+'__'+t['name'],'description':t.get('description',''),'parameters':t['inputSchema'],'tier':mcp_tier(group,t['name']),'group':group})
        if full_access():
            for t in result:
                t['tier']='auto'
                t['description']=t['description'].replace('Requires user approval.', 'Runs automatically in Full access mode.').replace('Always asks.', 'Runs automatically in Full access mode.').replace('Network request requires approval.', 'Network requests run automatically.').replace('Full PC access after approval;', 'Full PC access;').replace('Every side effect still needs its normal approval.', 'Actions run automatically in Full access mode.')
        return result
    def definitions(self,enabled):
        enabled=set(enabled or ())
        def shown(t):
            if t['group'] in self.connectors: return t['group'] in enabled
            return t['name'] not in EXTRA_TOOLS or 'more' in enabled or t['name'] in enabled
        return [{'type':'function','function':{k:t[k] for k in ['name','description','parameters']}} for t in self.catalog() if shown(t)]
    def get(self,name):
        return next((t for t in self.catalog() if t['name']==name),None)
    @staticmethod
    def skill_paths(run):
        out=[]
        for folder in run.get('skill_folders',[]) if isinstance(run,dict) else []:
            for p in (Path(folder),Path(folder)/'scripts'):
                if p.is_dir(): out.append(str(p))
        return out
    async def process(self,argv,timeout=60,extra_path=()):
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        proc=await asyncio.create_subprocess_exec(*argv,cwd=CONFIG['workspace'],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=flags,env={**os.environ,'PATH':os.pathsep.join(runtime_path_dirs()+[os.environ.get('PATH','')]),'PYTHONIOENCODING':'utf-8',**({'PYTHONPATH':os.pathsep.join([*extra_path,os.environ.get('PYTHONPATH','')]).rstrip(os.pathsep)} if extra_path else {})})
        try:
            out,err=await asyncio.wait_for(proc.communicate(),min(max(timeout,1),180))
            return {'exit_code':proc.returncode,'stdout':out.decode('utf-8','replace'),'stderr':err.decode('utf-8','replace')}
        except BaseException:
            if proc.returncode is None:
                if os.name=='nt':
                    killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(proc.pid),'/T','/F',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,creationflags=flags)
                    await killer.wait()
                else: proc.kill()
                await proc.wait()
            raise
    async def call(self,name,a,run):
        if name not in RETRIEVAL: return await self.dispatch(name,a,run)
        import time
        from .store import uid
        started=time.monotonic(); result=None
        try:
            result=await self.dispatch(name,a,run)
            if isinstance(result,dict):
                result.setdefault('duration_ms',int((time.monotonic()-started)*1000)); result.setdefault('retrieved_at',round(time.time(),3)); result.setdefault('attempts',1); result.setdefault('truncated',False)
            return result
        except asyncio.CancelledError:
            result={'status':'cancelled'}; raise
        except Exception as e:
            category='not_found' if isinstance(e,FileNotFoundError) else 'permissions' if isinstance(e,PermissionError) else 'unsupported' if isinstance(e,UnicodeError) else 'invalid_input' if isinstance(e,ValueError) else 'retrieval_failed'
            result={'status':'error','category':category,'source':RETRIEVAL[name],'message':str(e)[:300],'attempts':1,'truncated':False,'retrieved_at':round(time.time(),3),'duration_ms':int((time.monotonic()-started)*1000)}
            return result
        finally:
            r=result if isinstance(result,dict) else {}
            # Diagnostics never store queries, URLs or content; only the source host for web fetches.
            try: self.store.execute('INSERT INTO retrieval_events VALUES(?,?,?,?,?,?,?,?,?,?)',(uid(),(run or {}).get('id'),name,r.get('status','ok'),r.get('category'),RETRIEVAL[name] if name!='web_fetch' else host_of(r.get('source') or a.get('url','')),r.get('duration_ms',int((time.monotonic()-started)*1000)),r.get('attempts',1),1 if r.get('cached') else 0,time.time()))
            except Exception: pass
    async def dispatch(self,name,a,run):
        if (name in ('run_command','run_code') or '__' in name) and not external_tools_enabled():
            raise ValueError('Computer and command tools are disabled. Enable them in Settings first.')
        if name=='update_plan':
            from .work import plan_steps
            steps=plan_steps(a)
            return {'recorded':len(steps),'active':next((x['id'] for x in steps if x['status']=='active'),None)}
        if name=='update_brief':
            from .brief import tool_update
            return tool_update(self.store,run['chat'],a)
        if name=='find_capability':
            run.setdefault('enabled',set()).add('install_capability')
            from .catalog import search
            found=await asyncio.to_thread(search,a['query'],{'any':None}.get(a.get('kind','any'),a.get('kind')),8)
            return {**found,'next':'Pick the best match and call install_capability with its id. Prefer items with more stars. Skip connectors with needs unless the user can supply them.'}
        if name=='install_capability':
            from .catalog import find,install_skill,connector_plan
            kind,item=find(a['id'])
            if kind=='skills':
                done=await asyncio.to_thread(install_skill,item)
                return {**done,'next':f"Call load_skill with name {done['name']} to use it."}
            if not self.connector_installer: raise ValueError('Connectors can only be installed while Luminaria is running')
            name,command,args=connector_plan(item)
            if name in CONFIG.get('mcp',{}): return {'kind':'connector','name':name,'status':'already installed','next':f'Call discover_tools with category all, then use tools named {name}__*.'}
            await self.connector_installer(name,{'command':command,'args':args,'cwd':CONFIG['workspace']})
            return {'kind':'connector','name':name,'status':'installed','next':f'Call discover_tools with category all, then use tools named {name}__*.'}
        if name=='list_skills':
            from .skills import catalog
            return [{k:s[k] for k in ('name','description','category','missing')} for s in catalog(self.connectors) if self.store.setting('skill:'+s['name'],True)]
        if name=='load_skill':
            from .skills import load_skill,preflight
            if not self.store.setting('skill:'+a['name'],True): raise ValueError('This skill is disabled')
            check=preflight(a['name'],self.connectors)
            from .skill_runs import set_state
            if not check['available']:
                if run.get('id'):set_state(self.store,a['name'],'Needs setup',check['reason'],run)
                return {'status':'error','category':'needs_setup',**check}
            instructions=load_skill(a['name']); run.setdefault('enabled',set()).add('finish_skill')
            if run.get('id'):set_state(self.store,a['name'],'Running','Instructions loaded; workflow outputs have not been verified.',run)
            folder=instructions.get('folder')
            if folder:
                # Scripts that ship with the skill can be imported by run_code and found by run_command.
                run.setdefault('skill_folders',[])
                if folder not in run['skill_folders']: run['skill_folders'].append(folder)
            files=instructions.get('files') or []
            how=(f"This skill's own files are in {folder} ({', '.join(files[:12])}{', …' if len(files)>12 else ''}). Run its scripts by full path, "
                 f"for example python \"{folder}\\scripts\\name.py\"; Python code you run can also import them directly. Outputs go in the working folder. ") if folder and files else ''
            return {**instructions,'state':'Running','how_to_use':how+'Do the steps yourself with tools (write files, run scripts); do not ask the user to do them.',
                    'completion':'Use finish_skill after producing output files and collecting evidence action IDs. Loading instructions alone is not completion.'}
        if name=='finish_skill':
            from .skill_runs import complete
            return complete(self.store,a['name'],a['outputs'],a.get('evidence_actions') or [],run)
        if name=='create_file_workflow':
            from .file_workflows import create
            plan=create(self.store,a)
            return {'workflow':plan['id'],'state':plan['state'],'steps':len(plan['steps']),'message':'Plan saved, not executed. Review it in Tools → File workflows before running steps.'}
        if '__' in name:
            group,tool=name.split('__',1)
            return await self.connectors[group].call(tool,a)
        if name=='inspect_file':
            from .file_check import inspect
            return inspect(workspace_path(a['path']))
        if name=='list_files':
            p=workspace_path(a.get('path','.')); root=Path(CONFIG['workspace']).resolve()
            show=lambda f:str(f.relative_to(root)) if f.is_relative_to(root) else str(f)
            return [{'name':f.name,'path':show(f),'directory':f.is_dir(),'bytes':f.stat().st_size if f.is_file() else 0} for f in sorted(p.iterdir(),key=lambda f:(not f.is_dir(),f.name.lower()))][:300]
        if name=='read_file':
            p=workspace_path(a['path'])
            if p.stat().st_size>8_000_000: raise ValueError('File is larger than 8 MB; use a targeted script')
            text=p.read_bytes().decode('utf-8'); offset=max(0,a.get('offset',0)); limit=min(max(a.get('limit',16000),1),32000)
            from .sources import document
            return {'path':a['path'],**document(text,'workspace:'+a['path'],offset,limit)}
        if name=='write_file':
            p=workspace_path(a['path'],write=True); p.parent.mkdir(parents=True,exist_ok=True)
            if len(a['content'])>2_000_000: raise ValueError('Write limit is 2 MB')
            if p.exists():
                backup=DATA/'backups'/run['id']; backup.mkdir(parents=True,exist_ok=True)
                import shutil; shutil.copy2(p,backup/(str(__import__('time').time_ns())+'-'+p.name))
            p.write_text(a['content'],encoding='utf-8'); return {'saved':str(p),'bytes':p.stat().st_size}
        if name=='edit_file':
            p=workspace_path(a['path'],write=True); text=p.read_text('utf-8')
            if not a['old_text'] or text.count(a['old_text'])!=1: raise ValueError('old_text must match exactly once; read the file and retry')
            return await self.call('write_file',{'path':a['path'],'content':text.replace(a['old_text'],a['new_text'],1)},run)
        if name=='delete_file':
            p=workspace_path(a['path'],write=True)
            if not p.is_file(): raise ValueError('Only individual files may be deleted')
            import shutil,time
            backup=DATA/'backups'/run['id']; backup.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,backup/(str(time.time_ns())+'-'+p.name)); p.unlink(); return {'deleted':str(p),'backup':str(backup)}
        if name=='search_files':
            from .sources import search_workspace
            return await search_workspace(workspace_path(),a['query'])
        if name=='run_command': return await self.process(['powershell.exe','-NoProfile','-NonInteractive','-Command',a['command']],a.get('timeout',60),extra_path=self.skill_paths(run))
        if name=='run_code':
            folder=DATA/'scripts'; folder.mkdir(parents=True,exist_ok=True)  # scratch scripts stay in Luminaria's folder, not the user's
            p=folder/(run['id']+'-'+str(__import__('time').time_ns())+('.py' if a['language']=='python' else '.js'))
            p.write_text(a['code'],encoding='utf-8')
            kind='python' if a['language']=='python' else 'node'
            exe=find_runtime(kind)
            if not exe: return {'status':'error','category':'needs_setup','message':runtime_missing_message(kind)}
            return await self.process([exe,str(p)],a.get('timeout',60),extra_path=self.skill_paths(run))
        if name=='web_search':
            from .retrieval import search
            return await search(a['query'])
        if name=='web_fetch':
            from .retrieval import fetch
            result=await fetch(a['url'],bool(a.get('refresh')))
            if a.get('browser_fallback') and result.get('category') in ('needs_javascript','auth','extraction'):
                if not external_tools_enabled():return {**result,'guidance':'Enable external tools and connect a browser before authorizing browser fallback.'}
                from .browser_retrieval import fetch as browser_fetch
                return await browser_fetch(self.connectors.get('browser'),a['url'])
            return result
        if name=='discover_tools':
            if a['category']=='more':
                run['enabled'].add('more')
                return [{'name':t['name'],'description':t['description'][:300],'approval':t['tier']} for t in self.catalog() if t['name'] in EXTRA_TOOLS]
            cats=list(self.connectors) if a['category']=='all' else [a['category']]
            run['enabled'].update(cats)
            return [{'name':t['name'],'description':t['description'][:300],'approval':t['tier']} for t in self.catalog() if t['group'] in cats]
        if name=='memory_search':
            q=a['query'].lower()
            if not q.strip() or len(q)>500:raise ValueError('Provide a non-empty literal query of at most 500 characters')
            from .memory_file import search as memory_lines
            memories=memory_lines(self.store,q)
            rows=self.store.rows('SELECT id,chat,payload FROM messages WHERE instr(lower(payload),?)>0 ORDER BY id DESC LIMIT 15',(q,))
            from .sources import matches
            history=[dict(id=r['id'],chat=r['chat'],matches=matches(str(json.loads(r['payload']).get('content','')),'message:'+str(r['id']),q,3)) for r in rows]
            found=bool(memories or history)
            return {'status':'ok' if found else 'empty','source':'memory and saved history','memories':memories,'history':history,**({} if found else {'message':'No saved memory or message contains this exact text. Try a shorter or different phrase.'})}
        if name=='history_read':
            from .sources import saved_object
            offset=a.get('offset',0);limit=a.get('limit',6000)
            if a.get('message_id'):
                rows=self.store.rows('SELECT payload FROM messages WHERE id=?',(a['message_id'],)); return saved_object(rows[0]['payload'],'message:'+str(a['message_id']),'message',offset,limit) if rows else {'status':'error','category':'not_found','source':'saved message','message':'No saved message has this ID.'}
            if a.get('action_id'):
                id=a['action_id']
                if not re.fullmatch('[a-f0-9]{32}',id): raise ValueError('Invalid action ID')
                p=DATA/'tool-outputs'/(id+'.json')
                if not p.exists():return {'status':'error','category':'not_found','source':'saved tool output','message':'No saved output exists for this action ID.'}
                if p.stat().st_size>32_000_000:return {'status':'error','category':'too_large','source':'saved tool output','message':'Saved output exceeds 32 MB. Download it from Activity and inspect a targeted part.'}
                return saved_object(p.read_bytes().decode('utf-8'),'action:'+id,'output',offset,limit)
            raise ValueError('Supply message_id or action_id')
        if name=='remember':
            from .memory_file import remember
            return remember(self.store,a.get('title',''),a['content'])
        if name=='create_schedule':
            from .store import uid,now
            id=uid(); interval=max(5,a['interval_minutes'])*60
            self.store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',(id,a['title'],a['prompt'],interval,now()+interval))
            return {'id':id,'interval_seconds':interval,'note':'Runs only while Studio is open. Side effects wait for approval.'}
        raise ValueError('Unknown tool')
