import os,sys,tempfile,time,unittest

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
os.environ.setdefault('STUDIO_PORT','3210')

from fastapi.testclient import TestClient
from backend import app as server

class ConnectorRouteTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(server.app,base_url='http://127.0.0.1:3210',headers={'X-Studio-Token':server.TOKEN})
  cls.client.__enter__()
 @classmethod
 def tearDownClass(cls):
  cls.client.__exit__(None,None,None);FOLDER.cleanup()

 def test_custom_connector_starts_without_restart_and_can_be_removed(self):
  r=self.client.post('/api/connectors',json={'name':'scratch','command':sys.executable,'args':['-c','pass']})
  self.assertEqual(r.status_code,200,r.text)
  self.assertIn('scratch',server.connectors);self.assertIn('scratch',server.CONFIG['mcp'])
  r=self.client.delete('/api/connectors/scratch')
  self.assertEqual(r.status_code,200,r.text)
  self.assertNotIn('scratch',server.connectors);self.assertNotIn('scratch',server.CONFIG['mcp'])

 def test_built_in_names_are_protected(self):
  self.assertEqual(self.client.post('/api/connectors',json={'name':'github','command':'x','args':[]}).status_code,400)
  for name in ('browser','github','missing'):
   with self.subTest(name=name):self.assertEqual(self.client.delete('/api/connectors/'+name).status_code,404)

 def test_integration_catalog_and_disconnect(self):
  r=self.client.get('/api/integrations');self.assertEqual(r.status_code,200)
  self.assertEqual({i['id'] for i in r.json()['integrations']},{'github','linear','notion','slack','gmail','google_drive','google_calendar'})
  self.assertEqual(self.client.post('/api/integrations/github',json={}).status_code,400)
  self.assertEqual(self.client.delete('/api/integrations/unknown').status_code,404)
  self.assertEqual(self.client.delete('/api/integrations/github').status_code,200)

 def test_oauth_callback_needs_no_token_but_refuses_unknown_state(self):
  r=self.client.get('/oauth/callback?code=x&state=nope',headers={'X-Studio-Token':''})
  self.assertEqual(r.status_code,400);self.assertIn('expired',r.text)

if __name__=='__main__':unittest.main()
