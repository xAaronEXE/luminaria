import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import voice,voice_assets
class VoiceDownloadTests(unittest.TestCase):
 def setup_download(self,payload,expected=None,status=200):
  root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup);folder=Path(root.name)
  item={'name':'sample.onnx','url':'https://huggingface.co/test/resolve/pinned/sample.onnx','bytes':len(payload),'sha256':hashlib.sha256(expected if expected is not None else payload).hexdigest()}
  client=httpx.Client
  patches=[patch.dict(voice_assets.ASSETS,fixture=[item]),patch.object(httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(lambda req:httpx.Response(status,content=payload))))]
  for p in patches:p.start();self.addCleanup(p.stop)
  return folder
 def test_verified_download_is_saved_and_retry_reuses_it(self):
  folder=self.setup_download(b'model');voice._install_assets('fixture',folder)
  self.assertEqual((folder/'sample.onnx').read_bytes(),b'model')
  with patch.object(httpx,'Client',side_effect=AssertionError('must not redownload')):voice._install_assets('fixture',folder)
 def test_bad_checksum_preserves_existing_file(self):
  folder=self.setup_download(b'bad',expected=b'new');target=folder/'sample.onnx';target.write_bytes(b'old')
  with self.assertRaisesRegex(ValueError,'checksum'):voice._install_assets('fixture',folder)
  self.assertEqual(target.read_bytes(),b'old');self.assertEqual(list(folder.glob('*.part')),[])
 def test_http_error_is_actionable(self):
  folder=self.setup_download(b'no',status=503)
  with self.assertRaisesRegex(ValueError,'HTTP 503'):voice._install_assets('fixture',folder)
  self.assertFalse((folder/'sample.onnx').exists())
 def test_connection_error_is_actionable(self):
  folder=self.setup_download(b'model')
  with patch.object(httpx,'Client',side_effect=httpx.ConnectError('offline')):
   with self.assertRaisesRegex(ValueError,'connection'):voice._install_assets('fixture',folder)
 def test_disk_space_guard(self):
  import shutil
  folder=self.setup_download(b'model')
  with patch.object(shutil,'disk_usage',return_value=shutil._ntuple_diskusage(100,99,1)):
   with self.assertRaisesRegex(ValueError,'disk space'):voice._install_assets('fixture',folder)
if __name__=='__main__':unittest.main()
