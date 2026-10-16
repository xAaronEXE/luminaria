"""Hosted MCP integrations: presets, encrypted credentials and browser sign-in.

Signing in to Luminaria never grants an integration. Each integration is connected
separately here, and its tools still go through the normal approval rules.
"""
import asyncio,json,os,re,secrets,webbrowser
from contextlib import asynccontextmanager
from urllib.parse import parse_qs,urlparse
from .config import DATA

PRESETS={
 'github':{'label':'GitHub','about':'Repositories, issues, pull requests and code search.','url':'https://api.githubcopilot.com/mcp/','readonly_url':'https://api.githubcopilot.com/mcp/readonly','auth':'token',
  'token_label':'Fine-grained personal access token','setup':'Create a token at github.com/settings/personal-access-tokens/new and give it only the repositories and permissions you want the assistant to use.'},
 'linear':{'label':'Linear','about':'Issues, projects and comments.','url':'https://mcp.linear.app/mcp','readonly_url':'https://mcp.linear.app/mcp/readonly','auth':'oauth',
  'setup':'Your browser opens Linear to approve access. No keys are needed.'},
 'notion':{'label':'Notion','about':'Pages, databases and search.','url':'https://mcp.notion.com/mcp','auth':'oauth',
  'setup':'Your browser opens Notion to choose which pages to share. No keys are needed.'},
 'slack':{'label':'Slack','about':'Search and send messages in channels you can access.','url':'https://mcp.slack.com/mcp','auth':'oauth','client_id':True,
  'setup':'Slack only accepts approved apps. Create a Slack app, add the redirect URL below, and paste its client ID. A workspace admin may need to approve it.'},
 'gmail':{'label':'Gmail','about':'Read, search and draft email.','url':'https://gmailmcp.googleapis.com/mcp/v1','auth':'oauth','client_id':True,'client_secret':True,'google':True,
  'setup':'In Google Cloud, enable the Gmail MCP API, create an OAuth client for a web application, tick "Use this client for an AI-powered agent", and add the redirect URL below.'},
 'google_drive':{'label':'Google Drive','about':'Find and read files in your Drive.','url':'https://drivemcp.googleapis.com/mcp/v1','auth':'oauth','client_id':True,'client_secret':True,'google':True,
  'setup':'In Google Cloud, enable the Drive MCP API and use an OAuth client set up like the Gmail one.'},
 'google_calendar':{'label':'Google Calendar','about':'Read and create calendar events.','url':'https://calendarmcp.googleapis.com/mcp/v1','auth':'oauth','client_id':True,'client_secret':True,'google':True,
  'setup':'In Google Cloud, enable the Calendar MCP API and use an OAuth client set up like the Gmail one.'},
}
SIGN_IN_TIMEOUT=300
PENDING={}

def redirect_uri():
    return f"http://127.0.0.1:{os.environ.get('STUDIO_PORT','3210')}/oauth/callback"

def _secret_path(name):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,30}',name):raise ValueError('Invalid integration name')
    folder=DATA/'integrations';folder.mkdir(parents=True,exist_ok=True)
    return folder/(name+'.secret')

def read_secrets(name):
    path=_secret_path(name)
    if not path.is_file():return {}
    raw=path.read_bytes()
    try:
        import win32crypt
        raw=win32crypt.CryptUnprotectData(raw,None,None,None,1)[1]
    except ImportError:pass
    except Exception:return {}
    return json.loads(raw.decode())

def write_secrets(name,values):
    raw=json.dumps(values).encode()
    try:
        import win32crypt
        raw=win32crypt.CryptProtectData(raw,'Luminaria integration '+name,None,None,None,1)
    except ImportError:pass
    path=_secret_path(name);tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);os.replace(tmp,path)

def forget(name):
    _secret_path(name).unlink(missing_ok=True)

class SecretStorage:
    """MCP TokenStorage backed by the integration's encrypted secret file."""
    def __init__(self,name):self.name=name
    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        data=read_secrets(self.name).get('tokens');return OAuthToken.model_validate(data) if data else None
    async def set_tokens(self,tokens):
        values=read_secrets(self.name);values['tokens']=tokens.model_dump(mode='json',exclude_none=True);write_secrets(self.name,values)
    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        values=read_secrets(self.name)
        if values.get('client'):return OAuthClientInformationFull.model_validate(values['client'])
        if values.get('client_id'):
            info={'client_id':values['client_id'],'redirect_uris':[redirect_uri()],'token_endpoint_auth_method':'client_secret_post' if values.get('client_secret') else 'none'}
            if values.get('client_secret'):info['client_secret']=values['client_secret']
            return OAuthClientInformationFull.model_validate(info)
        return None
    async def set_client_info(self,info):
        values=read_secrets(self.name);values['client']=info.model_dump(mode='json',exclude_none=True);write_secrets(self.name,values)

