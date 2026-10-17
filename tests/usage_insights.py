import asyncio,json,tempfile,unittest
from datetime import date,datetime,timezone
from pathlib import Path
from unittest.mock import patch
from tests.work_events import FOLDER,Harness,stream,tool_call
import httpx
from backend import identity,usage as usage_module
from backend.store import Store
from backend.usage import Usage,streaks,task_times

def answer(text,usage=None,timings=None):
 chunks=[{'choices':[{'delta':{'content':text}}]}]
 if usage or timings:chunks.append({'choices':[],**({'usage':usage} if usage else {}),**({'timings':timings} if timings else {})})
 return stream(chunks)

def ts(day,hour=12):return datetime.fromisoformat(f'{day}T{hour:02d}:00:00+00:00').timestamp()

class EngineRecording(unittest.IsolatedAsyncioTestCase):
 async def test_task_records_tokens_tools_skills_and_no_content(self):
  first=stream([tool_call(0,'c1','load_skill',{'name':'missing-skill'}),tool_call(1,'c2','read_file',{'path':'a.txt'}),
   {'choices':[],'usage':{'prompt_tokens':900,'completion_tokens':40,'prompt_tokens_details':{'cached_tokens':600}}}])
  h=Harness([first,answer('Secret answer text',{'prompt_tokens':1000,'completion_tokens':64},{'cache_n':512})])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'please read a.txt'})
   h.engine.start(chat,reasoning=True);await h.engine.tasks[chat]
   rows=h.engine.usage.rows()
   gens=[r for r in rows if r['kind']=='generation'];tools=[r for r in rows if r['kind']=='tool'];tasks=[r for r in rows if r['kind']=='task']
   self.assertEqual([g['data']['completion_tokens'] for g in gens],[40,64])
   self.assertEqual([g['data']['cached_tokens'] for g in gens],[600,512])
   self.assertTrue(all(g['data']['reasoning'] for g in gens))
   self.assertEqual({t['name']:t['status'] for t in tools},{'load_skill':'error','read_file':'done'})
   self.assertNotIn('skill',next(t for t in tools if t['name']=='load_skill')['data'])
   self.assertEqual(len(tasks),1);task=tasks[0]['data']
   self.assertEqual((task['tokens_in'],task['tokens_out'],task['generations'],task['tool_ok'],task['tool_failed']),(1900,104,2,1,1))
   self.assertTrue(task['reasoning']);self.assertGreaterEqual(task['active'],0);self.assertEqual(task['wait'],0)
   dump=json.dumps(rows)
   for private in ('a.txt','please read','Secret answer','missing-skill'):self.assertNotIn(private,dump)
   h.engine.usage.task({**h.engine.runs[chat]},[],None)
   self.assertEqual(len(h.engine.usage.rows('task')),1)
  finally:h.close()

 async def test_approval_wait_is_separated_from_active_time(self):
  h=Harness([stream([tool_call(0,'c1','write_file',{'path':'b.txt','content':'y'})]),answer('ok')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'write'})
   h.engine.start(chat);await h.engine.tasks[chat]
   await asyncio.sleep(0.3)
   h.engine.resume(chat,{'approved':True});await h.engine.tasks[chat]
   task=h.engine.usage.rows('task')[0]['data']
   self.assertGreaterEqual(task['wait'],0.3);self.assertLess(task['active'],task['wall']);self.assertEqual(task['paused'],0)
   tool=h.engine.usage.rows('tool')[0];self.assertEqual((tool['name'],tool['status']),('write_file','done'))
   self.assertIsInstance(tool['data']['duration_ms'],int)
  finally:h.close()

 async def test_generation_without_usage_is_labelled_missing(self):
  h=Harness([answer('hi')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'hi'})
   h.engine.start(chat);await h.engine.tasks[chat]
   summary=h.engine.usage.summary()
   self.assertEqual(summary['lifetime']['total'],0)
   self.assertTrue(any('without token counts' in m for m in summary['missing']))
   self.assertTrue(any('cached' in m for m in summary['missing']))
  finally:h.close()

