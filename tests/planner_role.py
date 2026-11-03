import tempfile,unittest
from pathlib import Path
from backend.orchestration import pick_planner

class PlannerRole(unittest.TestCase):
    def setUp(self):
        d=Path(tempfile.mkdtemp())
        def m(id,params,strengths):
            f=d/(id+'.gguf');f.write_bytes(b'x');return {'id':id,'name':id,'parameters':params,'strengths':strengths,'model_file':str(f)}
        self.models=[m('qwen2-5-coder-3b',"3B",['Coding']),m('qwen3-14b-abliterated-q6','14B',['Reasoning','Tools','Writing']),
                     m('qwen3-8b','8B',['Reasoning','Tools']),m('qwen2-5-14b-uncensored','14B',['Writing'])]
    def test_strongest_reasoning_model_plans(self):
        self.assertEqual(pick_planner(self.models,'auto',vram=16*2**30)['id'],'qwen3-14b-abliterated-q6')
    def test_user_choice_and_off(self):
        self.assertEqual(pick_planner(self.models,'qwen3-8b')['id'],'qwen3-8b')
        self.assertIsNone(pick_planner(self.models,'chat'))
        self.assertIsNone(pick_planner([self.models[0]],'auto',vram=16*2**30))

if __name__=='__main__': unittest.main()
