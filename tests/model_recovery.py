import os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name

import httpx
from backend import runtime
from backend.engine import Engine

class Fake:
 def __init__(self,handler):
  self.client=httpx.AsyncClient(transport=httpx.MockTransport(handler));self.events=[]
 def broadcast(self,event):self.events.append(event)

async def instant(seconds):return None

async def read(fake):
 async with Engine.model_stream(fake,{'model':'x'}) as response:
  return response.status_code,(await response.aread()).decode()

class DiagnoseTests(unittest.TestCase):
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

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
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
  with patch.object(runtime,'manager_state',lambda:{'owned':False,'running':False}),patch.object(runtime,'start_swap',lambda:calls.append(1)):
   with self.assertRaises(RuntimeError) as caught:await read(Fake(handler))
  self.assertEqual(calls,[]);self.assertIn('Cannot reach the model server',str(caught.exception))

if __name__=='__main__':unittest.main()
