import asyncio,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import file_workflows as files
from backend.store import Store

class FileWorkflowTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.workspace=self.root/'Files';self.workspace.mkdir()
  self.store=Store(self.root/'state.sqlite3');self.patch=patch.dict(files.CONFIG,{'workspace':str(self.workspace)});self.patch.start();self.service=files.Workflows(self.store)
 def tearDown(self):self.patch.stop();self.store.db.close();self.temp.cleanup()
 def plan(self,steps,allowed=None):return files.create(self.store,{'objective':'Prepare verified output','completion_criteria':'Expected text and original recoverable','allowed_locations':allowed or ['reports'],'steps':steps})
 async def test_read_create_edit_trash_and_recovery_are_verified(self):
  directory=self.workspace/'reports';directory.mkdir();(directory/'source.txt').write_bytes(b'original\r\ntext')
  plan=self.plan([{'action':'read','path':'reports/source.txt'},{'action':'create','path':'reports/result.txt','content':'draft'},{'action':'edit','path':'reports/result.txt','old_text':'draft','new_text':'final'},{'action':'trash','path':'reports/source.txt'}])
  with patch.object(files,'FULL_ACCESS',True):self.service.start(plan['id'],True)
  await self.service.task;result=files.get(self.store,plan['id'])
  self.assertEqual(result['state'],'Awaiting review');self.assertTrue(all(s['state']=='Verified' for s in result['steps']))
  self.assertEqual((directory/'result.txt').read_text(),'final');self.assertFalse((directory/'source.txt').exists())
  result=self.service.accept(plan['id']);self.assertEqual(result['state'],'Completed')
  self.service.restore(plan['id'],result['steps'][-1]['id']);self.assertEqual((directory/'source.txt').read_bytes(),b'original\r\ntext')
  with self.assertRaises(ValueError):self.service.restore(plan['id'],result['steps'][-1]['id'])
 async def test_changed_source_stops_without_overwriting(self):
  (self.workspace/'reports').mkdir();path=self.workspace/'reports/a.txt';path.write_text('old')
  plan=self.plan([{'action':'edit','path':'reports/a.txt','old_text':'old','new_text':'new'}]);path.write_text('manual edit')
  self.service.start(plan['id']);await self.service.task
  self.assertEqual(path.read_text(),'manual edit');self.assertEqual(files.get(self.store,plan['id'])['state'],'Needs review')
 async def test_recovered_effect_is_not_replayed_after_restart(self):
  plan=self.plan([{'action':'create','path':'reports/a.txt','content':'result'}]);step=plan['steps'][0]
  self.service.step(plan,step);step['state']='Running';plan['state']='Running';files.persist(self.store,plan)
  restarted=files.Workflows(self.store);result=restarted.recover(files.get(self.store,plan['id']))
  self.assertTrue(result['steps'][0]['recovered']);self.assertEqual(result['state'],'Awaiting review')
  with self.assertRaises(ValueError):restarted.start(plan['id'])
 async def test_uncertain_crash_outcome_is_not_retried(self):
  plan=self.plan([{'action':'create','path':'reports/a.txt','content':'planned'}]);step=plan['steps'][0]
  (self.workspace/'reports').mkdir();(self.workspace/'reports/a.txt').write_text('different')
  step['state']='Running';files.persist(self.store,plan)
  with self.assertRaises(ValueError):self.service.start(plan['id'])
  self.assertEqual(files.get(self.store,plan['id'])['steps'][0]['state'],'Uncertain')
 async def test_stop_prevents_next_effect_and_review_cannot_run_all(self):
  plan=self.plan([{'action':'create','path':'reports/a.txt','content':'a'},{'action':'create','path':'reports/b.txt','content':'b'}])
  with patch.object(files,'FULL_ACCESS',False),self.assertRaises(ValueError):self.service.start(plan['id'],True)
  self.service.start(plan['id']);self.service.stop();await self.service.task
  self.assertFalse((self.workspace/'reports/b.txt').exists())
  self.assertEqual(files.get(self.store,plan['id'])['state'],'Stopped')
 async def test_crlf_edit_is_exact_and_accept_checks_final_content(self):
  (self.workspace/'reports').mkdir();path=self.workspace/'reports/a.txt';path.write_bytes(b'old\r\nsecond')
  plan=self.plan([{'action':'edit','path':'reports/a.txt','old_text':'old','new_text':'new'}]);self.service.start(plan['id']);await self.service.task
  self.assertEqual(path.read_bytes(),b'new\r\nsecond');path.write_text('changed after verification')
  with self.assertRaises(ValueError):self.service.accept(plan['id'])
 def test_paths_and_overwrites_are_rejected_before_execution(self):
  (self.workspace/'reports').mkdir();(self.workspace/'reports/a.txt').write_text('existing')
  for step in ({'action':'create','path':'../outside.txt','content':'x'},{'action':'create','path':'other/a.txt','content':'x'},{'action':'create','path':'reports/a.txt','content':'x'},{'action':'delete','path':'reports/a.txt'}):
   with self.subTest(step=step),self.assertRaises(ValueError):self.plan([step])
 def test_new_instance_retains_recovery_data_and_never_claims_read_execution(self):
  (self.workspace/'reports').mkdir();(self.workspace/'reports/a.txt').write_text('evidence')
  plan=self.plan([{'action':'read','path':'reports/a.txt'}]);plan['steps'][0]['state']='Running';files.persist(self.store,plan)
  result=files.Workflows(self.store).recover(files.get(self.store,plan['id']))
  self.assertEqual(result['steps'][0]['state'],'Ready');self.assertNotIn('result',result['steps'][0])
