import asyncio,os,tempfile,unittest
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend.engine import Engine

class Fake:
    def __init__(self): self.added=[]
    def add(self,chat,payload): self.added.append((chat,payload)); return len(self.added)

class Steering(unittest.TestCase):
    def engine(self):
        e=Engine.__new__(Engine); e.steering={}; e.tasks={}; e.store=Fake(); e.events=[]; e.broadcast=lambda m:e.events.append(m)
        return e
    def test_steer_needs_a_running_task(self):
        e=self.engine()
        with self.assertRaises(ValueError): e.steer('c','hi')
    def test_steer_queues_and_limits(self):
        async def go():
            e=self.engine(); e.tasks['c']=asyncio.ensure_future(asyncio.sleep(5))
            with self.assertRaises(ValueError): e.steer('c','   ')
            for i in range(5): self.assertEqual(e.steer('c',f'm{i}'),i+1)
            with self.assertRaises(ValueError): e.steer('c','one too many')
            self.assertEqual(e.steering['c'][0],'m0'); self.assertEqual(e.store.added,[],'nothing enters the chat until a round boundary')
            e.tasks['c'].cancel()
        asyncio.run(go())

if __name__=='__main__':unittest.main()
