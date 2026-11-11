import os,tempfile,unittest
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend.engine import Engine

class Presets(unittest.TestCase):
    def preset(self,run,text='hello'):
        e=Engine.__new__(Engine); return e.preset(run,[{'role':'user','content':text}])
    def test_presets(self):
        self.assertEqual(self.preset(None),0.4)
        self.assertEqual(self.preset({'routing':{'profile':{'needs':['coding']}}}),0.2)
        self.assertEqual(self.preset({'routing':{'profile':{'needs':['writing']}}}),0.7)
        self.assertEqual(self.preset({'routing':{'profile':{'needs':['reasoning']}}}),0.3)
        self.assertEqual(self.preset({'step_id':'s1','routing':{'profile':{'needs':['writing']}}}),0.2,'plan steps stay steady')
        self.assertEqual(self.preset({},'thanks!'),0.4)
        run={}; self.preset(run,'fix this python traceback in my function and run the tests'); self.assertEqual(run['preset'],'coding')

if __name__=='__main__':unittest.main()
