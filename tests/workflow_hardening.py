import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests.work_events import Harness,stream,tool_call
from backend import engine as engine_module,retrieval
from backend.sources import document,matches
from backend import skills
import httpx

class SourceTests(unittest.TestCase):
 def test_revision_changes_but_source_identity_survives_edits(self):
  old=document('old\nexact path', 'file:a');new=document('new\nexact path','file:a')
  self.assertEqual(old['source_id'],new['source_id']);self.assertNotEqual(old['revision'],new['revision'])
  self.assertEqual(document('old\nexact path','file:a')['references'],old['references'])
 def test_late_history_match_gets_its_original_context(self):
  text='prefix '*1000+'the exact needle here'
  result=matches(text,'message:7','needle')[0]
  self.assertIn('needle',result['context']);self.assertGreater(result['reference']['start'],0)
  self.assertEqual(result['representation'],'verbatim')
 def test_blank_queries_are_rejected(self):
  with self.assertRaises(ValueError):matches('anything','a',' ')
 def test_saved_json_can_be_retrieved_in_bounded_original_passages(self):
  from backend.sources import saved_object
  raw=json.dumps({'text':'prefix '*5000+'exact original reference'})
  first=saved_object(raw,'action:1','output',0,1000);later=saved_object(raw,'action:1','output',len(raw)-100,100)
  self.assertNotIn('output',first);self.assertTrue(first['truncated'])
  self.assertIn('exact original reference',later['text']);self.assertEqual(first['revision'],later['revision'])

class ContinuationTests(unittest.IsolatedAsyncioTestCase):
 async def test_reordered_arguments_do_not_repeat_a_successful_write(self):
  h=Harness([stream([tool_call(0,'a','write_file',{'path':'b.txt','content':'first'})]),stream([tool_call(0,'b','write_file',{'content':'first','path':'b.txt'})]),stream([{'choices':[{'delta':{'content':'Done'}}]}])])
  try:
   h.store.set_setting('permission:write_file',True)
   with patch.object(engine_module,'ROUND_LIMIT',1):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'write'})
    h.engine.start(chat);await h.engine.tasks[chat];previous=h.engine.public_run(chat)
   target=Path(engine_module.CONFIG['workspace'])/'b.txt';target.write_text('manual change')
   h.store.add(chat,{'role':'user','content':'continue'});h.engine.start(chat,continue_from=previous);await h.engine.tasks[chat]
   self.assertEqual(target.read_text(),'manual change')
   self.assertIn('already succeeded',h.store.actions(chat)[-1]['result']['text'])
  finally:await h.engine.client.aclose();h.close()
 async def test_failed_write_cannot_be_replayed_on_continue(self):
  h=Harness([stream([tool_call(0,'a','edit_file',{'path':'a.txt','old_text':'absent','new_text':'new'})]),stream([tool_call(0,'b','edit_file',{'new_text':'new','old_text':'absent','path':'a.txt'})])])
  try:
   h.store.set_setting('permission:edit_file',True)
   with patch.object(engine_module,'ROUND_LIMIT',1):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'edit'})
    h.engine.start(chat);await h.engine.tasks[chat];previous=h.engine.public_run(chat)
   h.store.add(chat,{'role':'user','content':'continue'});h.engine.start(chat,continue_from=previous);await h.engine.tasks[chat]
   self.assertEqual(h.engine.public_run(chat)['phase'],'Denied')
   self.assertIn('uncertain outcome',h.store.actions(chat)[-1]['result']['text'])
  finally:await h.engine.client.aclose();h.close()
 async def test_skill_preflight_blocks_missing_connector(self):
  h=Harness([])
  try:
   with patch.object(skills,'external_tools_enabled',lambda:True):
    result=await h.engine.tools.call('load_skill',{'name':'playwright'},{'chat':'test'})
   self.assertEqual(result['status'],'error');self.assertEqual(result['state'],'Needs setup')
   self.assertNotIn('instructions',result)
  finally:await h.engine.client.aclose();h.close()

