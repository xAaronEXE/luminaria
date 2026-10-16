import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import httpx
from backend import updates

class UpdateTests(unittest.IsolatedAsyncioTestCase):
 async def attempt(self,valid=True,name='Luminaria-0.2.3-Setup.exe'):
  payload=b'test installer - never execute'
  prefix='https://github.com/example/luminaria/releases/download/v0.2.3/'
  info={'available':True,'installable':True,'installer':{'name':name,'browser_download_url':prefix+name},'checksums':{'browser_download_url':prefix+'SHA256SUMS.txt'}}
  digest=hashlib.sha256(payload).hexdigest() if valid else '0'*64
  def respond(request):
   return httpx.Response(200,content=(digest+'  '+name).encode() if request.url.path.endswith('SHA256SUMS.txt') else payload)
  client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
  with tempfile.TemporaryDirectory() as folder,patch.object(updates,'DATA',Path(folder)),patch.dict(updates.CONFIG,release_repo='example/luminaria'),patch.object(updates,'check',AsyncMock(return_value=info)),patch.object(updates.httpx,'AsyncClient',return_value=client),patch.object(updates.subprocess,'Popen') as launch:
   if valid:
    result=await updates.install();self.assertTrue(result['launched']);launch.assert_called_once()
    self.assertEqual((Path(folder)/'updates'/name).read_bytes(),payload)
   else:
    with self.assertRaisesRegex(ValueError,'Checksum mismatch'):await updates.install()
    launch.assert_not_called();self.assertEqual(list((Path(folder)/'updates').iterdir()),[])
 async def test_luminaria_installer_verified_before_launch(self):await self.attempt()
 async def test_legacy_name_supported(self):await self.attempt(name='LocalAIStudio-0.2.3-Setup.exe')
 async def test_corrupt_installer_never_launched(self):await self.attempt(valid=False)
