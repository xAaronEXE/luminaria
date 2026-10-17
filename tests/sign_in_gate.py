import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
os.environ.setdefault('STUDIO_PORT','3210')

import httpx
from fastapi.testclient import TestClient
from backend import app as server,identity,profiles,config

USER={'id':'a'*32,'provider':'github','name':'Aaron'}

def client_for(handler):
 real=httpx.AsyncClient
 return lambda **kw:real(transport=httpx.MockTransport(handler),**{k:v for k,v in kw.items() if k!='follow_redirects'})

def ok(request):return httpx.Response(200,json={'user':USER})
def revoked(request):return httpx.Response(401)
def offline(request):raise httpx.ConnectError('offline',request=request)

class GateTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  profiles.PATH.unlink(missing_ok=True);identity.forget_gate()
  self.data=Path(tempfile.mkdtemp(dir=FOLDER.name))
  self.patches=[patch.object(identity,'DATA',self.data)]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  identity.forget_gate();profiles.PATH.unlink(missing_ok=True)

 def account_profile(self,required=True):
  data=profiles.registry();item={'id':'b'*32,'name':'Aaron','provider':'github','identity_id':USER['id']}
  data['profiles'].append(item);data['selected']=item['id']
  if required:data['require_sign_in']=True
  profiles.save(data);return item

 async def check(self,handler,profile_id='b'*32,token='c'*64):
  with patch.object(config,'PROFILE_ID',profile_id),patch.object(identity,'read_session',lambda path=None:token),patch.object(identity.httpx,'AsyncClient',client_for(handler)):
   return await identity.gate(force=True)

 async def test_not_required_is_always_unlocked(self):
  self.assertEqual(await identity.gate(),{'required':False,'unlocked':True})

 async def test_local_data_container_requires_a_valid_session(self):
  data=profiles.registry();data['require_sign_in']=True;profiles.save(data)
  result=await self.check(ok,profile_id='local',token=None)
  self.assertFalse(result['unlocked']);self.assertIn('Sign in',result['reason'])
  self.assertTrue((await self.check(ok,profile_id='local'))['unlocked'])

 async def test_verified_account_unlocks_and_records_the_check(self):
  self.account_profile()
  result=await self.check(ok)
  self.assertTrue(result['unlocked']);self.assertNotIn('offline',result)
  self.assertTrue((self.data/'identity-verified.json').is_file())

 async def test_offline_grace_lasts_seven_days(self):
  self.account_profile()
  (self.data/'identity-verified.json').write_text(json.dumps({'at':time.time()-2*86400,'name':'Aaron'}))
  result=await self.check(offline)
  self.assertTrue(result['unlocked']);self.assertTrue(result['offline']);self.assertIn('2 days ago',result['reason'])
  (self.data/'identity-verified.json').write_text(json.dumps({'at':time.time()-8*86400,'name':'Aaron'}))
  result=await self.check(offline)
  self.assertFalse(result['unlocked']);self.assertIn('cannot reach',result['reason'])

 async def test_revoked_or_mismatched_sessions_lock(self):
  self.account_profile()
  (self.data/'identity-verified.json').write_text(json.dumps({'at':time.time(),'name':'Aaron'}))
  result=await self.check(revoked)
  self.assertFalse(result['unlocked']);self.assertIn('expired',result['reason'])
  self.assertFalse((self.data/'identity-verified.json').exists())
  other=lambda request:httpx.Response(200,json={'user':{**USER,'id':'d'*32}})
  self.assertFalse((await self.check(other))['unlocked'])
  self.assertFalse((await self.check(ok,token=None))['unlocked'])

 async def test_turning_on_requires_a_verified_online_account(self):
  with patch.object(config,'PROFILE_ID','local'):
   with self.assertRaises(ValueError):await identity.set_required(True)
  self.assertNotIn('require_sign_in',profiles.registry())
  self.account_profile(required=False)
  with patch.object(config,'PROFILE_ID','b'*32),patch.object(identity,'read_session',lambda path=None:'c'*64),patch.object(identity.httpx,'AsyncClient',client_for(offline)):
   with self.assertRaises(ValueError):await identity.set_required(True)
  self.assertNotIn('require_sign_in',profiles.registry())
  with patch.object(config,'PROFILE_ID','b'*32),patch.object(identity,'read_session',lambda path=None:'c'*64),patch.object(identity.httpx,'AsyncClient',client_for(ok)):
   self.assertEqual(await identity.set_required(True),{'required':True})
  self.assertTrue(profiles.registry()['require_sign_in'])
  with self.assertRaises(ValueError):profiles.select('local')
  self.assertEqual(await identity.set_required(False),{'required':False})
  profiles.select('local')

class MiddlewareTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(server.app,base_url='http://127.0.0.1:3210',headers={'X-Studio-Token':server.TOKEN});cls.client.__enter__()
 @classmethod
 def tearDownClass(cls):cls.client.__exit__(None,None,None)
 def tearDown(self):profiles.PATH.unlink(missing_ok=True);identity.forget_gate()

 def test_locked_app_only_serves_sign_in_routes(self):
  self.assertEqual(self.client.get('/api/state').status_code,200)
  data=profiles.registry();data['require_sign_in']=True;profiles.save(data);identity.forget_gate()
  r=self.client.get('/api/state');self.assertEqual(r.status_code,423);self.assertTrue(r.json()['locked'])
  self.assertEqual(self.client.post('/api/chat',json={}).status_code,423)
  self.assertEqual(self.client.post('/api/identity/require',json={'enabled':False}).status_code,423)
  self.assertEqual(self.client.get('/api/gate').status_code,200)
  self.assertEqual(self.client.get('/api/bootstrap').status_code,200)
  self.assertEqual(self.client.get('/').status_code,200)

def tearDownModule():
 server.store.db.close();FOLDER.cleanup()

if __name__=='__main__':unittest.main()
