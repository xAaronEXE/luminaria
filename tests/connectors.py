import asyncio,unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch
from backend.connectors import Connector

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
 async def test_discovery_and_shutdown_notify_ui_and_clear_catalog(self):
  events=[]
  class Tool:
   def model_dump(self,**kwargs):return {'name':'fixture_tool'}
  class Session:
   async def initialize(self):pass
   async def list_tools(self):return SimpleNamespace(tools=[Tool()])
  @asynccontextmanager
  async def io(*args):yield (None,None)
  @asynccontextmanager
  async def session(*args):yield Session()
  with patch('backend.connectors.stdio_client',io),patch('backend.connectors.ClientSession',session):
   c=Connector('fixture',{'command':'unused'},events.append);c.start()
   await asyncio.wait_for(c.ready.wait(),2)
   self.assertEqual(c.status,'connected');self.assertEqual(len(c.tools),1)
   self.assertEqual(events,[{'type':'connectors_changed','connector':'fixture'}])
   await c.close();self.assertEqual(c.status,'stopped');self.assertEqual(c.tools,[])
   self.assertEqual(len(events),2)
 async def test_failed_connector_notifies_without_claiming_tools(self):
  events=[];c=Connector('missing',{},events.append);await c.worker()
  self.assertTrue(c.status.startswith('unavailable'));self.assertEqual(c.tools,[])
  self.assertEqual(len(events),1)
