import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import updates

PAYLOAD=b'test installer - never execute'
NAME='Luminaria-9.0.0-Setup.exe'

def manifest(digest=None,size=None,url=None,version='9.0.0',name=NAME):
 return {'version':version,'notes':'Notes','installer':{'name':name,'size':len(PAYLOAD) if size is None else size,'sha256':digest or hashlib.sha256(PAYLOAD).hexdigest(),'url':url or f'{updates.CHANNEL}/download/v{version}/{name}'}}

class UpdateTests(unittest.IsolatedAsyncioTestCase):
 def client(self,latest,payload=PAYLOAD,status=200):
  def respond(request):
   if request.url.path.endswith('/latest'):
    return httpx.Response(status,json=latest)
   return httpx.Response(200,content=payload)
  original=httpx.AsyncClient
  return patch.object(updates.httpx,'AsyncClient',lambda *a,**k:original(transport=httpx.MockTransport(respond)))
 async def install(self,latest,payload=PAYLOAD):
  with tempfile.TemporaryDirectory() as folder,patch.object(updates,'DATA',Path(folder)),self.client(latest,payload),patch.object(updates.subprocess,'Popen') as launch:
   saved=lambda:list((Path(folder)/'updates').glob('*'))
   try:return await updates.install(),launch,saved()
   except ValueError as e:return e,launch,saved()
 async def test_verified_installer_launches(self):
  result,launch,files=await self.install(manifest())
  self.assertTrue(result['launched']);launch.assert_called_once();self.assertEqual([f.name for f in files],[NAME])
 async def test_corrupt_installer_never_launches(self):
  result,launch,files=await self.install(manifest(digest='0'*64))
  self.assertIn('Checksum mismatch',str(result));launch.assert_not_called();self.assertEqual(files,[])
 async def test_oversized_download_stops(self):
  result,launch,files=await self.install(manifest(size=4))
  self.assertIn('larger',str(result));launch.assert_not_called();self.assertEqual(files,[])
 async def test_foreign_installer_address_rejected(self):
  result,launch,_=await self.install(manifest(url='https://example.com/'+NAME))
  self.assertIn('unexpected address',str(result));launch.assert_not_called()
 async def test_channel_states_are_explained(self):
  for status,text in ((503,'not set up'),(404,'No release'),(409,'missing its installer')):
   with self.client({},status=status):
    result=await updates.check()
   self.assertFalse(result['available']);self.assertIn(text,result['message'])
 async def test_same_version_is_not_offered(self):
  with self.client(manifest(version=updates.CONFIG['version'],name=f"Luminaria-{updates.CONFIG['version']}-Setup.exe")):
   result=await updates.check()
  self.assertFalse(result['installable']);self.assertIn('latest version',result['message'])
 async def test_offline_check_is_not_an_error(self):
  def fail(request):raise httpx.ConnectError('offline')
  original=httpx.AsyncClient
  with patch.object(updates.httpx,'AsyncClient',lambda *a,**k:original(transport=httpx.MockTransport(fail))):
   result=await updates.check()
  self.assertFalse(result['reachable']);self.assertIn('Could not reach',result['message'])
 def test_packaged_handoff_waits_for_owned_processes_before_setup(self):
  import sys
  from backend import update_handoff,runtime
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/NAME;target.write_bytes(PAYLOAD)
   with patch.object(sys,'frozen',True,create=True),patch.object(runtime,'swap_process') as manager,patch.object(update_handoff.subprocess,'Popen') as launch:
    manager.pid=12345;manager.poll.return_value=None
    self.assertTrue(update_handoff.launch(target))
    args=launch.call_args.args[0]
    self.assertIn('-ParentId',args);self.assertIn('-ManagerId',args)
    self.assertEqual(args[args.index('-ManagerId')+1],'12345')
    self.assertEqual(args[args.index('-Digest')+1],hashlib.sha256(PAYLOAD).hexdigest())
    script=(Path(folder)/'update-handoff.ps1').read_text('utf-8-sig')
    self.assertLess(script.index('WaitForExit(30000)'),script.index('Start-Process -FilePath $Installer'))
    self.assertIn('Process identity changed',script);self.assertIn('Installer checksum changed',script)
 def test_unowned_model_server_is_not_targeted(self):
  import sys
  from backend import update_handoff,runtime
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/NAME;target.write_bytes(PAYLOAD)
   with patch.object(sys,'frozen',True,create=True),patch.object(runtime,'swap_process',None),patch.object(update_handoff.subprocess,'Popen') as launch:
    update_handoff.launch(target)
    args=launch.call_args.args[0]
    self.assertEqual(args[args.index('-ManagerId')+1],'0')

if __name__=='__main__':unittest.main()
