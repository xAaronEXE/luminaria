import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import skills
from backend.config import ROOT

class Live:status='connected'

class SkillInventoryTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.patch=patch.object(skills,'DATA',Path(self.folder.name));self.patch.start()
 def tearDown(self):self.patch.stop();self.folder.cleanup()

 def test_every_installed_skill_is_in_the_inventory_and_vice_versa(self):
  installed={p.parent.name for p in (ROOT/'skills').glob('*/SKILL.md')}
  listed=set(skills.inventory()['skills'])
  self.assertEqual(installed,listed)
  categories=set(skills.inventory()['categories'])
  for name,info in skills.inventory()['skills'].items():
   with self.subTest(name=name):
    self.assertIn(info['category'],categories)
    self.assertLessEqual(set(info.get('requires',[])),set(skills.NEEDS))
    self.assertGreater(len((ROOT/'skills'/name/'SKILL.md').read_text('utf-8').strip()),100)

 def test_availability_follows_real_connectors_and_tool_settings(self):
  with patch.object(skills,'external_tools_enabled',lambda:False):
   rows={s['name']:s for s in skills.catalog({})}
   self.assertTrue(rows['research']['available'])
   self.assertEqual(rows['gh-fix-ci']['missing'],[skills.NEEDS['github'],skills.NEEDS['execution']])
   self.assertEqual(rows['playwright']['missing'],[skills.NEEDS['browser'],skills.NEEDS['execution']])
  with patch.object(skills,'external_tools_enabled',lambda:True):
   rows={s['name']:s for s in skills.catalog({'browser':Live(),'github':Live()})}
   self.assertTrue(rows['playwright']['available']);self.assertTrue(rows['gh-fix-ci']['available'])
   self.assertEqual(rows['screenshot']['missing'],[skills.NEEDS['windows']])

 def test_imported_skills_can_be_removed_but_built_ins_cannot(self):
  skills.save_skill('my-flow','# my-flow\n\nDo the thing carefully.')
  row=next(s for s in skills.catalog() if s['name']=='my-flow')
  self.assertTrue(row['local']);self.assertEqual(row['category'],'Imported')
  skills.remove_skill('my-flow');self.assertNotIn('my-flow',[s['name'] for s in skills.catalog()])
  with self.assertRaises(ValueError):skills.remove_skill('research')
  with self.assertRaises(ValueError):skills.remove_skill('../x')

if __name__=='__main__':unittest.main()
