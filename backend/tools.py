import asyncio, base64, json, os, re, subprocess
from pathlib import Path
from .config import CONFIG, DATA, workspace_path, FULL_ACCESS, external_tools_enabled

def schema(name,description,properties,required=(),tier='auto',group='workspace'):
    return {'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False},'tier':tier,'group':group}
S={'type':'string'}; I={'type':'integer'}
BUILTINS=[
 schema('list_skills','List installed reusable workflow skills.',{},[],'auto','skills'),
 schema('load_skill','Read a named workflow skill before using it.',{'name':S},['name'],'auto','skills'),
 schema('list_files','List a workspace directory.',{'path':S}),
 schema('read_file','Read a UTF-8 workspace file, with optional offset and limit in characters.',{'path':S,'offset':I,'limit':I},['path']),
 schema('write_file','Create or replace a UTF-8 workspace file. Requires user approval.',{'path':S,'content':S},['path','content'],'approve'),
 schema('edit_file','Replace exactly one occurrence of old_text in a workspace file.',{'path':S,'old_text':S,'new_text':S},['path','old_text','new_text'],'approve'),
 schema('delete_file','Delete one workspace file (never directories). Always asks.',{'path':S},['path'],'always'),
 schema('search_files','Search text files in the workspace for a literal string.',{'query':S},['query']),
 schema('run_command','Run a PowerShell command in the workspace. Full PC access after approval; not a sandbox. Use python/node configured paths from system prompt.',{'command':S,'timeout':I},['command'],'always','execution'),
 schema('run_code','Execute a Python or JavaScript script in the workspace. Saved as a file; no hidden REPL state.',{'language':{'type':'string','enum':['python','javascript']},'code':S,'timeout':I},['language','code'],'always','execution'),
 schema('web_search','Search the public web. Returns titles, snippets and source URLs.',{'query':S},['query'],'auto','research'),
 schema('web_fetch','Fetch an HTTP(S) page and extract text. Network request requires approval.',{'url':S},['url'],'approve','research'),
 schema('discover_tools','Load MCP tool schemas for browser or windows. Call before using those tools. Use category all to list every connected tool.',{'category':{'type':'string','enum':['browser','windows','all']}},['category'],'auto','system'),
 schema('memory_search','Search durable cross-chat memory and full saved conversation text by literal query.',{'query':S},['query'],'auto','memory'),
 schema('history_read','Retrieve saved message or complete tool output by ID. Original history remains after compaction.',{'message_id':I,'action_id':S},[],'auto','memory'),
 schema('remember','Save an explicit durable fact, preference or project decision with provenance. Requires approval.',{'title':S,'content':S},['title','content'],'approve','memory'),
 schema('update_plan','Share or revise your plan for a multi-step task. The user sees it as your stated plan, separate from executed actions, and it is saved with the chat. Send the full plan each time. Mark one step active while you work on it; list depends_on only for real dependencies.',{'goal':{'type':'string','description':'One sentence: what the finished work achieves.'},'steps':{'type':'array','minItems':1,'maxItems':24,'items':{'type':'object','properties':{'id':S,'title':S,'detail':{'type':'string','description':'What will be done and how it will be checked.'},'status':{'type':'string','enum':['pending','active','done','blocked','skipped']},'depends_on':{'type':'array','items':S}},'required':['id','title','status'],'additionalProperties':False}}},['steps'],'auto','planning'),
 schema('create_schedule','Schedule a recurring prompt while Studio is running. Every side effect still needs its normal approval. Minimum interval 5 minutes.',{'title':S,'prompt':S,'interval_minutes':I},['title','prompt','interval_minutes'],'approve','automation'),
]

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
        if FULL_ACCESS:
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
        proc=await asyncio.create_subprocess_exec(*argv,cwd=CONFIG['workspace'],stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,creationflags=flags,env={**os.environ,'PYTHONIOENCODING':'utf-8'})
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
        if (name in ('run_command','run_code') or '__' in name) and not external_tools_enabled():
            raise ValueError('Computer and command tools are disabled. Enable them in Settings first.')
        if name=='update_plan':
            from .work import plan_steps
            steps=plan_steps(a)
            return {'recorded':len(steps),'active':next((x['id'] for x in steps if x['status']=='active'),None)}
        if name=='list_skills':
            from .skills import catalog
            return [{k:s[k] for k in ('name','description','category','missing')} for s in catalog(self.connectors) if self.store.setting('skill:'+s['name'],True)]
        if name=='load_skill':
            from .skills import load_skill
            if not self.store.setting('skill:'+a['name'],True): raise ValueError('This skill is disabled')
            return load_skill(a['name'])
        if '__' in name:
            group,tool=name.split('__',1)
            return await self.connectors[group].call(tool,a)
        if name=='list_files':
            p=workspace_path(a.get('path','.'))
            return [{'name':f.name,'path':str(f.relative_to(Path(CONFIG['workspace']).resolve())),'directory':f.is_dir(),'bytes':f.stat().st_size if f.is_file() else 0} for f in sorted(p.iterdir(),key=lambda f:(not f.is_dir(),f.name.lower()))][:300]
        if name=='read_file':
            p=workspace_path(a['path'])
            if p.stat().st_size>8_000_000: raise ValueError('File is larger than 8 MB; use a targeted script')
            text=p.read_text('utf-8'); offset=max(0,a.get('offset',0)); limit=min(max(a.get('limit',16000),1),32000)
            return {'path':a['path'],'text':text[offset:offset+limit],'total_characters':len(text),'offset':offset}
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
            root=workspace_path(); result=[]; count=0
            for p in root.rglob('*'):
                count+=1
                if count>10000: break
                if any(v in p.parts for v in ['node_modules','.git','.venv','venv']): continue
                if not p.is_file() or p.stat().st_size>1_000_000 or not p.resolve().is_relative_to(root): continue
                try:
                    for n,line in enumerate(p.read_text('utf-8').splitlines(),1):
                        if a['query'].lower() in line.lower(): result.append({'path':str(p.relative_to(root)),'line':n,'text':line[:500]})
                        if len(result)>=80: return result
                except (UnicodeError,OSError): continue
            return result
        if name=='run_command': return await self.process(['powershell.exe','-NoProfile','-NonInteractive','-Command',a['command']],a.get('timeout',60))
        if name=='run_code':
            folder=workspace_path('.studio-scripts'); folder.mkdir(exist_ok=True)
            p=folder/(run['id']+'-'+str(__import__('time').time_ns())+('.py' if a['language']=='python' else '.js'))
            p.write_text(a['code'],encoding='utf-8')
            return await self.process([CONFIG['python'] if a['language']=='python' else CONFIG['node'],str(p)],a.get('timeout',60))
        if name in ['web_search','web_fetch']:
            # Use the configured execution runtime so packaged apps need no bundled research engine.
            script=Path(__file__).parent/'research.py'
            return await self.process([CONFIG['python'],str(script),'search' if name=='web_search' else 'fetch',a.get('query',a.get('url'))],45)
        if name=='discover_tools':
            cats=list(self.connectors) if a['category']=='all' else [a['category']]
            run['enabled'].update(cats)
            return [{'name':t['name'],'description':t['description'][:300],'approval':t['tier']} for t in self.catalog() if t['group'] in cats]
        if name=='memory_search':
            q=a['query'].lower()
            memories=[m for m in self.store.memory() if q in (m['title']+' '+m['content']).lower()]
            rows=self.store.rows('SELECT id,chat,payload FROM messages WHERE instr(lower(payload),?)>0 ORDER BY id DESC LIMIT 15',(q,))
            return {'memories':memories,'history':[dict(id=r['id'],chat=r['chat'],excerpt=json.loads(r['payload']).get('content','')[:1500]) for r in rows]}
        if name=='history_read':
            if a.get('message_id'):
                rows=self.store.rows('SELECT payload FROM messages WHERE id=?',(a['message_id'],)); return json.loads(rows[0]['payload']) if rows else {'error':'Not found'}
            if a.get('action_id'):
                id=a['action_id']
                if not re.fullmatch('[a-f0-9]{32}',id): raise ValueError('Invalid action ID')
                p=DATA/'tool-outputs'/(id+'.json'); return json.loads(p.read_text('utf-8')) if p.exists() else {'error':'Not found'}
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
