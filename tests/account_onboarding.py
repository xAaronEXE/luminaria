import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
FOLDER=tempfile.TemporaryDirectory();os.environ['STUDIO_DATA']=FOLDER.name
from backend import onboarding,profiles,config,preferences
from backend.store import Store

class OnboardingTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'test.sqlite')
  self.identity={'signed_in':True,'user':{'id':'a'*32,'name':'Test user'},'account':{'id':'a'*32}}
  self.patches=[patch.object(profiles,'PATH',self.root/'profiles.json'),patch.object(config,'PROFILE_ID','local'),patch.object(config,'CONFIG',{'workspace':str(self.root),'model':'local-test'}),patch.object(config,'CONFIG_PATH',self.root/'config.json'),patch.object(preferences,'shared_appearance_path',lambda:self.root/'appearance.json'),patch.object(onboarding.identity,'status',AsyncMock(return_value=self.identity))]
  for p in self.patches:p.start()
 def tearDown(self):
  self.store.db.close()
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 async def test_complete_saves_settings_and_is_scoped_to_account(self):
  self.assertFalse((await onboarding.status(self.store))['completed'])
  await onboarding.complete(self.store,{'name':'My workspace','workspace':str(self.root),'mode':'dark'})
  self.assertTrue((await onboarding.status(self.store))['completed'])
  self.assertEqual(profiles.registry()['profiles'][0]['name'],'My workspace')
  self.assertEqual(preferences.load_shared_appearance()['mode'],'dark')
  self.identity['account']['id']='b'*32
  self.assertFalse((await onboarding.status(self.store))['completed'])
 async def test_invalid_setup_and_signed_out_requests_are_rejected(self):
  with self.assertRaises(ValueError):await onboarding.complete(self.store,{'name':'','workspace':str(self.root),'mode':'dark'})
  with self.assertRaises(ValueError):await onboarding.complete(self.store,{'name':'Valid','workspace':str(self.root/'missing'),'mode':'dark'})
  self.assertIsNone(self.store.setting('onboarding_accounts'))
  self.identity['signed_in']=False
  with self.assertRaises(ValueError):await onboarding.status(self.store)

def tearDownModule():FOLDER.cleanup()
