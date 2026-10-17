import json,unittest
from pathlib import Path
import httpx
from tests.work_events import Harness,stream,tool_call,PLAN
from backend.config import CONFIG

class PlanningModeTests(unittest.IsolatedAsyncioTestCase):
 def capture(self,h):
  bodies=[]
  async def handler(request):bodies.append(json.loads(request.content));return h.responses.pop(0)
  h.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
  return bodies

 async def test_plan_only_offers_read_only_tools_and_refuses_changes(self):
  h=Harness([stream([tool_call(0,'c1','read_file',{'path':'a.txt'}),tool_call(1,'c2','update_plan',PLAN)]),
   stream([tool_call(0,'c3','write_file',{'path':'b.txt','content':'y'})]),
   stream([{'choices':[{'delta':{'content':'Here is the plan.'}}]}])])
  bodies=self.capture(h)
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Plan the change'})
   h.engine.start(chat,plan_only=True);await h.engine.tasks[chat]
   offered={t['function']['name'] for t in bodies[0]['tools']}
   self.assertIn('update_plan',offered);self.assertIn('read_file',offered)
   for name in ('write_file','edit_file','delete_file','run_command','run_code','web_fetch','remember','create_schedule'):self.assertNotIn(name,offered)
   self.assertIn('Planning-only mode is on',bodies[0]['messages'][0]['content'])
   self.assertFalse(h.store.rows("SELECT id FROM actions WHERE name='write_file'"))
   refusal=[m for m in h.store.messages(chat) if m['role']=='tool' and m.get('tool_call_id')=='c3']
   self.assertEqual(len(refusal),1);self.assertIn('Planning-only mode',refusal[0]['content'])
   self.assertFalse((Path(CONFIG['workspace'])/'b.txt').exists())
   self.assertFalse(h.store.rows("SELECT id FROM actions WHERE status='pending'"))
   run=h.engine.runs[chat];self.assertTrue(run['plan_only']);self.assertEqual(run['phase'],'Complete');self.assertEqual(run['plan_version'],1)
   started=next(e for e in h.work() if e['type']=='run.started');self.assertEqual(started['label'],'Planning run')
  finally:h.close()

 async def test_normal_run_keeps_full_tools_and_no_plan_instruction(self):
  h=Harness([stream([{'choices':[{'delta':{'content':'ok'}}]}])])
  bodies=self.capture(h)
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'hi'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertIn('write_file',{t['function']['name'] for t in bodies[0]['tools']})
   self.assertNotIn('Planning-only',json.dumps(bodies[0]['messages']))
   self.assertFalse(h.engine.runs[chat]['plan_only'])
  finally:h.close()

 async def test_compaction_runs_ignore_plan_only(self):
  h=Harness([])
  try:
   chat=h.store.create_chat()
   h.engine.start(chat,compact_only=True,plan_only=True);await h.engine.tasks[chat]
   self.assertFalse(h.engine.runs[chat]['plan_only'])
  finally:h.close()

if __name__=='__main__':unittest.main()
