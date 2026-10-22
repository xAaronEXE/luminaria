import asyncio,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
from backend import hardware
from backend.store import Store

class HardwareTuningTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.store=Store(self.root/'test.sqlite3');self.exe=self.root/'server.exe';self.exe.write_bytes(b'fixture executable, never run')
  self.weights=self.root/'model.gguf';self.weights.write_bytes(b'fixture weights, never loaded')
  self.model={'id':'test','model_file':str(self.weights),'context':4096};self.info={'hardware_id':'fixture','runtime_version':'fixture version'}
  self.config=patch.dict(hardware.CONFIG,{'llama_executable':str(self.exe)});self.config.start()
 def tearDown(self):self.config.stop();self.store.db.close();self.temp.cleanup()
 async def test_measurements_require_explicit_application_and_rollback(self):
  original={'threads':2,'gpu_layers':0};self.model['tuning']=original
  async def measure(model,t,g,progress):return {'threads':t,'gpu_layers':g,'median_tps':t+g+1,'repetitions':[{}, {}, {}]}
  job=hardware.Tuning(self.store)
  with patch.object(hardware,'measure_variant',measure),patch.object(hardware.psutil,'cpu_count',lambda **kw:8):
   job.start(self.model,{'threads':[2,4],'gpu_layers':[0]},self.info);await job.task
  self.assertEqual(self.model['tuning'],original)
  with patch.object(hardware,'registry',lambda:[self.model]),patch.object(hardware,'save') as save:
   result=hardware.apply_profile(self.store,job.job['id'],self.info)
   self.assertTrue(result['restart_required']);self.assertEqual(self.model['tuning']['threads'],4);save.assert_called_once()
   hardware.apply_profile(self.store,None,self.info,rollback=True)
   self.assertEqual(self.model['tuning'],original)
 async def test_changed_model_or_runtime_invalidates_selection(self):
  identity=hardware.provenance(self.model,self.info)
  self.store.set_setting('tuning_history',[{'id':'job','state':'Completed','model':'test','provenance':identity,'best':{'threads':4,'gpu_layers':0}}])
  self.weights.write_bytes(b'changed fixture')
  with patch.object(hardware,'registry',lambda:[self.model]),patch.object(hardware,'save') as save:
   with self.assertRaisesRegex(ValueError,'changed'):hardware.apply_profile(self.store,'job',self.info)
   save.assert_not_called()
 async def test_cancel_retains_completed_partial_variants(self):
  started=asyncio.Event()
  async def measure(*args):started.set();await asyncio.Event().wait()
  job=hardware.Tuning(self.store)
  with patch.object(hardware,'measure_variant',measure):
   job.start(self.model,{'threads':[1],'gpu_layers':[0]},self.info)
   await started.wait();await job.cancel()
  self.assertEqual(job.job['state'],'Cancelled');self.assertEqual(self.store.setting('tuning_history')[0]['state'],'Cancelled')
 def test_invalid_thread_and_layer_inputs_are_rejected(self):
  for body in ({'threads':[True]},{'threads':[0]},{'gpu_layers':[-2]},{'gpu_layers':'all'}):
   with self.subTest(body=body),self.assertRaises(ValueError):hardware.choices(body)
 async def test_immediate_and_repeated_stop_do_not_leave_a_running_record(self):
  job=hardware.Tuning(self.store)
  with patch.object(hardware,'measure_variant',AsyncMock(side_effect=AssertionError('must not load a model'))):
   job.start(self.model,{'threads':[1],'gpu_layers':[0]},self.info)
   await job.cancel();await job.cancel()
  self.assertEqual(job.job['state'],'Cancelled')
  self.assertEqual(len(self.store.setting('tuning_history')),1)
 async def test_repeated_stop_allows_inflight_cleanup_to_finish(self):
  started=asyncio.Event();cleaned=asyncio.Event()
  async def measure(*args):
   started.set()
   try:await asyncio.Event().wait()
   finally:await asyncio.sleep(.05);cleaned.set()
  job=hardware.Tuning(self.store)
  with patch.object(hardware,'measure_variant',measure):
   job.start(self.model,{'threads':[1],'gpu_layers':[0]},self.info)
   await started.wait();await asyncio.gather(job.cancel(),job.cancel())
  self.assertTrue(cleaned.is_set());self.assertEqual(job.job['state'],'Cancelled')
