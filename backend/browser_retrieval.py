"""Explicitly authorized fallback using the user's connected browser, never login automation."""
import json
from jsonschema import validate
from .sources import document

async def fetch(connector,url):
    if not connector or connector.status!='connected':
        return {'status':'error','category':'needs_setup','source':url,'message':'Connect a browser before requesting browser fallback.'}
    required={'browser_navigate':{'url':url},'browser_snapshot':{}}
    for name,args in required.items():
        tool=next((t for t in connector.tools if t['name']==name),None)
        if not tool:return {'status':'error','category':'unsupported','source':url,'message':'The browser does not expose the supported navigation and snapshot tools.'}
        validate(args,tool['inputSchema'])
    navigation=await connector.call('browser_navigate',{'url':url})
    if navigation.get('isError'):return {'status':'error','category':'browser_navigation','source':url,'message':'Browser navigation failed; no snapshot was used.'}
    result=await connector.call('browser_snapshot',{})
    if result.get('isError'):return {'status':'error','category':'browser_snapshot','source':url,'message':'The browser could not read the page. Complete any sign-in or permission dialog yourself.'}
    text='\n'.join(p.get('text','') for p in result.get('content',[]) if p.get('type')=='text').strip()
    if not text:return {'status':'empty','source':url,'message':'The browser returned no readable snapshot.'}
    return {**document(text,url,limit=24000),'representation':'browser_snapshot','retrieval_method':'authorized_browser_snapshot','cached':False,
            'note':'Snapshot from the connected browser after requested navigation. No login or access-control bypass was performed.'}
