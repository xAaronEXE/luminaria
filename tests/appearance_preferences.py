import unittest
from backend.preferences import DEFAULTS,migrate,validate

class AppearancePreferenceTests(unittest.TestCase):
 def test_default_is_black_on_white_with_no_accent(self):
  self.assertEqual(DEFAULTS['appearance']['mode'],'light');self.assertEqual(DEFAULTS['appearance']['accent'],'')
 def test_saved_mode_migrates_and_unsaved_profiles_default_to_light(self):
  self.assertEqual(migrate({'theme_mode':'dark'})['appearance']['mode'],'dark')
  self.assertEqual(migrate({})['appearance']['mode'],'light')
  kept={'appearance':{'mode':'system','accent':'#112233','modes':{'dark':{},'light':{}},'version':1}}
  self.assertEqual(migrate(kept),kept)
 def test_custom_colors_validate_per_mode(self):
  value=validate({'appearance':{'mode':'system','accent':'#3366FF','modes':{'dark':{'accent':'#99BBFF','colors':{'bg':'#050505','entity':'#FFFFFF'}}}}})['appearance']
  self.assertEqual(value['modes']['dark']['colors']['bg'],'#050505');self.assertEqual(value['modes']['light'],{})
  for bad in ({'mode':'sepia'},{'accent':'blue'},{'modes':{'dark':{'colors':{'unknown':'#000000'}}}},{'modes':{'dark':{'colors':{'bg':'black'}}}},{'modes':{'dim':{}}}):
   with self.assertRaises(ValueError):validate({'appearance':bad})
  self.assertEqual(validate({'theme_mode':'system'})['theme_mode'],'system')

if __name__=='__main__':unittest.main()
