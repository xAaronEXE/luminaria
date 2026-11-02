"""Deterministic file-first observe/act/verify/recover workflows, with no shell or UI control."""
import asyncio,hashlib,json,os,threading
from pathlib import Path
from .config import CONFIG,full_access
from .sources import document
from .store import uid,now

LIMIT=2_000_000

def digest(data):return hashlib.sha256(data).hexdigest()

def observe(path):
    if not path.exists():return {'exists':False,'sha256':None}
    if not path.is_file() or path.stat().st_size>LIMIT:raise ValueError('Only individual files up to 2 MB are supported by file workflows.')
    data=path.read_bytes();return {'exists':True,'sha256':digest(data),'bytes':len(data)}

def target(plan,step):
    root=Path(plan['root']).resolve();path=(root/step['path']).resolve()
    if str(Path(CONFIG['workspace']).resolve())!=str(root):raise ValueError('Default folder changed. Restore it or create a new workflow.')
    allowed=[(root/p).resolve() for p in plan['allowed_locations']]
    if not path.is_relative_to(root) or not any(path.is_relative_to(p) and p.is_relative_to(root) for p in allowed):raise ValueError('Target is outside the explicitly allowed locations.')
    if step.get('resolved') and str(path)!=step['resolved']:raise ValueError('The target location changed since planning; review symlinks and create a fresh plan.')
    return path

def get(store,id):
    if not isinstance(id,str) or len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise ValueError('Invalid workflow ID.')
    plan=store.setting('file_workflow:'+id,None)
    if plan is None:raise ValueError('File workflow not found.')
    return plan

def persist(store,plan):
    plan['updated']=now();store.set_setting('file_workflow:'+plan['id'],plan)

def create(store,body):
    if not isinstance(body,dict):raise ValueError('A workflow must be an object with objective, allowed locations, criteria and steps.')
    objective=body.get('objective');criteria=body.get('completion_criteria');allowed=body.get('allowed_locations');steps=body.get('steps')
    if not isinstance(objective,str) or not objective.strip() or len(objective)>1000:raise ValueError('Provide an objective of at most 1,000 characters.')
    if not isinstance(criteria,str) or not criteria.strip() or len(criteria)>2000:raise ValueError('Provide completion criteria of at most 2,000 characters.')
    if not isinstance(allowed,list) or not 1<=len(allowed)<=10 or any(not isinstance(p,str) or not p.strip() for p in allowed):raise ValueError('Declare one to ten allowed workspace locations.')
    if not isinstance(steps,list) or not 1<=len(steps)<=50:raise ValueError('Provide one to fifty file steps.')
    root=Path(CONFIG['workspace']).resolve()
    if any(Path(p).drive or Path(p).is_absolute() or not (root/p).resolve().is_relative_to(root) for p in allowed):raise ValueError('Allowed locations must be relative and stay inside the workspace.')
    plan={'id':uid(),'root':str(root),'objective':objective.strip(),'completion_criteria':criteria.strip(),
          'allowed_locations':allowed,'state':'Ready','created':now(),'steps':[],'final_expected':{}}
    predicted={}
    for raw in steps:
        if not isinstance(raw,dict) or raw.get('action') not in ('read','create','edit','trash') or not isinstance(raw.get('path'),str) or not raw['path'].strip():raise ValueError('Each step needs read/create/edit/trash and a relative file path.')
        step={'id':uid(),'action':raw['action'],'path':raw['path'],'state':'Ready'}
        for key in ('content','old_text','new_text'):
            if key in raw:
                if not isinstance(raw[key],str) or len(raw[key].encode('utf-8'))>LIMIT:raise ValueError('Text fields must be strings of at most 2 MB.')
                step[key]=raw[key]
        if Path(step['path']).drive or Path(step['path']).is_absolute():raise ValueError('Step paths must be relative to the workspace.')
        path=target(plan,step);step['resolved']=str(path)
        if str(path) not in predicted:predicted[str(path)]=path.read_bytes() if observe(path)['exists'] else None
        before=predicted[str(path)];step['before']={'exists':before is not None,'sha256':digest(before) if before is not None else None}
        if step['action']=='read':
            if before is None:raise ValueError('Read source does not exist at this step: '+step['path'])
        elif step['action']=='create':
            if before is not None:raise ValueError('Create never overwrites. Choose edit or a new path: '+step['path'])
            if 'content' not in step:raise ValueError('Create needs content.')
            predicted[str(path)]=step['content'].encode('utf-8')
        elif step['action']=='edit':
            if before is None or not step.get('old_text'):raise ValueError('Edit needs an existing source and non-empty old text.')
            text=before.decode('utf-8')
            if text.count(step['old_text'])!=1:raise ValueError('Edit old text must match exactly once.')
            if 'new_text' not in step:raise ValueError('Edit needs new text.')
            updated=text.replace(step['old_text'],step['new_text'],1).encode('utf-8')
            if len(updated)>LIMIT:raise ValueError('Edited output exceeds the 2 MB workflow limit.')
            predicted[str(path)]=updated
        else:
            if before is None:raise ValueError('Trash source does not exist at this step.')
            predicted[str(path)]=None
        after=predicted[str(path)];step['expected']={'exists':after is not None,'sha256':digest(after) if after is not None else None}
        if step['action']!='read':plan['final_expected'][step['path']]=step['expected']
        plan['steps'].append(step)
    if sum(len(str(s.get(k,''))) for s in plan['steps'] for k in ('content','old_text','new_text'))>4_000_000:raise ValueError('Workflow text exceeds 4 MB; split the task.')
    persist(store,plan);return plan

