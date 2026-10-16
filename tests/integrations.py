import asyncio,json,secrets,socket,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import httpx,uvicorn
from mcp.server.auth.provider import AccessToken,AuthorizationCode,RefreshToken,construct_redirect_uri
from mcp.server.auth.settings import AuthSettings,ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.shared.auth import OAuthToken
from backend import integrations
from backend.connectors import Connector

class Provider:
 """In-memory authorization server that approves every request, standing in for a hosted service."""
 def __init__(self):self.clients={};self.codes={};self.tokens={'static-token':AccessToken(token='static-token',client_id='static',scopes=[])};self.refresh={};self.deny=False
 async def get_client(self,client_id):return self.clients.get(client_id)
 async def register_client(self,info):self.clients[info.client_id]=info
 async def authorize(self,client,params):
  if self.deny:return construct_redirect_uri(str(params.redirect_uri),error='access_denied',state=params.state)
  code=secrets.token_hex(8)
  self.codes[code]=AuthorizationCode(code=code,scopes=params.scopes or [],expires_at=time.time()+300,client_id=client.client_id,code_challenge=params.code_challenge,
                                     redirect_uri=params.redirect_uri,redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,resource=params.resource)
  return construct_redirect_uri(str(params.redirect_uri),code=code,state=params.state)
 async def load_authorization_code(self,client,code):return self.codes.get(code)
 async def exchange_authorization_code(self,client,code):
  self.codes.pop(code.code);access,refresh=secrets.token_hex(8),secrets.token_hex(8)
  self.tokens[access]=AccessToken(token=access,client_id=client.client_id,scopes=code.scopes,expires_at=int(time.time())+3600,resource=code.resource)
  self.refresh[refresh]=RefreshToken(token=refresh,client_id=client.client_id,scopes=code.scopes)
  return OAuthToken(access_token=access,token_type='Bearer',expires_in=3600,refresh_token=refresh)
 async def load_refresh_token(self,client,token):return self.refresh.get(token)
 async def exchange_refresh_token(self,client,token,scopes):raise NotImplementedError
 async def load_access_token(self,token):return self.tokens.get(token)
 async def revoke_token(self,token):pass

def free_port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  cls.port=free_port();cls.base=f'http://127.0.0.1:{cls.port}';cls.provider=Provider()
  server=MCPServer('Test service',auth_server_provider=cls.provider,
                   auth=AuthSettings(issuer_url=cls.base,resource_server_url=cls.base+'/mcp',client_registration_options=ClientRegistrationOptions(enabled=True)))
  @server.tool()
  def echo(text:str)->str:
   return 'echo: '+text
  cls.uvicorn=uvicorn.Server(uvicorn.Config(server.streamable_http_app(),host='127.0.0.1',port=cls.port,log_level='warning'))
  threading.Thread(target=cls.uvicorn.run,daemon=True).start()
  for _ in range(100):
   if cls.uvicorn.started:break
   time.sleep(.05)
 @classmethod
 def tearDownClass(cls):cls.uvicorn.should_exit=True

 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.opened=[];self.provider.deny=False
  loop=asyncio.get_event_loop()
  def browser(url):
   self.opened.append(url)
   response=httpx.get(url,follow_redirects=False)
   location=response.headers['location']
   loop.call_soon_threadsafe(integrations.complete,location.split('?',1)[1])
   return True
  self.patches=[patch.object(integrations,'DATA',Path(self.folder.name)),patch.object(integrations.webbrowser,'open',browser)]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.folder.cleanup()

 async def connect(self,name,config):
  connector=Connector(name,config);connector.start()
  await asyncio.wait_for(connector.ready.wait(),20)
  return connector

 async def test_browser_sign_in_connects_and_remembers_tokens(self):
  connector=await self.connect('linear',{'url':self.base+'/mcp','auth':'oauth'})
  try:
   self.assertEqual(connector.status,'connected');self.assertEqual([t['name'] for t in connector.tools],['echo'])
   result=await connector.call('echo',{'text':'hi'})
   self.assertIn('echo: hi',json.dumps(result))
  finally:await connector.close()
  self.assertEqual(len(self.opened),1)
  saved=integrations.read_secrets('linear');self.assertIn('access_token',saved['tokens']);self.assertIn('client_id',saved['client'])
  again=await self.connect('linear',{'url':self.base+'/mcp','auth':'oauth'})
  try:self.assertEqual(again.status,'connected')
  finally:await again.close()
  self.assertEqual(len(self.opened),1,'stored tokens should be reused without another browser sign-in')

 async def test_denied_sign_in_is_reported(self):
  self.provider.deny=True
  connector=await self.connect('notion',{'url':self.base+'/mcp','auth':'oauth'})
  try:self.assertIn('cancelled or denied',connector.status)
  finally:await connector.close()
  self.assertNotIn('tokens',integrations.read_secrets('notion'))

 async def test_token_integrations_send_the_saved_token(self):
  integrations.write_secrets('github',{'token':'static-token'})
  connector=await self.connect('github',{'url':self.base+'/mcp','auth':'token'})
  try:self.assertEqual(connector.status,'connected')
  finally:await connector.close()
  integrations.write_secrets('github',{'token':'wrong'})
  connector=await self.connect('github',{'url':self.base+'/mcp','auth':'token'})
  try:self.assertTrue(connector.status.startswith('unavailable'),connector.status)
  finally:await connector.close()

class IntegrationConfigTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.patch=patch.object(integrations,'DATA',Path(self.folder.name));self.patch.start()
 def tearDown(self):self.patch.stop();self.folder.cleanup()

 def test_presets_validate_what_each_service_needs(self):
  config,values=integrations.config_for('github',{'token':'github_pat_abc','readonly':True})
  self.assertEqual(config,{'url':'https://api.githubcopilot.com/mcp/readonly','auth':'token','preset':'github','readonly':True});self.assertEqual(values['token'],'github_pat_abc')
  self.assertNotIn('github_pat_abc',json.dumps(config))
  for name,body in [('github',{}),('github',{'token':'has space'}),('gmail',{'client_id':'abc123def.apps'}),('slack',{}),('unknown',{})]:
   with self.subTest(name=name,body=body),self.assertRaises(ValueError):integrations.config_for(name,body)
  config,values=integrations.config_for('gmail',{'client_id':'123-abc.apps.googleusercontent.com','client_secret':'shh'})
  self.assertEqual(values['client_secret'],'shh');self.assertEqual(config['auth'],'oauth')

 def test_saved_token_is_kept_when_reconnecting_without_retyping(self):
  integrations.write_secrets('github',{'token':'github_pat_saved','url':'https://api.githubcopilot.com/mcp/'})
  _,values=integrations.config_for('github',{})
  self.assertEqual(values['token'],'github_pat_saved')

 def test_expired_or_unknown_callbacks_are_refused(self):
  ok,message=integrations.complete('code=x&state=unknown')
  self.assertFalse(ok);self.assertIn('expired',message)

 def test_catalog_never_reports_connected_without_a_live_connector(self):
  rows={r['id']:r for r in integrations.catalog({'notion':{'url':'https://mcp.notion.com/mcp','auth':'oauth'}},{})['integrations']}
  self.assertTrue(rows['notion']['configured']);self.assertFalse(rows['notion']['connected']);self.assertEqual(rows['notion']['status'],'not connected')
  self.assertIn('/oauth/callback',integrations.catalog({},{})['redirect_uri'])

if __name__=='__main__':unittest.main()
