import asyncio,sys,unittest
from unittest.mock import patch
from backend import tools
from backend.tools import with_hints, python_shims, Toolbox

class CommandHints(unittest.TestCase):
    def test_missing_module_gets_a_next_step(self):
        r=with_hints({'exit_code':1,'stderr':"ModuleNotFoundError: No module named 'cv2'"})
        self.assertIn('pip install opencv-python',r['guidance'])
        r=with_hints({'exit_code':1,'stderr':"ModuleNotFoundError: No module named 'python_docx'"})
        self.assertIn('from docx import Document',r['guidance'])
        self.assertNotIn('guidance',with_hints({'exit_code':0,'stderr':''}))
    def test_pip_and_python_use_the_run_code_python(self):
        with patch.object(tools,'find_runtime',lambda k:"C:\\Lumi's\\python.exe"):
            s=python_shims()
        self.assertIn("function pip { & 'C:\\Lumi''s\\python.exe' -m pip @args }",s)
        with patch.object(tools,'find_runtime',lambda k:None): self.assertEqual(python_shims(),'')
    def test_timeout_is_reported_plainly(self):
        r=asyncio.run(Toolbox(None,{}).process([sys.executable,'-c','import time;time.sleep(5)'],1))
        self.assertTrue(r['timed_out']);self.assertIn('Stopped after 1 seconds',r['error'])

if __name__=='__main__': unittest.main()
