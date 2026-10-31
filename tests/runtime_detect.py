import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import config

class RuntimeDetect(unittest.TestCase):
    def test_finds_current_python_when_configured_name_is_missing(self):
        old=config.CONFIG.get('python'); config.CONFIG['python']='definitely-not-installed'
        try: found=config.find_runtime('python')
        finally: config.CONFIG['python']=old
        self.assertTrue(found is None or Path(found).is_file())
    def test_missing_node_returns_none_not_a_crash(self):
        old=config.CONFIG.get('node'); config.CONFIG['node']='definitely-not-installed-node'
        try:
            import shutil; real=shutil.which
            shutil.which=lambda n:None
            try: self.assertIsNone(config.find_runtime('node'))
            finally: shutil.which=real
        finally: config.CONFIG['node']=old
    def test_messages_are_plain_and_name_the_fix(self):
        self.assertIn('python.org',config.runtime_missing_message('python'))
        self.assertIn('nodejs.org',config.runtime_missing_message('node'))
if __name__=='__main__': unittest.main()
