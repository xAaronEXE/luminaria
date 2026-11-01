import os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
FOLDER=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ['STUDIO_DATA']=FOLDER.name
# A fresh install requires sign-in; these route tests start from an open local profile.
(__import__('pathlib').Path(FOLDER.name)/'profiles.json').write_text(__import__('json').dumps({'selected':'local','profiles':[{'id':'local','name':'Personal','provider':'local'}]}))
os.environ['STUDIO_PORT']='3210'
from fastapi.testclient import TestClient
from backend import app as server
from backend.config import CONFIG

class WorkflowRouteTests(unittest.TestCase):
 def test_api_requires_explicit_approval_and_verifies_the_output(self):
  workspace=Path(FOLDER.name)/'Files';workspace.mkdir(exist_ok=True)
  with patch.dict(CONFIG,{'workspace':str(workspace),'mcp':{}}),TestClient(server.app,base_url='http://127.0.0.1:3210') as client:
   headers={'X-Studio-Token':client.get('/api/bootstrap').json()['token']}
   created=client.post('/api/file-workflows',headers=headers,json={'objective':'Verify route execution','completion_criteria':'Output contains exact test text','allowed_locations':['reports'],'steps':[{'action':'create','path':'reports/route.txt','content':'route evidence'}]})
   self.assertEqual(created.status_code,200);id=created.json()['id']
   self.assertEqual(client.post(f'/api/file-workflows/{id}/run',headers=headers,json={}).status_code,400)
   self.assertFalse((workspace/'reports/route.txt').exists())
   self.assertEqual(client.post(f'/api/file-workflows/{id}/run',headers=headers,json={'approved':True}).status_code,200)
   for _ in range(100):
    plans=client.get('/api/file-workflows',headers=headers).json()['workflows'];plan=next(p for p in plans if p['id']==id)
    if plan['state']!='Running':break
    time.sleep(.02)
   self.assertEqual(plan['state'],'Awaiting review');self.assertEqual((workspace/'reports/route.txt').read_text(),'route evidence')
   self.assertEqual(client.post(f'/api/file-workflows/{id}/accept',headers=headers).json()['state'],'Completed')
   self.assertEqual(client.post(f'/api/file-workflows/{id}/run',headers=headers,json={'approved':True}).status_code,400)
   self.assertEqual(client.get('/api/file-workflows').status_code,403)
 def test_tuning_requires_opt_in_before_runtime_start(self):
  with patch.dict(CONFIG,{'mcp':{}}),TestClient(server.app,base_url='http://127.0.0.1:3210') as client:
   headers={'X-Studio-Token':client.get('/api/bootstrap').json()['token']}
   self.assertEqual(client.post('/api/tuning/start',headers=headers,json={'model':'not-installed'}).status_code,400)
   self.assertEqual(client.post('/api/tuning/start',headers=headers,json={'model':'not-installed','consent':True}).status_code,400)

def tearDownModule():
 server.store.db.close();FOLDER.cleanup()
