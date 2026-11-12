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
 async def test_direct_request_cannot_finish_with_no_actions(self):
  h=Harness([text('Done. I fixed it.'),text('Done.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Fix the bug in app.py.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat]
   self.assertEqual(run['phase'],'Stopped')
   self.assertEqual(run['verification']['outcome'],'not_run')
   self.assertEqual(h.store.actions(chat),[])
   self.assertEqual(h.responses,[])
   self.assertTrue(h.store.messages(chat)[-1]['content'].startswith('Work is not verified.'))
  finally:h.close()

 async def test_promised_file_search_retries_and_checks_the_tool_journal(self):
  h=Harness([text("First I'll locate the relevant files. Let's proceed by searching for them."),
   stream([tool_call(0,'list','list_files',{'path':'.'})]),text('The workspace contains a.txt.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Look through the workspace files.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.engine.runs[chat]['phase'],'Complete')
   self.assertEqual(h.engine.runs[chat]['verification']['outcome'],'passed')
   self.assertEqual([(a['name'],a['status']) for a in h.store.actions(chat)],[('list_files','done')])
  finally:h.close()

 async def test_genuine_refusal_stays_visible_without_a_retry(self):
  h=Harness([text("I can't make that change without the source file.")])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Fix the bug in app.py.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.engine.runs[chat]['phase'],'Stopped')
   self.assertTrue(h.store.messages(chat)[-1]['content'].startswith("I can't"))
   self.assertFalse(h.engine.runs[chat].get('verification_retry'))
  finally:h.close()

 async def test_model_recovery_retries_generation_before_executing_tools(self):
  h=Harness([httpx.Response(503),httpx.Response(503),text('Recovered.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'hello'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.store.messages(chat)[-1]['content'],'Recovered.')
   self.assertEqual(h.store.actions(chat),[])
   labels=[event['label'] for event in h.work() if event['type']=='model.recovery']
   self.assertEqual(labels,['Retrying the model','Retrying with a shorter context'])
  finally:h.close()

 async def test_direct_work_passes_only_with_a_recorded_check(self):
  check={'type':'file_contains','path':'verified.txt','text':'expected'}
  write={'path':'verified.txt','content':'expected'}
  h=Harness([stream([tool_call(0,'check','set_work_check',{'check':check})]),
   stream([tool_call(0,'write','write_file',write)]),text('The file is ready.')])
  try:
   h.store.set_setting('permission:write_file',True)
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Create verified.txt with expected as its content.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat]
   self.assertEqual(run['phase'],'Complete')
   self.assertEqual(run['verification']['outcome'],'passed')
  finally:h.close()

 async def test_research_retries_when_retrieved_text_does_not_support_a_claim(self):
  url='https://example.com/source'
  answer='The launch was in 1999. [Source]('+url+')'
  corrected='The launch was in 2000. [Source]('+url+')'
  h=Harness([stream([tool_call(0,'r1','research',{'question':'When was the launch?'})]),
   text(answer),text('UNSUPPORTED'),text(corrected),text('SUPPORTED')])
  try:
   h.store.set_setting('permission:research',True)
   original=h.engine.tools.dispatch
   async def dispatch(name,args,run):
    if name=='research':
     return {'status':'ok','sources':[{'url':url,'excerpt':'The launch was in 2000.'}]}
    return await original(name,args,run)
   with patch.object(h.engine.tools,'dispatch',dispatch):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Research when the launch occurred.'})
    h.engine.start(chat);await h.engine.tasks[chat]
   messages=h.store.messages(chat)
   self.assertFalse(any(m.get('content')==answer for m in messages))
   self.assertEqual(messages[-1]['content'],corrected)
   self.assertEqual(h.engine.runs[chat]['verification']['outcome'],'passed')
  finally:h.close()

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
   stream([tool_call(0,'w2','write_file',write)]),text('Done.'),text('Done.')])
  try:
   h.store.set_setting('permission:write_file',True)
   with patch.object(engine_module,'ROUND_LIMIT',2):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'write b'})
    h.engine.start(chat);await h.engine.tasks[chat]
    first=h.engine.public_run(chat);self.assertEqual(first['phase'],'Checkpoint')
    target=Path(CONFIG['workspace'])/'b.txt';self.assertTrue(target.exists());target.unlink()
    h.store.add(chat,{'role':'user','content':'continue'})
    with patch.object(engine_module,'ROUND_LIMIT',4):
     h.engine.start(chat,continue_from=first);await h.engine.tasks[chat]
   self.assertFalse(target.exists())
   writes=[a for a in h.store.actions(chat) if a['name']=='write_file']
   self.assertEqual(len(writes),2);self.assertIn('already succeeded',writes[1]['result']['text'])
   run=h.engine.runs[chat];self.assertEqual(run['phase'],'Stopped');self.assertEqual(run['verification']['outcome'],'not_run')
   self.assertEqual(run['continuations'],1);self.assertEqual(run['continuing'],first['started'])
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