class CacheTests(unittest.IsolatedAsyncioTestCase):
 async def test_redirect_cookie_is_not_cached_as_a_public_page(self):
  original=httpx.AsyncClient;hits=[]
  def handler(request):
   hits.append(str(request.url))
   if request.url.path=='/start':return httpx.Response(302,headers={'location':'/article','set-cookie':'session=fixture; Path=/'})
   return httpx.Response(200,text='Account-dependent extracted page content. '*8,headers={'content-type':'text/plain'})
  def client(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
  retrieval._cache.clear()
  with patch.object(retrieval.httpx,'AsyncClient',client):
   await retrieval.fetch('https://site.test/start');await retrieval.fetch('https://site.test/start')
  self.assertEqual(len(hits),4);self.assertEqual(retrieval._cache,{})
 async def test_public_default_client_caches_and_refreshes_but_sensitive_responses_do_not(self):
  original=httpx.AsyncClient;hits=[]
  def handler(request):
   hits.append(str(request.url));return httpx.Response(200,text='A long public article about measured hardware performance. '*8,headers={'content-type':'text/plain',**({'cache-control':'private'} if request.url.path=='/private' else {})})
  def client(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
  retrieval._cache.clear()
  with patch.object(retrieval.httpx,'AsyncClient',client):
   a=await retrieval.fetch('https://site.test/public');b=await retrieval.fetch('https://site.test/public')
   self.assertTrue(b['cached']);self.assertEqual(a['retrieved_at'],b['retrieved_at'])
   await retrieval.fetch('https://site.test/public',refresh=True)
   for path in ('/private','/signed?token=secret'):
    await retrieval.fetch('https://site.test'+path);await retrieval.fetch('https://site.test'+path)
  self.assertEqual(len(hits),6)
  self.assertNotIn('https://site.test/private',retrieval._cache)
  self.assertNotIn('https://site.test/signed?token=secret',retrieval._cache)

class BrowserTests(unittest.IsolatedAsyncioTestCase):
 async def test_fallback_checks_both_tools_before_navigation(self):
  from backend.browser_retrieval import fetch
  class Browser:
   status='connected';tools=[{'name':'browser_navigate','inputSchema':{'type':'object'}}]
   async def call(self,*args):raise AssertionError('must not navigate without snapshot capability')
  self.assertEqual((await fetch(Browser(),'https://example.test'))['category'],'unsupported')
 async def test_browser_content_is_untrusted_and_uncached(self):
  from backend.browser_retrieval import fetch
  class Browser:
   status='connected';tools=[{'name':n,'inputSchema':{'type':'object'}} for n in ('browser_navigate','browser_snapshot')]
   async def call(self,name,args):return {'content':[{'type':'text','text':'Observed page content'}]}
  out=await fetch(Browser(),'https://example.test')
  self.assertEqual(out['status'],'ok');self.assertFalse(out['cached']);self.assertIn('untrusted',out['trust'])

class SkillWorkflowTests(unittest.IsolatedAsyncioTestCase):
 async def test_evidence_output_and_readback_required_for_completion(self):
  h=Harness([])
  try:
   chat=h.store.create_chat();run={'id':'skill-test','chat':chat,'started':0}
   result=await h.engine.tools.call('load_skill',{'name':'research'},run)
   self.assertEqual(result['state'],'Running')
   (Path(engine_module.CONFIG['workspace'])/'report.md').write_text('Verified source findings')
   h.store.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',('evidence',chat,'read_file',json.dumps({'path':'a.txt'}),'auto','done','{}',1))
   result=await h.engine.tools.call('finish_skill',{'name':'research','outputs':['report.md'],'evidence_actions':['evidence']},run)
   self.assertEqual(result['state'],'Completed');self.assertEqual(len(result['outputs'][0]['sha256']),64)
   from backend.skill_runs import complete,set_state
   set_state(h.store,'research','Running','test',run)
   with self.assertRaises(ValueError):complete(h.store,'research',['missing.md'],['evidence'],run)
   with self.assertRaises(ValueError):complete(h.store,'research',['report.md'],['invented-action'],run)
  finally:await h.engine.client.aclose();h.close()
