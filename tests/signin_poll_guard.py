import ast,asyncio,tempfile,os,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
FOLDER=tempfile.TemporaryDirectory();os.environ['STUDIO_DATA']=FOLDER.name
from backend import identity
source=ast.parse((Path(__file__).resolve().parents[1]/'backend/app.py').read_text(encoding='utf-8'))
node=next(n for n in source.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='identity_poll');node.decorator_list=[]
class GuardTests(unittest.IsolatedAsyncioTestCase):
 async def call(self,entry,runs):
  request=SimpleNamespace(json=AsyncMock(return_value={'flow_id':'flow'}));engine=SimpleNamespace(runs=runs)
  async def identity_call(op):return await op
  context={'__name__':'backend.app','__package__':'backend','Request':object,'BackgroundTasks':object,'engine':engine,'identity_call':identity_call}
  exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_identity_poll','exec'),context)
  with patch.object(identity,'pending',{'flow':entry}),patch.object(identity,'poll',AsyncMock(return_value={'status':'complete'})) as poll:
   result=await context['identity_poll'](request,SimpleNamespace());poll.assert_awaited_once_with('flow');return result
 async def test_linking_is_allowed_during_task(self):await self.call({'enter_workspace':False},{'chat':{'finished':False}})
 async def test_workspace_entry_blocks_running_task(self):
  with self.assertRaisesRegex(ValueError,'active tasks'):await self.call({'enter_workspace':True},{'chat':{'finished':False}})
 async def test_interrupted_task_does_not_block_entry(self):await self.call({'enter_workspace':True},{'chat':{'finished':False,'resume_available':True}})
if __name__=='__main__':unittest.main()
