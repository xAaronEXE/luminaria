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
 def test_whole_pc_in_review_mode_too(self):
  # The whole PC is always in reach; review mode only changes approvals, not where files can be.
  config.CONFIG.update(access_mode='review',whole_pc=False)
  other=Path(tempfile.mkdtemp())/'a'
  self.assertEqual(config.workspace_path(str(other),roam=True),other.resolve())
 def test_home_shortcut(self):
  from unittest import mock
  with mock.patch.dict(os.environ,{'HOME':tempfile.mkdtemp(),'USERPROFILE':tempfile.mkdtemp()}):
   self.assertEqual(config.workspace_path('~/notes-luminaria-test.txt',roam=True),(Path.home()/'notes-luminaria-test.txt').resolve())
 def test_manual_is_readable_never_writable(self):
  m=config.manual_path()
  self.assertEqual(config.workspace_path(str(m),roam=True),m)
  with self.assertRaises(PermissionError):config.workspace_path(str(m),roam=True,write=True)
 def test_pc_places(self):
  places=config.pc_places()
  self.assertTrue(places['drives']);self.assertEqual(places['home'],str(Path.home()))
class OwnFolders(unittest.TestCase):
 def setUp(self): config.CONFIG.update(access_mode='full',whole_pc=True)
 def test_skill_folders_readable_never_writable(self):
  config.CONFIG['workspace']=tempfile.mkdtemp()
  for folder in config.skill_folders():
   target=folder/'some-skill'/'scripts'/'run.py'
   self.assertEqual(config.workspace_path(str(target)),target.resolve())
   with self.assertRaises(PermissionError):config.workspace_path(str(target),write=True)
 def test_working_folder_that_contains_luminaria_data_cannot_reach_it(self):
  # The working folder is a whole drive (here: the folder that holds the data folder), as on the owner's PC.
  config.CONFIG['workspace']=str(config.BASE_DATA.parent)
  with self.assertRaises(PermissionError):config.workspace_path(str(config.BASE_DATA/'profiles.json'))
  with self.assertRaises(PermissionError):config.workspace_path(str(config.DATA/'config.json'),roam=True)
  other=config.BASE_DATA.parent/'notes.txt'
  self.assertEqual(config.workspace_path('notes.txt'),other.resolve())
 def test_default_working_folder_inside_luminaria_still_works(self):
  work=config.DATA/'Files'/'local';work.mkdir(parents=True,exist_ok=True);config.CONFIG['workspace']=str(work)
  self.assertEqual(config.workspace_path('report.docx',write=True),(work/'report.docx').resolve())
  with self.assertRaises(PermissionError):config.workspace_path(str(config.DATA/'config.json'))

class SyncScope(unittest.TestCase):
 def test_too_broad_folders_refused(self):
  from backend.cloud_sync import CloudSync
  sync=CloudSync.__new__(CloudSync)
  for bad in (Path.home(),Path(Path.home().anchor or '/'),config.APP_HOME.parent):
   with self.assertRaises(ValueError):sync.check_scope(bad)
  sync.check_scope(Path(tempfile.mkdtemp()))
if __name__=='__main__':unittest.main()
