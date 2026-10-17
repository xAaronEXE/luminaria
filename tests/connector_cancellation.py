import asyncio,unittest
from contextlib import asynccontextmanager
from unittest.mock import patch
from backend.connectors import Connector

class ConnectorCancellationTests(unittest.IsolatedAsyncioTestCase):
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
  with patch.object(connector,'transport',transport),patch('backend.connectors.ClientSession',lambda *a:Session()):
   connector.start();await connector.ready.wait()
   task=asyncio.create_task(connector.call('slow',{}));await asyncio.wait_for(started.wait(),2)
   task.cancel()
   with self.assertRaises(asyncio.CancelledError):await task
   await asyncio.wait_for(cancelled.wait(),2)
   self.assertEqual((await connector.call('read',{}))['content'][0]['text'],'done')
   await connector.close()
