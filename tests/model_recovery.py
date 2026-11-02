import os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name

import httpx
from backend import runtime
from backend.engine import Engine,CONFIG

class Fake:
 def __init__(self,handler):
  self.client=httpx.AsyncClient(transport=httpx.MockTransport(handler));self.events=[]
 def broadcast(self,event):self.events.append(event)
 async def refresh_models(self,model_id):return None

async def instant(seconds):return None

async def read(fake):
 async with Engine.model_stream(fake,{'model':'x'}) as response:
  return response.status_code,(await response.aread()).decode()

class DiagnoseTests(unittest.TestCase):
 def test_runtime_is_discovered_without_developer_machine_paths(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);exe=root/'runtime/local-ai/runtime-vulkan/llama-server.exe'
   exe.parent.mkdir(parents=True);exe.touch()
   with patch.object(runtime,'ROOT',root),patch.dict(CONFIG,llama_executable='C:/missing/old/runtime.exe'),patch('backend.config.save_config') as save:
    self.assertEqual(runtime.resolve_executable(),str(exe))
    save.assert_called_once_with({'llama_executable':str(exe)})

 def test_missing_packaged_runtime_reports_repair_not_manual_path_setup(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch.object(runtime,'ROOT',Path(folder)),patch.dict(CONFIG,llama_executable=''):
    with self.assertRaisesRegex(ValueError,'Repair or reinstall'):runtime.resolve_executable()

 def test_use_installed_model_configures_local_paths_and_endpoint(self):
  from backend import models
  with tempfile.TemporaryDirectory() as folder:
   model=Path(folder)/'downloaded.gguf';model.touch()
   entry={'id':'downloaded','model_file':str(model),'context':8192}
   with patch.object(models,'registry',lambda:[entry]),patch.object(runtime,'resolve_executable',lambda:'bundled/llama-server.exe'),patch.object(models,'save_config') as save:
    self.assertEqual(models.select('downloaded'),entry)
    value=save.call_args.args[0]
    self.assertEqual(value['model_file'],str(model))
    self.assertEqual(value['llama_executable'],'bundled/llama-server.exe')
    self.assertEqual(value['endpoint'],'http://127.0.0.1:8098/v1')

 def test_known_failures_get_plain_explanations(self):
  cases={'ggml_backend_cuda_buffer_type_alloc_buffer: allocating 9000 MiB on device 0: cudaMalloc failed: out of memory':'GPU memory',
         'gguf_init_from_file: invalid magic characters':'could not be loaded',
         'clip_model_load: failed to load vision model':'vision projector',
         'error while attempting to bind on address 127.0.0.1:8097: address already in use':'port',
         'upstream health check timed out after 180s':'too long'}
  for line,expected in cases.items():
   with self.subTest(line=line):self.assertIn(expected,runtime.diagnose('loading...\n'+line+'\nexit status 1'))
  self.assertIsNone(runtime.diagnose('srv  load_model: model loaded\nmain: server is listening'))

 def test_only_the_latest_start_is_considered(self):
  path=Path(FOLDER.name)/'llama-swap.log'
  path.write_text('cudaMalloc failed: out of memory\n'+runtime.START_MARKER+'\nmodel loaded\n',encoding='utf-8')
  with patch.object(runtime,'DATA',Path(FOLDER.name)):self.assertIsNone(runtime.diagnose())
  path.write_text(runtime.START_MARKER+'\nok\n'+runtime.START_MARKER+'\nerror loading model: bad file\n',encoding='utf-8')
  with patch.object(runtime,'DATA',Path(FOLDER.name)):self.assertIn('could not be loaded',runtime.diagnose())

 def test_manager_state_reports_an_exited_process(self):
  process=subprocess.Popen([sys.executable,'-c','raise SystemExit(3)']);process.wait()
  with patch.object(runtime,'swap_process',process):
   self.assertEqual(runtime.manager_state(),{'owned':True,'running':False,'exit_code':3})
   runtime.stop_owned()
  self.assertIsNone(runtime.swap_process)

class StaleModelTests(unittest.TestCase):
 def test_missing_saved_model_falls_back_to_an_installed_one(self):
  from backend import models
  with tempfile.TemporaryDirectory() as folder:
   model=Path(folder)/'qwen.gguf';model.touch()
   entry={'id':'qwen','model_file':str(model),'context':8192}
   with patch.object(models,'registry',lambda:[entry]),patch.dict(CONFIG,model='gone',model_file=str(Path(folder)/'gone.gguf')),patch('backend.config.save_config') as save:
    self.assertEqual(runtime.ensure_model_file(),str(model))
    self.assertEqual(save.call_args.args[0]['model'],'qwen')
   with patch.object(models,'registry',lambda:[]),patch.dict(CONFIG,model_file=''):
    self.assertIsNone(runtime.ensure_model_file())
 def test_swap_model_ids_reads_the_running_config(self):
  with tempfile.TemporaryDirectory() as folder:
   (Path(folder)/'llama-swap.yaml').write_text('{"models":{"a":{},"b":{}}}',encoding='utf-8')
   with patch.object(runtime,'DATA',Path(folder)):self.assertEqual(runtime.swap_model_ids(),{'a','b'})

class RefreshTests(unittest.IsolatedAsyncioTestCase):
 async def test_model_downloaded_after_start_restarts_the_manager(self):
  from backend import models
  calls=[]
  class F:
   def broadcast(self,e):pass
  with tempfile.TemporaryDirectory() as folder:
   model=Path(folder)/'new.gguf';model.touch()
   with patch.object(models,'registry',lambda:[{'id':'new','model_file':str(model)}]),patch.dict(CONFIG,endpoint='http://127.0.0.1:8098/v1'),\
        patch.object(runtime,'manager_state',lambda:{'owned':True,'running':True}),patch.object(runtime,'swap_model_ids',lambda:{'old'}),\
        patch.object(runtime,'stop_owned',lambda:calls.append('stop')),patch.object(runtime,'start_swap',lambda:calls.append('start')),patch.object(runtime,'listening',lambda p:True):
    await Engine.refresh_models(F(),'new')
    self.assertEqual(calls,['stop','start'])
    calls.clear();await Engine.refresh_models(F(),'old');self.assertEqual(calls,[])

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_first_question_starts_manager_after_models_were_installed(self):
  started=[]
  def handler(request):
   if not started:raise httpx.ConnectError('refused',request=request)
   return httpx.Response(200,text='data: [DONE]\n\n')
  with tempfile.TemporaryDirectory() as folder:
   exe=Path(folder)/'llama-server.exe';exe.touch()
   model=Path(folder)/'model.gguf';model.touch()
   with patch.dict(CONFIG,endpoint='http://127.0.0.1:8098/v1',llama_executable=str(exe),model_file=str(model)),\
        patch.object(runtime,'manager_state',lambda:{'owned':False,'running':False}),\
        patch.object(runtime,'start_swap',lambda:started.append(1) or {'started':True}),\
        patch.object(runtime,'listening',lambda port:True):
    status,body=await read(Fake(handler))
  self.assertEqual((status,started),(200,[1]))

 async def test_custom_endpoint_does_not_restart_even_an_owned_local_manager(self):
  def handler(request):raise httpx.ConnectError('refused',request=request)
  calls=[]
  with patch.dict(CONFIG,endpoint='http://192.0.2.1:8098/v1'),\
       patch.object(runtime,'manager_state',lambda:{'owned':True,'running':False}),\
       patch.object(runtime,'start_swap',lambda:calls.append(1)):
   with self.assertRaises(RuntimeError):await read(Fake(handler))
  self.assertEqual(calls,[])

 async def test_crashed_manager_is_restarted_once_and_the_request_retried(self):
  started=[]
  def handler(request):
   if not started:raise httpx.ConnectError('refused',request=request)
   return httpx.Response(200,text='data: [DONE]\n\n')
  fake=Fake(handler)
  with patch.object(runtime,'manager_state',lambda:{'owned':True,'running':not started==[],'exit_code':None if started else 1}),\
       patch.object(runtime,'start_swap',lambda:started.append(1) or {'started':True}),patch.object(runtime,'listening',lambda port:True):
   status,body=await read(fake)
  self.assertEqual((status,started),(200,[1]));self.assertEqual(fake.events[0]['type'],'model_recovering')

 async def test_repeated_crash_reports_the_diagnosed_reason(self):
  def handler(request):raise httpx.ConnectError('refused',request=request)
  with patch.object(runtime,'manager_state',lambda:{'owned':True,'running':False,'exit_code':1}),patch.object(runtime,'start_swap',lambda:{}),\
       patch.object(runtime,'listening',lambda port:False),patch.object(runtime,'diagnose',lambda:'Not enough GPU memory to load this model.'),\
       patch('backend.engine.asyncio.sleep',new=instant):
   with self.assertRaises(RuntimeError) as caught:await read(Fake(handler))
  self.assertIn('stopped (exit code 1)',str(caught.exception));self.assertIn('GPU memory',str(caught.exception))

 async def test_an_unmanaged_endpoint_is_never_restarted(self):
  def handler(request):raise httpx.ConnectError('refused',request=request)
  calls=[]
  with patch.dict(CONFIG,llama_executable='',model_file=''),patch.object(runtime,'manager_state',lambda:{'owned':False,'running':False}),patch.object(runtime,'start_swap',lambda:calls.append(1)):
   with self.assertRaises(RuntimeError) as caught:await read(Fake(handler))
  # Never restarted; with no model configured the user is told how to get one.
  self.assertEqual(calls,[]);self.assertIn('No model is installed yet',str(caught.exception))

if __name__=='__main__':unittest.main()