def complete(query):
    """Deliver a browser redirect to the waiting sign-in. Returns a short message for the tab."""
    params=parse_qs(query);state=(params.get('state') or [''])[0]
    future=PENDING.pop(state,None)
    if not future or future.done():return False,'This sign-in link has expired. Start the connection again in Luminaria.'
    if params.get('error'):
        future.set_exception(PermissionError('Sign-in was cancelled or denied: '+params['error'][0][:100]));return False,'Sign-in was cancelled. You can close this tab.'
    future.set_result(((params.get('code') or [''])[0],state,(params.get('iss') or [None])[0]));return True,'Signed in. You can close this tab and return to Luminaria.'

def oauth_provider(connector):
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import AuthorizationCodeResult,OAuthClientMetadata
    waiting={}
    async def redirect(url):
        state=(parse_qs(urlparse(url).query).get('state') or [''])[0]
        waiting['future']=PENDING[state]=asyncio.get_running_loop().create_future()
        connector.status='waiting for browser sign-in';connector.changed()
        if not await asyncio.to_thread(webbrowser.open,url):connector.status='open this link to sign in: '+url[:500];connector.changed()
    async def callback():
        try:code,state,issuer=await asyncio.wait_for(waiting['future'],SIGN_IN_TIMEOUT)
        except asyncio.TimeoutError:raise PermissionError('Sign-in timed out after 5 minutes')
        return AuthorizationCodeResult(code=code,state=state,iss=issuer)
    metadata=OAuthClientMetadata(client_name='Luminaria',redirect_uris=[redirect_uri()],grant_types=['authorization_code','refresh_token'],response_types=['code'],
                                 token_endpoint_auth_method='none')
    return OAuthClientProvider(connector.config['url'],metadata,SecretStorage(connector.name),redirect,callback)

@asynccontextmanager
async def transport(connector):
    from mcp.client.streamable_http import create_mcp_http_client,streamable_http_client
    headers,auth={},None
    if connector.config.get('auth')=='token':
        token=read_secrets(connector.name).get('token')
        if not token:raise PermissionError('No access token saved for this integration')
        headers['Authorization']='Bearer '+token
    elif connector.config.get('auth')=='oauth':auth=oauth_provider(connector)
    async with create_mcp_http_client(headers=headers,auth=auth) as client:
        async with streamable_http_client(connector.config['url'],http_client=client) as (read,write):
            yield read,write

def config_for(name,body):
    preset=PRESETS.get(name)
    if not preset:raise ValueError('Unknown integration')
    readonly=bool(body.get('readonly')) and 'readonly_url' in preset
    values={}
    if preset['auth']=='token':
        token=str(body.get('token','')).strip()
        if not token:
            token=read_secrets(name).get('token','')
            if not token:raise ValueError(preset['token_label']+' is required')
        if len(token)>500 or re.search(r'\s',token):raise ValueError('That token does not look valid')
        values['token']=token
    if preset.get('client_id'):
        client_id=str(body.get('client_id','')).strip()
        if not re.fullmatch(r'[A-Za-z0-9._\-]{6,200}',client_id):raise ValueError('Paste the OAuth client ID')
        values['client_id']=client_id
    if preset.get('client_secret'):
        secret=str(body.get('client_secret','')).strip() or read_secrets(name).get('client_secret','')
        if not secret or len(secret)>300:raise ValueError('Paste the OAuth client secret')
        values['client_secret']=secret
    previous=read_secrets(name)
    if previous.get('client_id')==values.get('client_id') and previous.get('url')==(preset['readonly_url'] if readonly else preset['url']):
        values.update({k:previous[k] for k in ('tokens','client') if k in previous})
    url=preset['readonly_url'] if readonly else preset['url'];values['url']=url
    return {'url':url,'auth':preset['auth'],'preset':name,'readonly':readonly},values

def catalog(configs,connectors):
    rows=[]
    for name,preset in PRESETS.items():
        config=configs.get(name) or {};connector=connectors.get(name);saved=read_secrets(name)
        rows.append({'saved_token':bool(saved.get('token')),'saved_client_secret':bool(saved.get('client_secret')),'client_id':saved.get('client_id',''),'id':name,'label':preset['label'],'about':preset['about'],'auth':preset['auth'],'setup':preset['setup'],'token_label':preset.get('token_label'),
                     'needs_client_id':bool(preset.get('client_id')),'needs_client_secret':bool(preset.get('client_secret')),'can_readonly':'readonly_url' in preset,
                     'configured':bool(config.get('url')),'readonly':bool(config.get('readonly')),'status':connector.status if connector else 'not connected',
                     'tools':len(connector.tools) if connector else 0,'connected':bool(connector) and connector.status=='connected'})
    from .config import external_tools_enabled
    return {'integrations':rows,'redirect_uri':redirect_uri(),'tools_enabled':external_tools_enabled()}
