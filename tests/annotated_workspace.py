import json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import httpx
ISOLATED=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ['STUDIO_DATA']=ISOLATED.name
from backend import preferences,models
from backend.compaction import summarize
from backend.orchestration import choose

class PersistenceTests(unittest.TestCase):
 def test_shared_accent_survives_reopen_and_profile_change(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(preferences,'shared_appearance_path',return_value=Path(folder)/'appearance.json'):
   value={'mode':'dark','accent':'#E04040','modes':{'light':{},'dark':{}}}
   preferences.save_shared_appearance(value)
   self.assertEqual(preferences.load_shared_appearance()['accent'],'#E04040')
   self.assertEqual(preferences.load_shared_appearance()['mode'],'dark')
   self.assertFalse((Path(folder)/'appearance.tmp').exists())
 def test_context_is_saved_per_model_and_rejects_unknown_limits(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);weight=root/'model.gguf';weight.write_bytes(b'fixture')
   path=root/'models.json';path.write_text(json.dumps([{'id':'small','model_file':str(weight),'context':4096,'context_supported':16384}]))
   with patch.object(models,'PATH',path),patch.dict(models.CONFIG,{'model':'other'}):
    models.set_context('small',8192);self.assertEqual(models.registry()[0]['context'],8192)
    for bad in [True,'8192',0,32768]:
     with self.assertRaises(ValueError):models.set_context('small',bad)

class RoutingTests(unittest.IsolatedAsyncioTestCase):
 async def test_completed_model_metrics_survive_engine_restart(self):
  from tests.work_events import Harness
  h=Harness([])
  try:
   chat=h.store.create_chat()
   h.store.save_run({'id':'finished','chat':chat,'phase':'Complete','finished':123,
                     'model_id':'specialist','enabled':set(),
                     'metrics':{'tokens_per_second':42.5}})
   restored=h.engine.public_run(chat)
   self.assertEqual(restored['model_id'],'specialist')
   self.assertEqual(restored['metrics']['tokens_per_second'],42.5)
   self.assertNotIn('enabled',restored)
  finally:
   await h.engine.client.aclose();h.close()
 async def test_compacted_plan_uses_one_initial_system_message(self):
  from tests.work_events import Harness
  h=Harness([])
  try:
   chat=h.store.create_chat();message=h.store.add(chat,{'role':'user','content':'Do not send anything'})
   h.store.save_summary(chat,message,'Goal: draft a plan. Constraints: do not send anything.')
   context=h.engine.context(chat,{'plan_only':True})
   self.assertEqual(sum(m['role']=='system' for m in context),1)
   self.assertIn('Planning-only mode is on',context[0]['content'])
   self.assertIn('Constraints: do not send anything.',context[0]['content'])
  finally:
   await h.engine.client.aclose();h.close()
 async def test_specialist_keeps_context_and_emits_routing_evidence(self):
  from tests.work_events import Harness,stream
  from backend.config import CONFIG
  from unittest.mock import AsyncMock
  h=Harness([])
  weight=h.store.data_directory/'model.gguf';weight.write_bytes(b'fixture')
  registry=[{'id':'router','model_file':str(weight),'context':8192},
            {'id':'specialist','model_file':str(weight),'context':16384}]
  requests=[]
  async def transport(request):
   body=json.loads(request.content);requests.append(body)
   if not body.get('stream'):return httpx.Response(200,json={'choices':[{'message':{'content':'Ready'}}]})
   return stream([{'choices':[{'delta':{'content':'Specialist result'}}]}])
  await h.engine.client.aclose()
  h.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
  try:
   with patch.dict(CONFIG,{'orchestrator_model':'router'}),patch.object(models,'registry',return_value=registry),patch('backend.orchestration.choose',new=AsyncMock(return_value={'model_id':'specialist','reason':'Coding'})):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Write code'})
    h.engine.start(chat);await h.engine.tasks[chat]
    self.assertEqual(h.engine.runs[chat]['context']['limit'],16384)
    self.assertTrue(all(r['model']=='specialist' for r in requests))
    self.assertIn('routing.completed',[e['type'] for e in h.work()])
    self.assertIsNone(h.engine.inference.get())
  finally:
   await h.engine.client.aclose();h.close()
 async def test_router_can_only_select_installed_registry_ids(self):
  with tempfile.TemporaryDirectory() as folder:
   weight=Path(folder)/'model.gguf';weight.write_bytes(b'fixture')
   registry=[{'id':'small','model_file':str(weight)},{'id':'code','model_file':str(weight)}]
   async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'{"model_id":"code","reason":"coding task"}'}}]}))) as client:
    result=await choose(client,'http://local/v1','small',registry,'write code','code')
    self.assertEqual(result['model_id'],'code')
   async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'{"model_id":"download-something","needs":["coding"],"complexity":"high"}'}}]}))) as client:
    result=await choose(client,'http://local/v1','small',registry,'task','code')
    self.assertIn(result['model_id'],{'small','code'})
   # A missing routing model is not an error: the choice falls back to keywords, still among installed models.
   result=await choose(None,'http://local/v1','missing',registry,'task','code')
   self.assertIn(result['model_id'],{'small','code'})
 async def test_truncated_compaction_is_retried_without_accepting_partial_result(self):
  calls=[]
  async def count(messages):return 200,'fixture'
  async def complete(messages,max_tokens):
   calls.append(messages)
   if len(calls)==1:return {'content':'Incomplete summary with enough characters to pass length validation.','finish_reason':'length'}
   return {'content':'Goal: finish project. Constraints: no sending. Open work: verify results.'}
  result=await summarize([{'message_id':12,'content':'Important instructions'}],'',4096,count,complete)
  self.assertEqual(len(calls),2);self.assertIn('Source messages: 12 through 12',result)

if __name__=='__main__':unittest.main()
