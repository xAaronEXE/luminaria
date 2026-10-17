import json,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from tests.work_events import Harness,stream,tool_call
from backend import engine as engine_module
from backend.checkpoint import report
from backend.config import CONFIG

def text(content):return stream([{'choices':[{'delta':{'content':content}}]}])

class CheckpointTests(unittest.IsolatedAsyncioTestCase):
 async def test_round_limit_writes_a_readable_checkpoint_without_another_model_call(self):
  h=Harness([stream([tool_call(0,f'c{i}','read_file',{'path':'a.txt'})]) for i in range(3)])
  try:
   with patch.object(engine_module,'ROUND_LIMIT',3):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Look into a.txt'})
    h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat]
   self.assertEqual(run['phase'],'Checkpoint');self.assertEqual(run['checkpoint']['reason'],'limit');self.assertEqual(h.responses,[])
   last=h.store.messages(chat)[-1]
   self.assertTrue(last['checkpoint']);self.assertIn('Completed (3)',last['content']);self.assertIn('read_file `a.txt`',last['content'])
   self.assertIn('Changes made:** none',last['content']);self.assertIn('Continue task',last['content'])
   self.assertEqual([e for e in h.work() if e['type']=='run.completed'][-1]['status'],'checkpoint')
  finally:h.close()

 async def test_repeated_failures_stop_early(self):
  h=Harness([stream([tool_call(0,f'c{i}','read_file',{'path':'missing.txt'})]) for i in range(3)])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'read it'})
   h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat];self.assertEqual(run['checkpoint']['reason'],'repeated')
   content=h.store.messages(chat)[-1]['content']
   self.assertIn('failed 3 times',content);self.assertIn('Failed (3)',content);self.assertIn('No useful results',content)
  finally:h.close()

 async def test_continuation_does_not_repeat_a_completed_write(self):
  write={'path':'b.txt','content':'hello'}
  h=Harness([stream([tool_call(0,'w1','write_file',write)]),stream([tool_call(0,'l1','list_files',{'path':'.'})]),
   stream([tool_call(0,'w2','write_file',write)]),text('Done.')])
  try:
   h.store.set_setting('permission:write_file',True)
   with patch.object(engine_module,'ROUND_LIMIT',2):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'write b'})
    h.engine.start(chat);await h.engine.tasks[chat]
    first=h.engine.public_run(chat);self.assertEqual(first['phase'],'Checkpoint')
    target=Path(CONFIG['workspace'])/'b.txt';self.assertTrue(target.exists());target.unlink()
    h.store.add(chat,{'role':'user','content':'continue'})
    h.engine.start(chat,continue_from=first);await h.engine.tasks[chat]
   self.assertFalse(target.exists())
   writes=[a for a in h.store.actions(chat) if a['name']=='write_file']
   self.assertEqual(len(writes),2);self.assertIn('already succeeded',writes[1]['result']['text'])
   run=h.engine.runs[chat];self.assertEqual(run['phase'],'Complete');self.assertEqual(run['continuations'],1);self.assertEqual(run['continuing'],first['started'])
  finally:h.close()

 async def test_failed_final_generation_still_reports_progress(self):
  h=Harness([stream([tool_call(0,'c1','read_file',{'path':'a.txt'})]),httpx.Response(500,text='boom')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'read'})
   h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat];self.assertEqual(run['phase'],'Error');self.assertEqual(run['checkpoint']['reason'],'error')
   content=h.store.messages(chat)[-1]['content']
   self.assertIn('Task stopped',content);self.assertIn('Completed (1)',content)
  finally:h.close()

class ReportTests(unittest.TestCase):
 def test_command_and_integration_effects_are_not_reported_as_no_changes(self):
  for name,args in [('run_command',{'command':'create an output'}),('run_code',{'language':'python'}),('github__create_issue',{'title':'Example'}),('remember',{'title':'Preference'})]:
   with self.subTest(name=name):
    out=report([{'name':name,'args':args,'status':'done','result':{'text':'ok'}}])
    self.assertIn('Other actions that may have changed state',out)
    self.assertIn('not fully established',out)
    self.assertNotIn('No files were written',out)
    self.assertIn('does not independently verify',out)

 def test_uncertain_mutations_require_inspection_even_after_error(self):
  for status in ('interrupted','running','error'):
   with self.subTest(status=status):
    out=report([{'name':'write_file','args':{'path':'x.txt'},'status':status,'result':None}])
    self.assertIn('Uncertain outcomes',out)
    self.assertIn('ask the user before retrying',out)
    self.assertNotIn('Changes made:** none',out)
    self.assertNotIn('will not be repeated',out)

 def test_continuation_skip_is_not_a_new_write(self):
  for result in ({'already_done':'original-id','skipped':True},{'text':json.dumps({'already_done':'original-id','skipped':True})}):
   out=report([{'name':'write_file','args':{'path':'x.txt'},'status':'done','result':result}])
   self.assertIn('Previously completed actions skipped (1)',out)
   self.assertNotIn('file tools reported',out)
   self.assertNotIn('No useful results',out)

 def test_report_lists_changes_failures_denials_and_remaining_plan(self):
  actions=[{'name':'edit_file','args':{'path':'x.py'},'status':'done','result':{'text':'{"ok": true}'}},
   {'name':'web_fetch','args':{'url':'https://a.example'},'status':'error','result':{'text':'{"error": "Timed out after 20 s"}'}},
   {'name':'run_command','args':{'command':'rm'},'status':'denied','result':None}]
  plan={'steps':[{'title':'Edit','status':'done'},{'title':'Test it','status':'pending'},{'title':'Ship','status':'blocked'}]}
  out=report(actions,plan)
  self.assertIn('edit `x.py`',out);self.assertIn('Timed out after 20 s',out);self.assertIn('Declined by you:** run_command',out)
  self.assertIn('- Test it',out);self.assertIn('- Ship (blocked)',out);self.assertNotIn('- Edit',out)

if __name__=='__main__':unittest.main()