class Measures(unittest.TestCase):
 def setUp(self):
  self.store=Store(Path(tempfile.mkdtemp(dir=FOLDER.name))/'s.sqlite3');self.usage=Usage(self.store)
 def tearDown(self):self.store.db.close()
 def gen(self,key,day,tokens_in,tokens_out,tps=None,model='m1',hour=12,reasoning=False):
  self.usage.record('generation',key,run='r'+key,model=model,status='done',created=ts(day,hour),prompt_tokens=tokens_in,completion_tokens=tokens_out,tps=tps,reasoning=reasoning)

 def test_empty_history_reports_no_coverage(self):
  s=self.usage.summary()
  self.assertIsNone(s['coverage_start']);self.assertIn('earlier activity is not reconstructed',s['missing'][0])

 def test_streaks_busiest_day_fastest_and_history(self):
  for i,(day,tin,tout,tps) in enumerate([('2026-10-01',100,50,20.0),('2026-10-02',10,5,90.0),('2026-10-03',10,40,40.0),('2026-10-05',2000,10,None),('2026-10-06',1,1,None)]):
   self.gen(str(i),day,tin,tout,tps)
  self.usage.record('task','t1',run='t1',created=ts('2026-10-05'),active=30,wait=500,paused=0,wall=530,tokens_in=2000,tokens_out=10,generations=1)
  self.usage.record('task','t2',run='t2',created=ts('2026-10-03'),active=90,wait=0,paused=10,wall=100,tokens_in=10,tokens_out=40,generations=1)
  s=self.usage.summary('UTC',today=date(2026,10,7))
  self.assertEqual(s['streak']['longest'],3);self.assertEqual(s['streak']['current'],2)
  self.assertEqual(s['busiest_day'],{'day':'2026-10-05','tokens':2010,'generations':1})
  self.assertEqual(s['fastest']['tps'],40.0) # 90 tok/s came from a 5-token reply, too short to count.
  self.assertEqual(s['largest_task']['run'],'t1');self.assertEqual(s['longest_task']['run'],'t2');self.assertEqual(s['longest_task']['active'],90)
  self.assertEqual(len(s['history']),30);self.assertEqual(s['history'][-1]['day'],'2026-10-07')
  self.assertFalse(s['history'][0]['covered']);self.assertTrue(s['history'][-2]['covered'])
  self.assertEqual(s['lifetime']['total'],2227);self.assertIsNone(s['lifetime']['cached'])
  self.assertEqual(self.usage.summary('UTC',today=date(2026,10,9))['streak']['current'],0)

 def test_days_follow_the_chosen_time_zone(self):
  self.gen('late','2026-10-01',10,10,hour=23)
  self.assertEqual([d['day'] for d in self.usage.days(usage_module.zone('UTC')[0])],['2026-10-01'])
  self.assertEqual([d['day'] for d in self.usage.days(usage_module.zone('Asia/Tokyo')[0])],['2026-10-02'])
  self.assertEqual(usage_module.zone('Not/AZone')[1],'')
  s=self.usage.summary('Not/AZone');self.assertFalse(s['timezone_valid'])

 def test_skills_tools_and_integrations_are_counted_separately(self):
  run={'id':'r1','model_id':'m1'}
  self.usage.tool(run,'a1','list_skills','done');self.usage.tool(run,'a2','load_skill','done',5,'pdf-tools');self.usage.tool(run,'a3','load_skill','done',5,'pdf-tools')
  self.usage.tool(run,'a4','github__create_issue','error');self.usage.tool(run,'a5','github__list','done');self.usage.tool(run,'a6','run_command','denied')
  self.usage.tool(run,'a7','load_skill','done',5,'../escape')
  self.usage.skill('viewed','pdf-tools');self.usage.skill('enabled','pdf-tools');self.usage.skill('disabled','other')
  s=self.usage.summary()
  self.assertEqual(s['skills']|{'top':None},{'browsed_by_assistant':1,'viewed':1,'enabled':1,'disabled':1,'invoked':2,'top':None})
  self.assertEqual(s['skills']['top'],[{'name':'pdf-tools','count':2}])
  self.assertEqual(s['integrations'],[{'name':'github','ok':1,'failed':1,'denied':0}])
  self.assertIn({'name':'run_command','ok':0,'failed':0,'denied':1},s['tools'])
  self.usage.tool(run,'a2','load_skill','done',5,'pdf-tools')
  self.assertEqual(self.usage.summary()['skills']['invoked'],2) # Same action id: replay ignored.

 def test_export_and_delete(self):
  self.gen('1','2026-10-01',10,10)
  out=self.usage.export('UTC')
  self.assertEqual(len(out['events']),1);self.assertEqual(out['days'][0]['metrics']['tokens_in'],10)
  self.assertEqual(self.usage.delete(),1);self.assertEqual(self.usage.rows(),[])

