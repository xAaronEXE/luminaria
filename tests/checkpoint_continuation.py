import json,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from tests.work_events import Harness,stream,tool_call
from backend import engine as engine_module
from backend.checkpoint import report, continuation_receipt
from backend.config import CONFIG

def text(content):return stream([{'choices':[{'delta':{'content':content}}]}])

class CheckpointTests(unittest.IsolatedAsyncioTestCase):
 async def test_restore_prefers_latest_run_and_requires_approval(self):
  from types import SimpleNamespace
  from unittest.mock import AsyncMock
  h=Harness([])
  try:
   chat=h.store.create_chat()
   for id,phase,updated in [('older','Waiting for approval',1),('newer','Complete',2)]:
    run={'id':id,'chat':chat,'phase':phase}
    h.store.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(id,chat,json.dumps(run),phase,updated))
   snapshot=SimpleNamespace(next=('tools',),tasks=[SimpleNamespace(interrupts=[
    SimpleNamespace(value={'action_id':'approval'})])])
   with patch.object(h.engine.graph,'aget_state',AsyncMock(return_value=snapshot)) as checkpoint:
    await h.engine.restore()
    checkpoint.assert_not_awaited()
    self.assertIsNone(h.engine.runs.get(chat))
    h.store.execute('DELETE FROM runs WHERE id=?',('newer',))
    await h.engine.restore()
   run=h.engine.public_run(chat)
   self.assertEqual(run['lifecycle']['state'],'awaiting_approval')
   self.assertFalse(run['resume_available'])
   with self.assertRaisesRegex(ValueError,'approval decision'):
    h.engine.resume(chat)
  finally:h.close()

 async def test_stop_finalizes_queued_task_once_without_rewriting_finished_state(self):
  from backend import app
  h=Harness([])
  try:
   chat=h.store.create_chat()
   h.engine.start(chat)
   with patch.object(app,'engine',h.engine),patch.object(app,'store',h.store),patch.object(app,'broadcast'):
    await app.stop_chat(chat)
    first=h.engine.public_run(chat)
    await app.stop_chat(chat)
   self.assertEqual(first['lifecycle'],{'state':'stopped','active':False,'actions':[]})
   self.assertEqual(h.engine.public_run(chat),first)
   self.assertEqual(sum(e['type']=='run.cancelled' for e in h.work()),1)
  finally:h.close()

 def test_continuation_limit_is_in_the_lifecycle_contract(self):
  from backend.run_state import lifecycle, MAX_CONTINUATIONS
  run={'phase':'Checkpoint','finished':1,'checkpoint':{'reason':'limit'}}
  self.assertEqual(lifecycle(run)['actions'],['continue'])
  self.assertEqual(lifecycle({**run,'continuations':MAX_CONTINUATIONS})['actions'],[])

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

 async def test_unoffered_tool_cannot_reach_dispatch(self):
  h=Harness([stream([tool_call(0,'extra','create_schedule',{'title':'Check','prompt':'Say hello','interval_minutes':300})]),text('The tool was unavailable.')])
  try:
   h.store.set_setting('permission:create_schedule',True)
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Help me organize my work.'})
   with patch.object(h.engine.tools,'dispatch',wraps=h.engine.tools.dispatch) as dispatch:
    h.engine.start(chat);await h.engine.tasks[chat]
    dispatch.assert_not_called()
   self.assertEqual(h.store.actions(chat)[0]['status'],'error')
  finally:h.close()

 async def test_incomplete_stream_does_not_dispatch_partial_calls(self):
  chunk=tool_call(0,'partial','list_files',{'path':'.'})
  response=httpx.Response(200,text='data: '+json.dumps(chunk)+'\n\n')
  h=Harness([response,text('Recovered after retry.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'What can you help me with?'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.store.actions(chat),[])
   self.assertEqual(h.store.messages(chat)[-1]['content'],'Recovered after retry.')
  finally:h.close()

 async def test_direct_file_check_requires_a_write_to_that_output(self):
  check={'type':'file_exists','path':'wrong.txt'}
  h=Harness([stream([tool_call(0,'check','set_work_check',{'check':check})]),
   stream([tool_call(0,'write','write_file',{'path':'wrong.txt','content':'other'})]),
   text('The file is ready.'),text('I cannot verify the requested file.')])
  try:
   h.store.set_setting('permission:write_file',True)
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Create expected.txt.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   run=h.engine.runs[chat]
   self.assertEqual(run['phase'],'Stopped')
   self.assertIn('requested file',run['verification']['detail'])
  finally:h.close()

 async def test_unknown_connector_write_requires_reconciliation(self):
  from types import SimpleNamespace
  from unittest.mock import AsyncMock
  from backend.connectors import OutcomeUnknown
  name='mail__send'
  h=Harness([stream([tool_call(0,'discover','discover_tools',{'category':'all'})]),
             stream([tool_call(0,'send',name,{})])])
  try:
   send=AsyncMock(side_effect=OutcomeUnknown('No confirmation was received.'))
   h.engine.tools.connectors['mail']=SimpleNamespace(tools=[{'name':'send','inputSchema':{'type':'object'}}],call=send)
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Send a test message.'})
   # Explicitly enter the ordinary work lane so the fixture tests dispatch and approval.
   h.store.add(chat,{'role':'user','content':'Please carry out the mail task.'})
   with patch.dict(CONFIG,external_tools=True):
    h.engine.start(chat);await h.engine.tasks[chat]
    self.assertEqual(h.store.actions(chat)[-1]['status'],'pending')
    h.engine.resume(chat,{'approved':True});await h.engine.tasks[chat]
   action=h.store.actions(chat)[-1]
   self.assertEqual(action['status'],'interrupted')
   self.assertTrue(h.engine.runs[chat]['checkpoint'])
   send.assert_awaited_once()
   h.store.reconcile_action(chat,action['id'],'applied')
   self.assertEqual(h.store.actions(chat)[-1]['status'],'done')
   first=h.engine.public_run(chat)
   h.store.add(chat,{'role':'user','content':'Continue.'})
   h.responses.extend([
    stream([tool_call(0,'discover-again','discover_tools',{'category':'all'})]),
    stream([tool_call(0,'send-again',name,{})]),
    text('Activity confirms that the action took effect.'),
   ])
   with patch.dict(CONFIG,external_tools=True), patch.object(h.engine,'completion',wraps=h.engine.completion) as completion:
    h.engine.start(chat,continue_from=first);await h.engine.tasks[chat]
   send.assert_awaited_once()
   self.assertIn('user confirmed it took effect',str(completion.await_args_list[0].args[0]))
   skipped=h.store.actions(chat)[-1]
   self.assertEqual(skipped['result']['already_done'],action['id'])
   self.assertEqual(h.engine.public_run(chat)['phase'],'Complete')
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
 def test_confirmed_no_effect_supersedes_an_earlier_error(self):
  earlier={'id':'1','status':'error'}
  reconciled={'id':'2','status':'retryable','result':{'reconciled':'no_effect'}}
  self.assertEqual(continuation_receipt([earlier,reconciled]),(None,None))
  self.assertEqual(continuation_receipt([{'id':'0','status':'done'},earlier,reconciled]),('done','0'))
  self.assertEqual(continuation_receipt([earlier,reconciled,{'id':'3','status':'interrupted'}]),
                   ('uncertain','3'))

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
