"""Live prerequisite checklist; opening it never changes permissions or installs code."""
from pathlib import Path
from .config import CONFIG,external_tools_enabled,agent_tools_dir,bundled_runtime
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
    'description':'Open Tools & permissions, enable Computer and command tools, then Save permissions. You can keep Ask me first: Full access is not required.'})
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
 if 'Readable default folder' in row['missing']:
  steps.append({'id':'workspace','title':'Choose an accessible default folder','ready':False,'action':'workspace',
   'description':'Browse to a folder you can read and write, then save it. Existing files are not moved.'})
 return {'name':name,'ready':row['available'],'state':row['state'],'reason':row['reason'],'steps':steps,
  'note':'Readiness checks declared dependencies and the default folder. It does not guarantee that every workflow will succeed. No software is downloaded and no permissions change when you open this guide.'}

def connector_config(name):
 if name not in ('browser','windows'):raise ValueError('Unsupported skill connector')
 existing=CONFIG.get('mcp',{}).get(name)
 # Keep a connector the user set up, unless it points at a program file that no longer exists
 # (for example the old tools folder from a previous version). Bare names like npx are found on PATH.
 command=str((existing or {}).get('command',''))
 if existing and command and (not any(sep in command for sep in '/\\') or Path(command).is_file()):return existing
 # Use only the runtimes that ship with Luminaria; never run an installer or package manager.
 tools=agent_tools_dir()
 from .config import DATA
 if name=='browser':
  script=tools/'node_modules'/'@playwright'/'mcp'/'cli.js' if tools else None
  node=bundled_runtime('node')
  if not script or not script.is_file() or not node:raise ValueError('The built-in browser connector is missing. Reinstall Luminaria to restore it; nothing was installed.')
  return {'command':node,'args':[str(script),'--browser','msedge','--user-data-dir',str(DATA/'browser-profile'),'--output-dir',str(DATA/'browser-output')],'cwd':CONFIG['workspace']}
 python=bundled_runtime('python')
 module=tools/'python'/'Lib'/'site-packages'/'windows_mcp' if tools else None
 if not python or not module or not module.is_dir():raise ValueError('The built-in Windows connector is missing. Reinstall Luminaria to restore it; nothing was installed.')
 return {'command':python,'args':['-m','windows_mcp','serve','--transport','stdio'],'cwd':CONFIG['workspace'],'env':{'ANONYMIZED_TELEMETRY':'false'}}
