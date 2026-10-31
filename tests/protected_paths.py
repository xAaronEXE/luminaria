import os,tempfile,unittest
from pathlib import Path
os.environ['STUDIO_DATA']=tempfile.mkdtemp()
from backend import config
class Protected(unittest.TestCase):
 def setUp(self):
  self.work=Path(tempfile.mkdtemp());config.CONFIG.update(workspace=str(self.work),access_mode='full',whole_pc=True)
 def test_other_folder_allowed(self):
  other=Path(tempfile.mkdtemp())/'a.txt'
  self.assertEqual(config.workspace_path(str(other),roam=True),other.resolve())
 def test_own_data_and_credentials_blocked(self):
  for target in (config.DATA/'config.json',config.BASE_DATA/'profiles.json',Path.home()/'.ssh'/'id_rsa',config.APP_HOME/'x'):
   with self.assertRaises(PermissionError):config.workspace_path(str(target),roam=True)
 def test_preview_endpoint_style_call_stays_scoped(self):
  other=Path(tempfile.mkdtemp())/'a.txt'
  with self.assertRaises(ValueError):config.workspace_path(str(other))
 def test_off_without_whole_pc(self):
  config.CONFIG['whole_pc']=False
  with self.assertRaises(ValueError):config.workspace_path(str(Path(tempfile.mkdtemp())/'a'),roam=True)
class SyncScope(unittest.TestCase):
 def test_too_broad_folders_refused(self):
  from backend.cloud_sync import CloudSync
  sync=CloudSync.__new__(CloudSync)
  for bad in (Path.home(),Path(Path.home().anchor or '/'),config.APP_HOME.parent):
   with self.assertRaises(ValueError):sync.check_scope(bad)
  sync.check_scope(Path(tempfile.mkdtemp()))
if __name__=='__main__':unittest.main()
