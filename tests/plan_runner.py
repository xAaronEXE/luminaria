import asyncio,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.engine import Engine,CONFIG

class Store:
    def __init__(self,plan): self.s={'plan:c':plan}; self.msgs=[]
    def setting(self,k,d=None): return self.s.get(k,d)
    def set_setting(self,k,v): self.s[k]=v
    def add(self,chat,m): self.msgs.append({**m,'id':len(self.msgs)+1}); return len(self.msgs)
    def messages(self,chat,after=0): return [m for m in self.msgs if m['id']>after]

class PlanRunner(unittest.TestCase):
    def setUp(self):
        d=Path(tempfile.mkdtemp())
        def m(id,strengths,params='14B'):
            f=d/(id+'.gguf');f.write_bytes(b'x');return {'id':id,'name':id,'strengths':strengths,'parameters':params,'model_file':str(f)}
        self.models=[m('chat-writer',['Writing']),m('qwen25-coder-14b',['Coding','Tools']),m('qwen3-14b',['Reasoning','Tools','Writing'])]
        plan={'goal':'Ship a todo app','steps':[{'id':'s1','title':'Write the Python code for the todo list','status':'pending'},
                                                {'id':'s2','title':'Write a short README for users','status':'pending'}]}
        self.e=Engine.__new__(Engine);self.e.store=Store(plan);self.e.broadcast=lambda ev:None;self.calls=[]
        async def run_step(run,model,instruction,reasoning=False):
            self.calls.append((model['id'],instruction.split(']')[0]+']',reasoning))
            run['step_from']=self.e.store.add('c',{'role':'user','content':instruction})
            self.e.store.add('c',{'role':'assistant','content':'Did it. Saved in todo.py.'})
            return False
        self.e.run_step=run_step
    def test_steps_use_role_models_and_record_notes(self):
        with patch.dict(CONFIG,model='chat-writer',coder_model='auto',planner_model='auto'),patch('backend.orchestration.gpu_memory',lambda:16*2**30):
            paused=asyncio.run(self.e.run_plan({'chat':'c','id':'r'},self.models))
        self.assertFalse(paused)
        self.assertEqual([c[0] for c in self.calls],['qwen25-coder-14b','chat-writer','qwen3-14b'])
        self.assertTrue(self.calls[-1][1].startswith('[Final check]') and self.calls[-1][2])
        plan=self.e.store.setting('plan:c')
        self.assertEqual([s['status'] for s in plan['steps']],['done','done'])
        self.assertIn('todo.py',plan['steps'][0]['note'])
    def test_no_plan(self):
        e=Engine.__new__(Engine);e.store=Store(None)
        with self.assertRaises(ValueError): asyncio.run(e.run_plan({'chat':'c','id':'r'},self.models))

if __name__=='__main__': unittest.main()
