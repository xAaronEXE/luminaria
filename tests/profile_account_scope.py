import os,tempfile,unittest
from unittest.mock import patch
FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
from backend import app as server

class ScopeTests(unittest.TestCase):
 @classmethod
 def tearDownClass(cls):server.store.db.close();FOLDER.cleanup()
 def test_cached_totals_are_hidden_when_signed_out_mismatched_or_disabled(self):
  saved={'account_id':'a'*32,'devices':2,'daily':[{'day':'2026-10-21','metrics':{'tokens_in':20,'tokens_out':10,'generations':1}}]}
  server.store.set_setting('insights_account',saved)
  with patch.object(server,'insights_sync_public',lambda:{'enabled':True}):
   self.assertIsNone(server.profile_account_snapshot({'signed_in':False}))
   self.assertIsNone(server.profile_account_snapshot({'signed_in':True,'account':{'id':'b'*32}}))
   account=server.profile_account_snapshot({'signed_in':True,'account':{'id':'a'*32}})
   self.assertEqual(account['total'],30);self.assertEqual(len(account['grid']['cells']),371)
  with patch.object(server,'insights_sync_public',lambda:{'enabled':False}):
   self.assertIsNone(server.profile_account_snapshot({'signed_in':True,'account':{'id':'a'*32}}))

if __name__=='__main__':unittest.main()
