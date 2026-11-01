import os,tempfile,unittest

FOLDER=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ['STUDIO_DATA']=FOLDER.name
# A fresh install requires sign-in; these route tests start from an open local profile.
(__import__('pathlib').Path(FOLDER.name)/'profiles.json').write_text(__import__('json').dumps({'selected':'local','profiles':[{'id':'local','name':'Personal','provider':'local'}]}))
os.environ['STUDIO_PORT']='3210'
from fastapi.testclient import TestClient
from backend import app as server

class WorkEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(server.app,base_url='http://127.0.0.1:3210',headers={'X-Studio-Token':server.TOKEN});cls.client.__enter__()
  cls.chat=server.store.create_chat('Evidence fixture');cls.other=server.store.create_chat('Other chat')
  server.store.save_summary(cls.chat,1,'Earlier summary');cls.first=server.store.summary(cls.chat)['id']
  server.store.save_summary(cls.chat,2,'Latest summary')
 @classmethod
 def tearDownClass(cls):
  cls.client.__exit__(None,None,None);server.store.db.close();FOLDER.cleanup()
 def test_historical_summary_is_resolved_exactly(self):
  response=self.client.get(f'/api/chats/{self.chat}/summaries/{self.first}')
  self.assertEqual(response.status_code,200);self.assertEqual(response.json()['content'],'Earlier summary')
 def test_cross_chat_reference_is_rejected(self):
  self.assertEqual(self.client.get(f'/api/chats/{self.other}/summaries/{self.first}').status_code,404)
 def test_authentication_still_required(self):
  self.assertEqual(self.client.get(f'/api/chats/{self.chat}/summaries/{self.first}',headers={'X-Studio-Token':''}).status_code,403)
