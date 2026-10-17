import asyncio,unittest
from contextlib import asynccontextmanager
from unittest.mock import patch
from types import SimpleNamespace
from backend.connectors import Connector

class ConnectorCancellationTests(unittest.IsolatedAsyncioTestCase):
 async def test_capability_changes_refresh_and_failed_access_clears_readiness(self):
  holder={};refreshed=asyncio.Event();calls=0
  class Tool:
   def __init__(self,name):self.name=name
   def model_dump(self,**kw):return {'name':self.name,'inputSchema':{'type':'object'}}
  class Session:
   async def initialize(self):pass
   async def list_tools(self):
    nonlocal calls
    calls+=1
    if calls>1:refreshed.set()
    return SimpleNamespace(tools=[Tool('old' if calls==1 else 'new')])
   async def call_tool(self,*args,**kw):raise PermissionError('fixture expired access')
  @asynccontextmanager
  async def transport():yield None,None
  @asynccontextmanager
  async def session(*args,**kw):holder['notify']=kw['message_handler'];yield Session()
  connector=Connector('test',{})
  with patch.object(connector,'transport',transport),patch('backend.connectors.ClientSession',session):
   connector.start();await connector.ready.wait();self.assertEqual(connector.tools[0]['name'],'old')
   await holder['notify'](SimpleNamespace(root=SimpleNamespace(method='notifications/tools/list_changed')))
   self.assertEqual(connector.tools,[]);await asyncio.wait_for(refreshed.wait(),2)
   self.assertEqual(connector.tools[0]['name'],'new')
   with self.assertRaises(RuntimeError):await connector.call('new',{})
   await connector.task;self.assertNotEqual(connector.status,'connected');self.assertEqual(connector.tools,[])
 async def test_cancel_reaches_inflight_call_and_connector_remains_usable(self):
  started=asyncio.Event();cancelled=asyncio.Event()
  class Result:
   tools=[]
   def model_dump(self,**kwargs):return {'content':[{'type':'text','text':'done'}]}
  class Session:
   async def __aenter__(self):return self
   async def __aexit__(self,*args):pass
   async def initialize(self):pass
   async def list_tools(self):return Result()
   async def call_tool(self,name,args,**kwargs):
    if name=='slow':
     started.set()
     try:await asyncio.Event().wait()
     except asyncio.CancelledError:cancelled.set();raise
    return Result()
  @asynccontextmanager
  async def transport():yield None,None
  connector=Connector('test',{})
  with patch.object(connector,'transport',transport),patch('backend.connectors.ClientSession',lambda *a,**kw:Session()):
   connector.start();await connector.ready.wait()
   task=asyncio.create_task(connector.call('slow',{}));await asyncio.wait_for(started.wait(),2)
   task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
   await asyncio.wait_for(cancelled.wait(),2)
   self.assertEqual((await connector.call('read',{}))['content'][0]['text'],'done')
   await connector.close()