def same(a,b):return a['exists']==b['exists'] and a['sha256']==b['sha256']

class Workflows:
    def __init__(self,store):self.store=store;self.task=None;self.stop_event=threading.Event();self.active=None
    def busy(self):return self.task is not None and not self.task.done()
    def list(self):
        rows=self.store.rows("SELECT value FROM settings WHERE key LIKE 'file_workflow:%' ORDER BY rowid DESC LIMIT 50")
        return sorted([json.loads(r['value']) for r in rows],key=lambda p:p.get('updated',0),reverse=True)
    def recovery_file(self,plan,step):
        return self.store.data_directory/'workflow-recovery'/plan['id']/(step['id']+'.bin')
    def recover(self,plan):
        inspected=False
        for step in plan['steps']:
            if step['state']!='Running':continue
            inspected=True
            if step['action']=='read':
                step.update(state='Ready',reason='Read interrupted; retrieve a fresh observation before continuing.')
                continue
            path=target(plan,step);actual=observe(path)
            backup=self.recovery_file(plan,step)
            if same(actual,step['expected']) and (step['action']!='trash' or backup.is_file() and digest(backup.read_bytes())==step['before']['sha256']):
                step.update(state='Verified',observation=actual,recovered=True)
            elif same(actual,step['before']):step.update(state='Ready',reason='No completed effect detected. Explicitly run this step again after review.')
            else:step.update(state='Uncertain',reason='Target differs from both the planned source and expected output. Inspect it; no automatic replay is allowed.')
        if any(s['state']=='Uncertain' for s in plan['steps']):plan['state']='Needs review'
        elif inspected:plan['state']='Awaiting review' if all(s['state']=='Verified' for s in plan['steps']) else 'Stopped'
        elif plan['state']=='Running':plan['state']='Stopped'
        persist(self.store,plan);return plan
    def step(self,plan,step):
        path=target(plan,step);before=observe(path)
        if not same(before,step['before']):raise ValueError('Source changed after planning. Inspect it and create a fresh plan; this workflow will not overwrite it.')
        if self.stop_event.is_set():return False
        step['state']='Running';persist(self.store,plan)
        if step['action']=='read':step['result']=document(path.read_bytes().decode('utf-8'),'workspace:'+step['path'],limit=16000)
        else:
            if before['exists']:
                backup=self.recovery_file(plan,step);backup.parent.mkdir(parents=True,exist_ok=True)
                data=path.read_bytes()
                if digest(data)!=before['sha256']:raise ValueError('Source changed while preparing recovery copy.')
                if not backup.exists():
                    with backup.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
                if digest(backup.read_bytes())!=before['sha256']:raise ValueError('Recovery copy could not be verified.')
                step['recovery_available']=True
            if self.stop_event.is_set():step['state']='Ready';persist(self.store,plan);return False
            if not same(observe(path),before):raise ValueError('Source changed before the action; it was not modified.')
            if step['action']=='trash':path.unlink()
            else:
                content=step['content'] if step['action']=='create' else path.read_bytes().decode('utf-8').replace(step['old_text'],step['new_text'],1)
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_name('.luminaria-'+uid()+'.tmp')
                try:
                    with temporary.open('xb') as stream:stream.write(content.encode('utf-8'));stream.flush();os.fsync(stream.fileno())
                    if self.stop_event.is_set():step['state']='Ready';persist(self.store,plan);return False
                    if not same(observe(path),before):raise ValueError('Source changed before atomic replacement; no overwrite performed.')
                    if step['action']=='create':
                        # Hard-link publication fails if another writer created the destination.
                        os.link(temporary,path)
                    else:os.replace(temporary,path)
                finally:
                    if temporary.exists():temporary.unlink()
        actual=observe(path)
        if not same(actual,step['expected']):raise ValueError('Readback did not match the expected file state; inspect before continuing.')
        step.update(state='Verified',observation=actual,verified_at=now());persist(self.store,plan);return True
    def start(self,id,all_steps=False):
        if self.busy():raise ValueError('A file workflow is already active.')
        if all_steps and not full_access():raise ValueError('Review mode runs one approved step at a time. Switch to Hands-free in Settings › Permissions to run every step.')
        plan=self.recover(get(self.store,id))
        if plan['state'] in ('Completed','Needs review'):raise ValueError('Completed or uncertain workflows cannot be replayed. Inspect results or create a new plan.')
        if not any(s['state']=='Ready' for s in plan['steps']):raise ValueError('No ready steps remain. Review the results.')
        self.stop_event.clear();self.active=id;plan['state']='Running';persist(self.store,plan)
        self.task=asyncio.create_task(self.run(plan,all_steps));return plan
    async def run(self,plan,all_steps):
        try:
            for step in plan['steps']:
                if self.stop_event.is_set():break
                if step['state']=='Verified':continue
                if step['state']!='Ready':raise ValueError('A prior step requires inspection before this workflow can continue.')
                if not await asyncio.to_thread(self.step,plan,step):break
                if not all_steps:break
                await asyncio.sleep(0)
            plan['state']='Awaiting review' if all(s['state']=='Verified' for s in plan['steps']) else 'Stopped' if self.stop_event.is_set() else 'Ready'
        except Exception as error:plan.update(state='Needs review',error=str(error)[:400])
        finally:persist(self.store,plan);self.active=None
    def stop(self):
        self.stop_event.set()
        return {'state':'Stopping' if self.busy() else 'Stopped','message':'Stop requested; any current atomic file operation is settled and inspected before returning to Ready.'}
    async def close(self):
        self.stop()
        if self.task:await self.task
    def accept(self,id):
        if self.busy():raise ValueError('Stop or finish the active workflow first.')
        plan=get(self.store,id)
        if plan['state']!='Awaiting review':raise ValueError('Verify every step before accepting completion.')
        for relative,expected in plan['final_expected'].items():
            step=next(s for s in reversed(plan['steps']) if s['path']==relative)
            if not same(observe(target(plan,step)),expected):raise ValueError('A final output changed; review it before accepting.')
        plan.update(state='Completed',accepted_at=now());persist(self.store,plan);return plan
    def restore(self,id,step_id):
        if self.busy():raise ValueError('Stop the workflow before restoring a file.')
        plan=get(self.store,id);step=next((s for s in plan['steps'] if s['id']==step_id),None)
        if not step:raise ValueError('Step not found.')
        path=target(plan,step);backup=self.recovery_file(plan,step)
        if path.exists():raise ValueError('Restore never overwrites an existing file. Move or inspect that file first.')
        if not backup.is_file() or digest(backup.read_bytes())!=step['before']['sha256']:raise ValueError('No verified recovery copy is available.')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as output:output.write(backup.read_bytes());output.flush();os.fsync(output.fileno())
        step['restored_at']=now();plan['state']='Needs review';persist(self.store,plan)
        return {'status':'ok','path':step['path'],'observation':observe(path),'message':'Recovery copy restored. Create a fresh plan to continue after this change.'}
