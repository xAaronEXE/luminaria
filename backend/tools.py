import asyncio, base64, json, os, re, subprocess
from pathlib import Path
from .config import CONFIG, DATA, workspace_path as _wp, full_access, external_tools_enabled, find_runtime, runtime_missing_message, runtime_path_dirs
def workspace_path(path='.'): return _wp(path,roam=True)

def schema(name,description,properties,required=(),tier='auto',group='workspace'):
    return {'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False},'tier':tier,'group':group}
S={'type':'string'}; I={'type':'integer'}
BUILTINS=[
 schema('list_skills','List installed reusable workflow skills.',{},[],'auto','skills'),
 schema('load_skill','Read a named workflow skill before using it.',{'name':S},['name'],'auto','skills'),
 schema('finish_skill','Verify output files and finish a loaded skill. Supply successful evidence action IDs from this run. File readback/hashes establish existence, not semantic correctness.',{'name':S,'outputs':{'type':'array','items':S,'minItems':1,'maxItems':10},'evidence_actions':{'type':'array','items':S,'minItems':1,'maxItems':30}},['name','outputs','evidence_actions'],'auto','skills'),
 schema('create_file_workflow','Propose a bounded file workflow for user review in Tools → File workflows. Does not execute file steps. Declare the user objective, allowed workspace locations, completion criteria, and read/create/edit/trash steps. No shell, permanent deletion, or application control.',{'objective':S,'completion_criteria':S,'allowed_locations':{'type':'array','items':S,'minItems':1,'maxItems':10},'steps':{'type':'array','minItems':1,'maxItems':50,'items':{'type':'object','properties':{'action':{'type':'string','enum':['read','create','edit','trash']},'path':S,'content':S,'old_text':S,'new_text':S},'required':['action','path'],'additionalProperties':False}}},['objective','completion_criteria','allowed_locations','steps'],'approve','planning'),
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
 schema('discover_tools','Load MCP tool schemas for browser or windows. Call before using those tools. Use category all to list every connected tool.',{'category':{'type':'string','enum':['browser','windows','all']}},['category'],'auto','system'),
 schema('memory_search','Search durable cross-chat memory and full saved conversation text by literal query.',{'query':S},['query'],'auto','memory'),
 schema('history_read','Retrieve bounded verbatim saved message or tool-output JSON by ID, offset and limit in characters. Small results include parsed original data; large results return excerpts with stable references. Original history remains on disk.',{'message_id':I,'action_id':S,'offset':I,'limit':I},[],'auto','memory'),
 schema('remember','Save an explicit durable fact, preference or project decision with provenance. Requires approval.',{'title':S,'content':S},['title','content'],'approve','memory'),
 schema('update_plan','Share or revise your plan for a multi-step task. The user sees it as your stated plan, separate from executed actions, and it is saved with the chat. Send the full plan each time. Mark one step active while you work on it; list depends_on only for real dependencies.',{'goal':{'type':'string','description':'One sentence: what the finished work achieves.'},'steps':{'type':'array','minItems':1,'maxItems':24,'items':{'type':'object','properties':{'id':S,'title':S,'detail':{'type':'string','description':'What will be done and how it will be checked.'},'status':{'type':'string','enum':['pending','active','done','blocked','skipped']},'depends_on':{'type':'array','items':S}},'required':['id','title','status'],'additionalProperties':False}}},['steps'],'auto','planning'),
 schema('update_brief','Propose changes to the pinned working brief for this chat when the user states a goal, constraint, decision, pending item or reference to keep. The user sees and can edit it. You cannot add permissions or change entries the user wrote. Never copy passwords, keys or tokens; record where they are kept instead.',{'changes':{'type':'array','minItems':1,'maxItems':8,'items':{'type':'object','properties':{'op':{'type':'string','enum':['add','replace','remove']},'id':{'type':'string','description':'Entry id for replace or remove.'},'section':{'type':'string','enum':['goals','constraints','decisions','pending','references']},'text':{'type':'string','description':'One short sentence, under 300 characters.'}},'required':['op'],'additionalProperties':False}}},['changes'],'auto','planning'),
 schema('create_schedule','Schedule a recurring prompt while Studio is running. Every side effect still needs its normal approval. Minimum interval 5 minutes.',{'title':S,'prompt':S,'interval_minutes':I},['title','prompt','interval_minutes'],'approve','automation'),
]

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
    def __init__(self,store,connectors): self.store=store; self.connectors=connectors
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
        return [{'type':'function','function':{k:t[k] for k in ['name','description','parameters']}} for t in self.catalog() if t['group'] not in self.connectors or t['group'] in enabled]
    def get(self,name):
        return next((t for t in self.catalog() if t['name']==name),None)
    async def process(self,argv,timeout=60):
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        proc=await asyncio.create_subprocess_exec(*argv,cwd=CONFIG['workspace'],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=flags,env={**os.environ,'PATH':os.pathsep.join(runtime_path_dirs()+[os.environ.get('PATH','')]),'PYTHONIOENCODING':'utf-8'})
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
            instructions=load_skill(a['name'])
            if run.get('id'):set_state(self.store,a['name'],'Running','Instructions loaded; workflow outputs have not been verified.',run)
            return {**instructions,'state':'Running','completion':'Use finish_skill after producing output files and collecting evidence action IDs. Loading instructions alone is not completion.'}
        if name=='finish_skill':
            from .skill_runs import complete
            return complete(self.store,a['name'],a['outputs'],a['evidence_actions'],run)
        if name=='create_file_workflow':
            from .file_workflows import create
            plan=create(self.store,a)
            return {'workflow':plan['id'],'state':plan['state'],'steps':len(plan['steps']),'message':'Plan saved, not executed. Review it in Tools → File workflows before running steps.'}
        if '__' in name:
            group,tool=name.split('__',1)
            return await self.connectors[group].call(tool,a)
        if name=='list_files':
            p=workspace_path(a.get('path','.'))
            return [{'name':f.name,'path':str(f.relative_to(Path(CONFIG['workspace']).resolve())),'directory':f.is_dir(),'bytes':f.stat().st_size if f.is_file() else 0} for f in sorted(p.iterdir(),key=lambda f:(not f.is_dir(),f.name.lower()))][:300]
        if name=='read_file':
            p=workspace_path(a['path'])
            if p.stat().st_size>8_000_000: raise ValueError('File is larger than 8 MB; use a targeted script')
            text=p.read_bytes().decode('utf-8'); offset=max(0,a.get('offset',0)); limit=min(max(a.get('limit',16000),1),32000)
            from .sources import document
            return {'path':a['path'],**document(text,'workspace:'+a['path'],offset,limit)}
        if name=='write_file':
            p=workspace_path(a['path']); p.parent.mkdir(parents=True,exist_ok=True)
            if len(a['content'])>2_000_000: raise ValueError('Write limit is 2 MB')
            if p.exists():
                backup=DATA/'backups'/run['id']; backup.mkdir(parents=True,exist_ok=True)
                import shutil; shutil.copy2(p,backup/(str(__import__('time').time_ns())+'-'+p.name))
            p.write_text(a['content'],encoding='utf-8'); return {'saved':str(p),'bytes':p.stat().st_size}
        if name=='edit_file':
            p=workspace_path(a['path']); text=p.read_text('utf-8')
            if not a['old_text'] or text.count(a['old_text'])!=1: raise ValueError('old_text must match exactly once; read the file and retry')
            return await self.call('write_file',{'path':a['path'],'content':text.replace(a['old_text'],a['new_text'],1)},run)
        if name=='delete_file':
            p=workspace_path(a['path'])
            if not p.is_file(): raise ValueError('Only individual files may be deleted')
            import shutil,time
            backup=DATA/'backups'/run['id']; backup.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,backup/(str(time.time_ns())+'-'+p.name)); p.unlink(); return {'deleted':str(p),'backup':str(backup)}
        if name=='search_files':
            from .sources import search_workspace
            return await search_workspace(workspace_path(),a['query'])
        if name=='run_command': return await self.process(['powershell.exe','-NoProfile','-NonInteractive','-Command',a['command']],a.get('timeout',60))
        if name=='run_code':
            folder=workspace_path('.studio-scripts'); folder.mkdir(exist_ok=True)
            p=folder/(run['id']+'-'+str(__import__('time').time_ns())+('.py' if a['language']=='python' else '.js'))
            p.write_text(a['code'],encoding='utf-8')
            kind='python' if a['language']=='python' else 'node'
            exe=find_runtime(kind)
            if not exe: return {'status':'error','category':'needs_setup','message':runtime_missing_message(kind)}
            return await self.process([exe,str(p)],a.get('timeout',60))
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
            cats=list(self.connectors) if a['category']=='all' else [a['category']]
            run['enabled'].update(cats)
            return [{'name':t['name'],'description':t['description'][:300],'approval':t['tier']} for t in self.catalog() if t['group'] in cats]
        if name=='memory_search':
            q=a['query'].lower()
            if not q.strip() or len(q)>500:raise ValueError('Provide a non-empty literal query of at most 500 characters')
            memories=[m for m in self.store.memory() if q in (m['title']+' '+m['content']).lower()]
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
            if len(a['content'])>6000 or sum(len(m['content']) for m in self.store.memory())+len(a['content'])>16000: raise ValueError('Pinned memory is full; shorten existing memories in the UI')
            return {'memory_id':self.store.save_memory(a['title'],a['content'],'chat:'+run['chat'])}
        if name=='create_schedule':
            from .store import uid,now
            id=uid(); interval=max(5,a['interval_minutes'])*60
            self.store.execute('INSERT INTO schedules VALUES(?,?,?,?,?,1)',(id,a['title'],a['prompt'],interval,now()+interval))
            return {'id':id,'interval_seconds':interval,'note':'Runs only while Studio is open. Side effects wait for approval.'}
        raise ValueError('Unknown tool')
