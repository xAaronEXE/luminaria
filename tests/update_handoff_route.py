import os,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
from backend import app as api,updates,lifecycle
from fastapi import BackgroundTasks,HTTPException

def tearDownModule():
 api.store.db.close();FOLDER.cleanup()

class HandoffRouteTests(unittest.IsolatedAsyncioTestCase):
 async def test_active_work_prevents_install(self):
  with patch.object(api,'engine',SimpleNamespace(runs={'chat':{'finished':False}})),patch.object(updates,'install',new_callable=AsyncMock) as install:
   with self.assertRaises(HTTPException) as error:await api.update_install(BackgroundTasks())
   self.assertEqual(error.exception.status_code,409);install.assert_not_awaited()
 async def test_shutdown_runs_after_response_background(self):
  tasks=BackgroundTasks()
  with patch.object(api,'engine',SimpleNamespace(runs={})),patch.object(updates,'install',new_callable=AsyncMock,return_value={'closing':True}),patch.object(lifecycle,'request_shutdown') as close:
   result=await api.update_install(tasks)
   self.assertTrue(result['closing']);close.assert_not_called()
   await tasks();close.assert_called_once_with()
 async def test_development_launch_does_not_close_host(self):
  tasks=BackgroundTasks()
  with patch.object(api,'engine',SimpleNamespace(runs={})),patch.object(updates,'install',new_callable=AsyncMock,return_value={'closing':False}),patch.object(lifecycle,'request_shutdown') as close:
   await api.update_install(tasks);await tasks();close.assert_not_called()
