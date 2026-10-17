import asyncio,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name

import httpx
from langgraph.checkpoint.memory import MemorySaver
from backend import engine as engine_module
from backend.config import CONFIG
from backend.engine import Engine
from backend.store import Store
from backend.tools import Toolbox
from backend.work import WorkLog,plan_steps,region_for

def stream(chunks):
 body=''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n'
 return httpx.Response(200,content=body.encode(),headers={'content-type':'text/event-stream'})

def tool_call(index,id,name,args):
 return {'choices':[{'delta':{'tool_calls':[{'index':index,'id':id,'function':{'name':name,'arguments':json.dumps(args)}}]}}]}

PLAN={'steps':[{'id':'look','title':'Look at the files','status':'active'},{'id':'answer','title':'Answer','status':'pending','depends_on':['look']}]}

class Harness:
 def __init__(self,responses):
  root=Path(tempfile.mkdtemp(dir=FOLDER.name));(root/'Files').mkdir();(root/'Files'/'a.txt').write_text('x')
  self.store=Store(root/'studio.sqlite3');self.events=[];self.responses=list(responses)
  self.patches=[patch.dict(CONFIG,{'workspace':str(root/'Files')}),patch.object(engine_module,'DATA',root)]
  for p in self.patches:p.start()
  self.engine=Engine(self.store,Toolbox(self.store,{}),self.events.append,MemorySaver())
  async def handler(request):return self.responses.pop(0)
  self.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
  async def count(messages,definitions=None):return 100,'test'
  self.engine.token_count=count
 def close(self):
  for p in self.patches:p.stop()
 def work(self):return [e['event'] for e in self.events if e['type']=='work']

class WorkEventTests(unittest.IsolatedAsyncioTestCase):
 async def test_run_records_plan_tools_and_generation_as_ordered_evidence(self):
  h=Harness([stream([tool_call(0,'c1','update_plan',PLAN),tool_call(1,'c2','list_files',{'path':'.'})]),stream([{'choices':[{'delta':{'content':'Done.'}}]}])])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Look around'})
   run=h.engine.start(chat);await h.engine.tasks[chat]
   types=[e['type'] for e in h.work()]
   self.assertEqual(types[0],'run.started');self.assertEqual(types[-1],'run.completed')
   for kind in ('generation.started','generation.completed','tool.requested','tool.started','tool.completed','plan.created'):self.assertIn(kind,types)
   self.assertLess(types.index('plan.created'),types.index('generation.completed',types.index('plan.created')))
   seqs=[e['seq'] for e in h.work()];self.assertEqual(seqs,sorted(seqs));self.assertEqual(len(set(seqs)),len(seqs))
   plan=next(e for e in h.work() if e['type']=='plan.created')
   self.assertEqual(plan['source'],'model-provided');self.assertEqual(plan['steps'][1]['depends_on'],['look'])
   listing=next(e for e in h.work() if e['type']=='tool.completed' and e['tool']=='list_files')
   self.assertEqual(listing['region'],'files');self.assertEqual(listing['step'],'look');self.assertEqual(listing['parent'],'gen0')
   self.assertEqual(set(listing['evidence']),{'action'});self.assertNotIn('args',listing);self.assertNotIn('a.txt',json.dumps(h.work()))
   persisted=h.engine.worklog.events(chat)
   self.assertEqual([e['id'] for e in persisted],[e['id'] for e in h.work()])
   self.assertTrue(all(e['run']==run for e in persisted))
  finally:h.close()

 async def test_failures_and_cancellation_are_recorded(self):
  h=Harness([stream([tool_call(0,'c1','read_file',{'path':'missing.txt'})]),stream([tool_call(0,'c2','read_file',{'path':'a.txt'})]),stream([{'choices':[{'delta':{'content':'ok'}}]}])])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'read'})
   h.engine.start(chat);await h.engine.tasks[chat]
   failed=next(e for e in h.work() if e['type']=='tool.failed')
   second=[e for e in h.work() if e['type']=='tool.requested'][1]
   self.assertEqual(second['follows_failure'],failed['node'])
   h.events.clear()
   async def hang(request):await asyncio.sleep(30)
   h.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(hang))
   h.store.add(chat,{'role':'user','content':'again'})
   h.engine.start(chat);await asyncio.sleep(.2);h.engine.tasks[chat].cancel()
   await h.engine.tasks[chat]
  finally:h.close()
  self.assertEqual(h.work()[-1]['type'],'run.cancelled')

 async def test_approval_replay_does_not_duplicate_events(self):
  h=Harness([stream([tool_call(0,'c1','write_file',{'path':'b.txt','content':'y'})]),stream([{'choices':[{'delta':{'content':'ok'}}]}])])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'write'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.work()[-1]['type'],'approval.requested')
   h.engine.resume(chat,{'approved':True});await h.engine.tasks[chat]
   types=[e['type'] for e in h.work()]
   for kind in ('tool.requested','approval.requested','approval.allowed','tool.completed'):self.assertEqual(types.count(kind),1,kind)
   self.assertIn('run.resumed',types);self.assertEqual(types[-1],'run.completed')
  finally:h.close()

 def test_replayed_events_are_ignored_and_runs_are_bounded(self):
  folder=tempfile.mkdtemp(dir=FOLDER.name);store=Store(Path(folder)/'s.sqlite3');seen=[]
  log=WorkLog(store,seen.append);run={'id':'r1','chat':'c1'}
  self.assertIsNotNone(log.record(run,'tool.requested','a1',node='a1'))
  self.assertIsNone(log.record(run,'tool.requested','a1',node='a1'))
  self.assertEqual(len(seen),1);self.assertEqual(len(log.events('c1')),1)
  for i in range(5):log.record({'id':f'x{i}','chat':'c1'},'run.started')
  self.assertEqual(len({e['run'] for e in log.events('c1',runs=3)}),3)
  with self.assertRaises(ValueError):log.record(run,'made.up')

 def test_plan_validation_and_regions(self):
  self.assertEqual(plan_steps(PLAN)[0]['status'],'active')
  for bad in ({'steps':[]},{'steps':[{'id':'a','title':'','status':'pending'}]},{'steps':[{'id':'a','title':'x','status':'pending','depends_on':['b']}]},{'steps':[{'id':'a','title':'x','status':'thinking'}]}):
   with self.assertRaises(ValueError):plan_steps(bad)
  self.assertEqual(region_for('web_fetch'),'retrieval');self.assertEqual(region_for('memory_search'),'memory');self.assertEqual(region_for('run_code'),'verification');self.assertEqual(region_for('browser__click'),'tools')

if __name__=='__main__':unittest.main()