class Times(unittest.TestCase):
 def test_overlapping_waits_and_pauses_are_not_double_counted(self):
  events=[{'type':'approval.requested','node':'a','at':10},{'type':'run.interrupted','at':15},{'type':'run.resumed','at':40},
   {'type':'approval.allowed','node':'a','at':45},{'type':'approval.requested','node':'b','at':90}]
  self.assertEqual(task_times(events,0,100),{'wall':100,'active':55,'wait':20,'paused':25})
 def test_streak_rules(self):
  self.assertEqual(streaks([],date(2026,1,1))['current'],0)
  self.assertEqual(streaks(['2025-12-31'],date(2026,1,1))['current'],1)

class Sync(unittest.IsolatedAsyncioTestCase):
 async def test_sync_uploads_daily_totals_only_and_reads_account_view(self):
  store=Store(Path(tempfile.mkdtemp(dir=FOLDER.name))/'s.sqlite3');u=Usage(store);sent=[]
  u.record('generation','g1',run='r1',model='m',status='done',created=ts('2026-10-01'),prompt_tokens=50,completion_tokens=20)
  u.record('tool','t1',run='r1',name='web_fetch',status='error',created=ts('2026-10-01'),integration=None)
  def handler(request):
   sent.append((request.method,request.url.path,json.loads(request.content) if request.content else None))
   if request.method=='POST':return httpx.Response(200,json={'stored':1})
   return httpx.Response(200,json={'devices':2,'days':[{'day':'2026-10-01','metrics':{'tokens_in':80,'tokens_out':30,'generations':2}},{'day':'2026-10-02','metrics':{'generations':1,'tokens_in':5}}]})
  real=httpx.AsyncClient
  with patch.object(identity,'_any_session',lambda missing='':'c'*64),patch.object(identity.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**{k:v for k,v in kw.items() if k!='follow_redirects'})):
   first=await usage_module.sync(store,u,'UTC');again=await usage_module.sync(store,u,'UTC')
  uploads=[b for m,p,b in sent if m=='POST']
  self.assertEqual(uploads[0],uploads[1]) # Same totals each time: the service replaces, never adds.
  day=uploads[0]['days'][0];self.assertEqual(day['day'],'2026-10-01');self.assertEqual(set(day['metrics']),set(usage_module.SYNC_KEYS))
  self.assertEqual((day['metrics']['tokens_in'],day['metrics']['tool_failed']),(50,1))
  self.assertNotIn('web_fetch',json.dumps(uploads));self.assertNotIn('m',uploads[0]['days'][0])
  self.assertEqual(first['account']['devices'],2);self.assertEqual(first['account']['total'],115);self.assertEqual(first['account']['active_days'],2)
  self.assertIsNotNone(store.setting('insights_sync')['last_sync']);store.db.close()

 async def test_old_service_and_signed_out_errors_are_readable(self):
  real=httpx.AsyncClient
  with patch.object(identity,'_any_session',lambda missing='':'c'*64),patch.object(identity.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(404,json={'error':'Not found'})),**{k:v for k,v in kw.items() if k!='follow_redirects'})):
   with self.assertRaisesRegex(ValueError,'updated sign-in service'):await usage_module.service('GET','/insights/days')
  with patch.object(identity,'DATA',Path(tempfile.mkdtemp(dir=FOLDER.name))),patch.object(identity,'SESSION',Path(tempfile.mkdtemp(dir=FOLDER.name))/'none.bin'):
   with self.assertRaisesRegex(ValueError,'Sign in to sync'):await usage_module.service('GET','/insights/days')

if __name__=='__main__':unittest.main()
