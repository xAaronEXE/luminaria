"""Each MCP lifecycle (local stdio or hosted HTTP) stays in its owning asyncio task (AnyIO scope rule)."""
import asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class Connector:
    def __init__(self,name,config,on_change=None):
        self.name=name; self.config=config; self.status='connecting'; self.tools=[]
        self.on_change=on_change
        self.queue=asyncio.Queue(); self.ready=asyncio.Event(); self.task=None
    def changed(self):
        if self.on_change:self.on_change({'type':'connectors_changed','connector':self.name})
    def start(self): self.task=asyncio.create_task(self.worker())
    def transport(self):
        if self.config.get('url'):
            from .integrations import transport
            return transport(self)
        p=StdioServerParameters(command=self.config['command'],args=self.config.get('args',[]),env={**os.environ,**self.config.get('env',{})},cwd=self.config.get('cwd'))
        return stdio_client(p)
    async def worker(self):
        try:
            async with self.transport() as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    result=await session.list_tools()
                    self.tools=[t.model_dump(by_alias=True) for t in result.tools]; self.status='connected'; self.ready.set()
                    self.changed()
                    while True:
                        item=await self.queue.get()
                        if item is None: return
                        name,args,future=item
                        if future.cancelled(): continue
                        try:
                            call=asyncio.create_task(session.call_tool(name,args,read_timeout_seconds=120))
                            def cancel_call(done,active=call):
                                if done.cancelled() and not active.done(): active.cancel()
                            future.add_done_callback(cancel_call)
                            try: result=await call
                            except asyncio.CancelledError:
                                if not future.cancelled(): raise
                                continue
                            finally:
                                future.remove_done_callback(cancel_call)
                                if not call.done():
                                    call.cancel()
                                    try: await call
                                    except asyncio.CancelledError: pass
                            if not future.done(): future.set_result(result.model_dump(by_alias=True))
                        except Exception as e:
                            if not future.done(): future.set_exception(RuntimeError(str(e)))
        except asyncio.CancelledError: raise
        except BaseException as e:
            while isinstance(e,BaseExceptionGroup) and e.exceptions: e=e.exceptions[0]
            self.status='unavailable: '+(str(e) or type(e).__name__)[:200]
        finally:
            if self.status=='connected':self.status='stopped'
            self.tools=[];self.changed()
            self.ready.set()
            while not self.queue.empty():
                item=self.queue.get_nowait()
                if item and not item[2].done(): item[2].set_exception(RuntimeError('Connector stopped'))
    async def call(self,name,args):
        await asyncio.wait_for(self.ready.wait(),25)
        if self.status!='connected': raise RuntimeError(self.status)
        future=asyncio.get_running_loop().create_future()
        await self.queue.put((name,args,future)); return await asyncio.wait_for(future,130)
    async def close(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except BaseException: pass
