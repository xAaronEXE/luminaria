"""Live prerequisite checklist; opening it never changes permissions or installs code."""
from pathlib import Path
from .config import CONFIG,APP_HOME,external_tools_enabled,find_runtime
from .skills import inventory,preflight

def checklist(name,connectors):
 row=preflight(name,connectors)
 requires=list(inventory()['skills'].get(name,{}).get('requires',[]))
 steps=[]
 if requires and 'execution' not in requires:requires.append('execution')
 for need in requires:
  if need=='execution':
   ready=external_tools_enabled()
   steps.append({'id':need,'title':'Allow computer and command tools','ready':ready,'action':'permissions',
    'description':'Open Tools & permissions, enable Computer and command tools, then Save permissions. You can keep Review actions: Full access is not required. Changing access mode requires restart; enabling this switch does not.'})
  elif need=='github':
   connector=connectors.get(need);ready=bool(connector and connector.status=='connected')
   steps.append({'id':need,'title':'Connect GitHub','ready':ready,'action':'github',
    'description':'Open the GitHub connection form, create a token with only the repository access you need, then connect. Signing in to your Luminaria account does not connect repositories.'})
  elif need in ('browser','windows'):
   connector=connectors.get(need);ready=bool(connector and connector.status=='connected')
   configured=bool(CONFIG.get('mcp',{}).get(need))
   steps.append({'id':need,'title':'Connect the browser' if need=='browser' else 'Connect Windows desktop tools','ready':ready,'action':'connector',
    'configured':configured,'status':connector.status if connector else 'Not configured',
    'description':'Start or reconnect this local connector, then check that its tools load. This does not grant website sign-ins or Windows permissions. Browser profiles may open a separate browser; desktop actions use your Windows account.'})
 if 'Readable working folder' in row['missing']:
  steps.append({'id':'workspace','title':'Choose an accessible working folder','ready':False,'action':'workspace',
   'description':'Browse to a folder you can read and write, then save it. Existing files are not moved.'})
 return {'name':name,'ready':row['available'],'state':row['state'],'reason':row['reason'],'steps':steps,
  'note':'Readiness checks declared dependencies and the working folder. It does not guarantee that every workflow will succeed. No software is downloaded and no permissions change when you open this guide.'}

def connector_config(name):
 if name not in ('browser','windows'):raise ValueError('Unsupported skill connector')
 existing=CONFIG.get('mcp',{}).get(name)
 if existing:return existing
 # Use only already-installed app-owned runtimes; never run an installer or package manager.
 home=APP_HOME.parent if APP_HOME.name.lower()=='app' else APP_HOME
 runtime=home/'runtime'/'local-ai'/'agent-tools'
 if name=='browser':
  script=runtime/'node_modules'/'@playwright'/'mcp'/'cli.js'
  node=Path(find_runtime('node') or '')
  if not script.is_file() or not node.is_file():raise ValueError('The bundled browser connector is missing. Open Integrations to configure an existing trusted MCP server; no software was installed.')
  from .config import DATA
  return {'command':str(node),'args':[str(script),'--browser','msedge','--user-data-dir',str(DATA/'browser-profile'),'--output-dir',str(DATA/'browser-output')],'cwd':CONFIG['workspace']}
 python=runtime/'python-env'/'Scripts'/'python.exe'
 module=runtime/'python-env'/'Lib'/'site-packages'/'windows_mcp'
 if not python.is_file() or not module.is_dir():raise ValueError('The bundled Windows connector is missing. Open Integrations to configure an existing trusted MCP server; no software was installed.')
 return {'command':str(python),'args':['-m','windows_mcp','serve','--transport','stdio'],'cwd':CONFIG['workspace']}
