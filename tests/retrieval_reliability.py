import json,unittest
import httpx
from tests.work_events import Harness,stream,tool_call
from backend import retrieval

def text(content):return stream([{'choices':[{'delta':{'content':content}}]}])
def client(handler):return httpx.AsyncClient(transport=httpx.MockTransport(handler),follow_redirects=True)
async def nowait(seconds):pass

class ToolEnvelopeTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):self.h=Harness([]);self.run={'id':'r1','chat':'c1'}
 def tearDown(self):self.h.close();retrieval._cache.clear()
 async def call(self,name,args):return await self.h.engine.tools.call(name,args,self.run)
 def events(self):return self.h.store.rows('SELECT * FROM retrieval_events ORDER BY created')

 async def test_search_files_reports_matches_and_empty_distinctly(self):
  found=await self.call('search_files',{'query':'x'})
  self.assertEqual(found['status'],'ok');self.assertEqual(found['matches'][0]['path'],'a.txt');self.assertFalse(found['truncated'])
  missing=await self.call('search_files',{'query':'nothing-like-this'})
  self.assertEqual(missing['status'],'empty');self.assertIn('exact text',missing['message'])
  for key in ('duration_ms','retrieved_at','attempts','source'):self.assertIn(key,missing)

 async def test_memory_search_and_history_read_use_envelopes(self):
  empty=await self.call('memory_search',{'query':'zebra'});self.assertEqual(empty['status'],'empty')
  chat=self.h.store.create_chat();mid=self.h.store.add(chat,{'role':'user','content':'zebra notes'})
  hit=await self.call('memory_search',{'query':'zebra'});self.assertEqual(hit['status'],'ok');self.assertEqual(len(hit['history']),1)
  msg=await self.call('history_read',{'message_id':mid});self.assertEqual(msg['status'],'ok');self.assertEqual(msg['message']['content'],'zebra notes')
  gone=await self.call('history_read',{'message_id':999999});self.assertEqual((gone['status'],gone['category']),('error','not_found'))
  gone=await self.call('history_read',{'action_id':'a'*32});self.assertEqual(gone['category'],'not_found')

 async def test_web_search_categories(self):
  def none(q):return []
  def limited(q):raise RuntimeError('202 Ratelimit')
  def ok(q):return [{'title':'T','href':'https://example.com','body':'snippet'}]
  self.assertEqual((await retrieval.search('a',none))['status'],'empty')
  self.assertEqual((await retrieval.search('a',limited))['category'],'throttled')
  self.assertEqual((await retrieval.search('',ok))['category'],'invalid_input')
  result=await retrieval.search('a',ok);self.assertEqual(result['results'][0]['url'],'https://example.com')

 async def test_diagnostics_never_store_query_or_path(self):
  await self.call('memory_search',{'query':'secret-phrase'})
  await self.call('web_fetch',{'url':'http://localhost/private?token=abc'})
  rows=self.events();self.assertEqual([r['tool'] for r in rows],['memory_search','web_fetch'])
  self.assertEqual(rows[1]['category'],'invalid_input');self.assertEqual(rows[1]['source'],'localhost')
  dump=json.dumps(rows);self.assertNotIn('secret-phrase',dump);self.assertNotIn('token',dump);self.assertNotIn('private',dump)

 async def test_non_retrieval_tools_are_not_recorded(self):
  await self.call('list_files',{'path':'.'});self.assertEqual(self.events(),[])

class FetchErrorTests(unittest.IsolatedAsyncioTestCase):
 def tearDown(self):retrieval._cache.clear()
 async def test_status_codes_map_to_distinct_categories(self):
  for code,category in ((401,'auth'),(403,'blocked'),(404,'not_found'),(410,'not_found'),(451,'blocked')):
   result=await retrieval.fetch(f'https://e.test/{code}',client=client(lambda r,c=code:httpx.Response(c)),sleep=nowait)
   self.assertEqual((result['status'],result['category'],result['attempts']),('error',category,1),code);self.assertTrue(result['guidance'])

 async def test_server_errors_retry_then_succeed(self):
  calls=[]
  def handler(request):
   calls.append(1);return httpx.Response(503) if len(calls)<3 else httpx.Response(200,text='plain answer',headers={'content-type':'text/plain'})
  result=await retrieval.fetch('https://e.test/flaky',client=client(handler),sleep=nowait)
  self.assertEqual((result['status'],result['attempts'],result['text']),('ok',3,'plain answer'))

 async def test_throttling_honours_short_retry_after_and_gives_up_on_long(self):
  waits=[]
  async def sleep(s):waits.append(s)
  result=await retrieval.fetch('https://e.test/slow',client=client(lambda r:httpx.Response(429,headers={'retry-after':'2'})),sleep=sleep)
  self.assertEqual((result['category'],result['attempts'],waits),('throttled',2,[2]))
  waits.clear();result=await retrieval.fetch('https://e.test/slower',client=client(lambda r:httpx.Response(429,headers={'retry-after':'120'})),sleep=sleep)
  self.assertEqual((result['attempts'],waits),(1,[]))

 async def test_network_failure_and_timeout(self):
  def down(request):raise httpx.ConnectError('refused')
  def slow(request):raise httpx.ReadTimeout('slow')
  self.assertEqual((await retrieval.fetch('https://e.test/down',client=client(down),sleep=nowait))['category'],'network')
  result=await retrieval.fetch('https://e.test/slow',client=client(slow),sleep=nowait)
  self.assertEqual((result['category'],result['attempts']),('timeout',3))

class EngineStatusTests(unittest.IsolatedAsyncioTestCase):
 async def test_error_envelopes_count_as_failed_actions(self):
  h=Harness([stream([tool_call(0,'h1','history_read',{'message_id':424242})]),text('Not found.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'read it'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(h.store.rows("SELECT status FROM actions WHERE name='history_read'")[0]['status'],'error')
  finally:h.close()

if __name__=='__main__':unittest.main()
