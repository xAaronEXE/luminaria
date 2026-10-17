import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import identity,profiles

class SecretStorageTests(unittest.TestCase):
 def test_windows_encryption_roundtrip_and_tamper_rejection(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'session.bin';token='ab'*32;identity.save_session(path,token)
   self.assertNotIn(token.encode(),path.read_bytes());self.assertEqual(identity.read_session(path),token)
   path.write_bytes(b'corrupt')
   with self.assertRaisesRegex(ValueError,'could not be unlocked'):identity.read_session(path)

class IdentityFlowTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  identity.pending.clear();self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.user={'id':'12345678-1234-4234-8234-123456789012','provider':'github','name':'Fixture Account','expires':9999999999}
  self.device='a'*64;self.secret='b'*64;self.token='c'*64;self.revoked=False;self.sent=[]
  self.patches=[patch.object(identity,'BASE_DATA',self.root),patch.object(identity,'DATA',self.root),patch.object(identity,'SESSION',self.root/'current.bin'),patch.object(profiles,'PATH',self.root/'profiles.json')]
  for p in self.patches:p.start()
 async def asyncTearDown(self):
  for p in reversed(self.patches):p.stop()
  identity.pending.clear();self.temp.cleanup()
 def transport(self,request):
  self.sent.append((request.url.path,request.headers.get('Authorization')))
  if request.url.path=='/health':return httpx.Response(200,json={'providers':[{'id':'github','configured':True}]})
  if request.url.path=='/device/start':return httpx.Response(200,json={'device_id':self.device,'device_secret':self.secret,'verification_uri':identity.ORIGIN+'/authorize?device='+self.device,'expires_in':600})
  if request.url.path=='/device/poll':return httpx.Response(200,json={'access_token':self.token})
  if request.url.path=='/session':return httpx.Response(401,json={}) if self.revoked else httpx.Response(200,json={'user':self.user})
  if request.url.path=='/logout':self.revoked=True;return httpx.Response(200,json={})
  raise AssertionError(request.url.path)
 def clients(self):
  constructor=httpx.AsyncClient
  return patch.object(identity.httpx,'AsyncClient',side_effect=lambda **kwargs:constructor(transport=httpx.MockTransport(self.transport),**kwargs))
 async def test_pairing_preserves_current_profile_and_encrypts_provider_session(self):
  with self.clients():
   flow=await identity.start('github');self.assertNotIn(self.secret,json.dumps(flow))
   result=await identity.poll(flow['flow_id']);self.assertFalse(result['restart_required']);self.assertNotIn(self.token,json.dumps(result))
   path=self.root/'identity-github.bin';self.assertEqual(identity.read_session(path),self.token)
   self.assertFalse(profiles.PATH.exists())
   status=await identity.status();self.assertTrue(status['signed_in']);self.assertEqual(status['connections'][0]['provider'],'github')
   await identity.logout();self.assertFalse(path.exists());self.assertTrue(self.revoked)
 async def test_revoked_session_cannot_create_an_account_profile(self):
  with self.clients():
   flow=await identity.start('github');self.revoked=True
   with self.assertRaises(httpx.HTTPStatusError):await identity.poll(flow['flow_id'])
   self.assertFalse(profiles.PATH.exists());self.assertFalse(list(self.root.glob('profiles/*/identity-session.bin')))
 async def test_multiple_provider_sessions_are_verified_together(self):
  identity.save_session(self.root/'identity-github.bin','1'*64)
  identity.save_session(self.root/'identity-discord.bin','2'*64)
  def transport(request):
   if request.url.path=='/session':
    provider='github' if request.headers['Authorization'].endswith('1'*64) else 'discord'
    return httpx.Response(200,json={'user':{**self.user,'provider':provider}})
   return self.transport(request)
  constructor=httpx.AsyncClient
  with patch.object(identity.httpx,'AsyncClient',side_effect=lambda **kwargs:constructor(transport=httpx.MockTransport(transport),**kwargs)):
   result=await identity.status()
  self.assertEqual({u['provider'] for u in result['connections']},{'github','discord'})
  self.assertFalse(profiles.PATH.exists())
 async def test_provider_mismatch_fails_and_revokes_issued_session(self):
  with self.clients():
   flow=await identity.start('github');self.user['provider']='discord'
   with self.assertRaisesRegex(ValueError,'did not match'):await identity.poll(flow['flow_id'])
   self.assertTrue(self.revoked);self.assertFalse(profiles.PATH.exists())
 async def test_browser_cancellation_stops_waiting_without_a_profile(self):
  original=self.transport
  self.transport=lambda request:httpx.Response(403,json={'error':'cancelled'}) if request.url.path=='/device/poll' else original(request)
  with self.clients():
   flow=await identity.start('google')
   with self.assertRaisesRegex(ValueError,'cancelled or permission was denied'):await identity.poll(flow['flow_id'])
   self.assertNotIn(flow['flow_id'],identity.pending);self.assertFalse(profiles.PATH.exists())
   self.assertNotIn('/session',[path for path,_ in self.sent])
 async def test_same_server_identity_reuses_profile_without_email_linking(self):
  first=profiles.identity_profile(self.user);second=profiles.identity_profile(self.user)
  self.assertEqual(first['id'],second['id'])
  third=profiles.identity_profile({**self.user,'provider':'discord'})
  self.assertNotEqual(first['id'],third['id'])
 async def test_unconfigured_provider_and_expired_flow_fail(self):
  with self.assertRaises(ValueError):await identity.start('unknown')
  with self.assertRaisesRegex(ValueError,'expired'):await identity.poll('d'*64)
 async def test_cancel_removes_private_pairing_and_cannot_be_polled(self):
  with self.clients():
   flow=await identity.start('github');identity.cancel(flow['flow_id'])
   self.assertNotIn(flow['flow_id'],identity.pending)
   with self.assertRaisesRegex(ValueError,'expired'):await identity.poll(flow['flow_id'])
 async def test_publisher_has_not_configured_provider(self):
  with patch.object(identity.httpx,'AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503,json={'error':'unconfigured'})))):
   with self.assertRaisesRegex(ValueError,'not been configured'):await identity.start('github')
 async def test_offline_logout_preserves_encrypted_session(self):
  identity.save_session(identity.SESSION,self.token)
  def offline(request):raise httpx.ConnectError('Fixture offline',request=request)
  with patch.object(identity.httpx,'AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(offline))):
   with self.assertRaises(httpx.ConnectError):await identity.logout()
  self.assertEqual(identity.read_session(),self.token)
 async def test_foreign_verification_link_is_rejected(self):
  def foreign(request):return httpx.Response(200,json={'device_id':self.device,'device_secret':self.secret,'verification_uri':'https://example.invalid/login'})
  with patch.object(identity.httpx,'AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(foreign))):
   with self.assertRaisesRegex(ValueError,'invalid sign-in link'):await identity.start('github')
  self.assertEqual(identity.pending,{})
 async def test_cancel_during_server_validation_never_selects_profile(self):
  entered=asyncio.Event();release=asyncio.Event();constructor=httpx.AsyncClient
  async def transport(request):
   if request.url.path=='/session':entered.set();await release.wait()
   return self.transport(request)
  with patch.object(identity.httpx,'AsyncClient',side_effect=lambda **kwargs:constructor(transport=httpx.MockTransport(transport),**kwargs)):
   flow=await identity.start('github');task=asyncio.create_task(identity.poll(flow['flow_id']))
   await asyncio.wait_for(entered.wait(),2);identity.cancel(flow['flow_id']);release.set()
   with self.assertRaisesRegex(ValueError,'cancelled'):await task
  self.assertFalse(profiles.PATH.exists());self.assertTrue(self.revoked)
