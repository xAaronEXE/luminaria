import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import skill_setup,skills

class Ready:status='connected'
class SetupTests(unittest.TestCase):
 def test_guide_targets_actual_missing_requirements(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(skills.CONFIG,workspace=folder),patch.object(skills,'external_tools_enabled',lambda:False),patch.object(skill_setup,'external_tools_enabled',lambda:False):
   result=skill_setup.checklist('gh-fix-ci',{})
   self.assertFalse(result['ready']);self.assertEqual([s['id'] for s in result['steps']],['github','execution'])
   self.assertTrue(all(not s['ready'] for s in result['steps']))
 def test_live_connector_and_permission_readiness(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(skills.CONFIG,workspace=folder),patch.object(skills,'external_tools_enabled',lambda:True),patch.object(skill_setup,'external_tools_enabled',lambda:True):
   result=skill_setup.checklist('playwright',{'browser':Ready()})
   self.assertTrue(result['ready']);self.assertTrue(all(s['ready'] for s in result['steps']))
 def test_missing_working_folder_has_real_setup_destination(self):
  with patch.dict(skills.CONFIG,workspace='Z:/nonexistent-luminaria-setup-folder'):
   result=skill_setup.checklist('research',{})
   self.assertFalse(result['ready']);self.assertEqual(result['steps'][0]['action'],'workspace')
 def test_unknown_skill_or_connector_is_rejected(self):
  with self.assertRaises(ValueError):skill_setup.checklist('../escape',{})
  with self.assertRaises(ValueError):skill_setup.connector_config('arbitrary')
 def test_existing_connector_is_reused_without_changing_settings(self):
  config={'command':'existing','args':['--existing']}
  with patch.dict(skill_setup.CONFIG,mcp={'browser':config}):
   self.assertEqual(skill_setup.connector_config('browser'),config)

if __name__=='__main__':unittest.main()
