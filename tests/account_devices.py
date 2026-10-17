import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
os.environ.setdefault('STUDIO_PORT','3210')

import httpx
from backend import identity,profiles,config

USER={'id':'a'*32,'provider':'github','name':'Aaron'}
ACCOUNT={'id':'d'*32,'name':'Aaron'}

def client_for(handler):
 real=httpx.AsyncClient
 return lambda **kw:real(transport=httpx.MockTransport(handler),**{k:v for k,v in kw.items() if k!='follow_redirects'})

class Service:
 def __init__(self,account=ACCOUNT):
  self.account=account;self.requests=[]
  self.devices=[{'id':'1'*16,'current':True,'provider':'github','label':'DESKTOP-AARON','created':1,'last_seen':2,'expires':3},
   {'id':'2'*16,'current':False,'provider':'google','label':None,'created':1,'last_seen':2,'expires':3},{'id':'bad','current':False}]
 def __call__(self,request):
  self.requests.append((request.method,request.url.path,json.loads(request.content) if request.content else None,request.headers.get('authorization')))
  if request.url.path=='/session':return httpx.Response(200,json={'user':USER,'account':self.account})
  if request.url.path=='/sessions':return httpx.Response(404,json={'error':'Not found'}) if self.devices is None else httpx.Response(200,json={'devices':self.devices,'idle_days':30,'max_days':90})
  if request.url.path=='/sessions/revoke':
   body=json.loads(request.content)
   if body.get('others'):return httpx.Response(200,json={'revoked':1})
   return httpx.Response(200,json={'revoked':1,'current':False}) if body['id']=='2'*16 else httpx.Response(404,json={'error':'That device is not signed in to your account'})
  return httpx.Response(404,json={'error':'Not found'})

class Base(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  profiles.PATH.unlink(missing_ok=True);identity.forget_gate()
  self.data=Path(tempfile.mkdtemp(dir=FOLDER.name));self.service=Service()
  self.patches=[patch.object(identity,'DATA',self.data),patch.object(identity,'SESSION',self.data/'identity-session.bin'),
   patch.object(identity,'read_session',lambda path=None:'c'*64),patch.object(identity.httpx,'AsyncClient',client_for(self.service))]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  identity.forget_gate();profiles.PATH.unlink(missing_ok=True)
 def local(self,**extra):
  data=profiles.registry();item={'id':'e'*32,'name':'Work','provider':'local',**extra};data['profiles'].append(item);profiles.save(data);return item

class DeviceTests(Base):
 async def test_list_validates_rows_and_states_the_rules(self):
  result=await identity.devices()
  self.assertTrue(result['available']);self.assertEqual([d['id'] for d in result['devices']],['1'*16,'2'*16])
  self.assertEqual(result['devices'][1]['label'],'Unnamed device');self.assertEqual((result['idle_days'],result['max_days'],result['offline_days']),(30,90,7))
  self.assertEqual(self.service.requests[0][3],'Bearer '+'c'*64)
 async def test_revoking_another_device(self):
  self.assertEqual((await identity.revoke_device('2'*16))['revoked'],1)
  self.assertEqual(self.service.requests[-1][2],{'id':'2'*16})
 async def test_this_device_uses_sign_out_instead(self):
  with self.assertRaisesRegex(ValueError,'Sign out on this PC'):await identity.revoke_device('1'*16)
  self.assertFalse(any(r[1]=='/sessions/revoke' for r in self.service.requests))
 async def test_unknown_and_malformed_devices(self):
  with self.assertRaisesRegex(ValueError,'not signed in to your account'):await identity.revoke_device('3'*16)
  with self.assertRaises(ValueError):await identity.revoke_device('../x')
 async def test_sign_out_everywhere_else(self):
  self.assertEqual((await identity.revoke_others())['revoked'],1);self.assertEqual(self.service.requests[-1][2],{'others':True})
 async def test_older_service_reports_unavailable_without_failing(self):
  self.service.devices=None
  result=await identity.devices()
  self.assertFalse(result['available']);self.assertIn('updated sign-in service',result['message'])
 async def test_no_session_asks_to_sign_in(self):
  with patch.object(identity,'read_session',lambda path=None:None):
   with self.assertRaisesRegex(ValueError,'Sign in first'):await identity.devices()
 def test_device_label_is_the_pc_name_without_odd_characters(self):
  with patch('platform.node',return_value='DESKTOP-<AARON>\n'):self.assertEqual(identity.device_label(),'DESKTOP-AARON')
  with patch('platform.node',return_value=''):self.assertEqual(identity.device_label(),'This PC')

class MigrationTests(Base):
 def test_choices_are_explicit_and_never_move_data(self):
  p=self.local()
  r=profiles.migrate(p['id'],'attach',ACCOUNT);self.assertIn('stay exactly where they are',r['message'])
  saved=next(x for x in profiles.registry()['profiles'] if x['id']==p['id']);self.assertEqual((saved['account_id'],saved['migration'],saved['provider']),(ACCOUNT['id'],'attached','local'))
  profiles.migrate(p['id'],'separate');saved=next(x for x in profiles.registry()['profiles'] if x['id']==p['id']);self.assertNotIn('account_id',saved);self.assertEqual(saved['migration'],'separate')
  profiles.migrate(p['id'],'untouched');saved=next(x for x in profiles.registry()['profiles'] if x['id']==p['id']);self.assertEqual(saved,{'id':p['id'],'name':'Work','provider':'local'})
 def test_invalid_choices(self):
  p=self.local()
  for args in ((p['id'],'merge'),('missing','attach',ACCOUNT),(p['id'],'attach',None)):
   with self.assertRaises(ValueError):profiles.migrate(*args)
  data=profiles.registry();data['profiles'].append({'id':'f'*32,'name':'GitHub','provider':'github','identity_id':USER['id']});profiles.save(data)
  with self.assertRaisesRegex(ValueError,'already belongs'):profiles.migrate('f'*32,'attach',ACCOUNT)
 def test_cannot_lock_yourself_out(self):
  data=profiles.registry();data['require_sign_in']=True;profiles.save(data)
  with patch.object(profiles,'PROFILE_ID','local'),self.assertRaisesRegex(ValueError,'lock you out'):profiles.migrate('local','separate')
 def test_attached_profiles_can_be_selected_when_sign_in_is_required(self):
  p=self.local();data=profiles.registry();data['require_sign_in']=True;profiles.save(data)
  with self.assertRaisesRegex(ValueError,'not attached'):profiles.select(p['id'])
  profiles.migrate(p['id'],'attach',ACCOUNT);self.assertTrue(profiles.select(p['id'])['restart_required'])

class GateTests(Base):
 async def gate(self,profile_id):
  data=profiles.registry();data['require_sign_in']=True;profiles.save(data)
  with patch.object(config,'PROFILE_ID',profile_id):return await identity.gate(force=True)
 async def test_attached_profile_opens_for_its_account_only(self):
  p=self.local(account_id=ACCOUNT['id'],migration='attached')
  self.assertTrue((await self.gate(p['id']))['unlocked'])
  self.service.account={'id':'9'*32,'name':'Someone else'}
  result=await self.gate(p['id']);self.assertFalse(result['unlocked']);self.assertIn('different Luminaria account',result['reason'])
 async def test_separate_profile_stays_locked_when_sign_in_is_required(self):
  p=self.local(migration='separate')
  result=await self.gate(p['id']);self.assertFalse(result['unlocked']);self.assertIn('kept separate',result['reason'])
 async def test_undecided_profile_keeps_existing_behaviour(self):
  self.assertTrue((await self.gate('local'))['unlocked'])

if __name__=='__main__':unittest.main()
