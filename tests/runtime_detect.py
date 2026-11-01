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
            import shutil; real=shutil.which; bundled=config.bundled_runtime
            shutil.which=lambda n:None; config.bundled_runtime=lambda kind:None
            empty=tempfile.mkdtemp()
            from unittest.mock import patch
            try:
                with patch.dict(os.environ,{'LOCALAPPDATA':empty,'ProgramFiles':empty,'ProgramFiles(x86)':empty}):
                    self.assertIsNone(config.find_runtime('node'))
            finally: shutil.which=real; config.bundled_runtime=bundled
        finally: config.CONFIG['node']=old
    def test_messages_are_plain_and_name_the_fix(self):
        self.assertIn('Reinstall',config.runtime_missing_message('python'))
        self.assertIn('Reinstall',config.runtime_missing_message('node'))
class Bundled(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp())
        (self.tmp/'python').mkdir(); (self.tmp/'python'/'python.exe').write_text('x')
        (self.tmp/'node').mkdir(); (self.tmp/'node'/'node.exe').write_text('x')
        (self.tmp/'python'/'Lib'/'site-packages'/'windows_mcp').mkdir(parents=True)
        (self.tmp/'node_modules'/'@playwright'/'mcp').mkdir(parents=True); (self.tmp/'node_modules'/'@playwright'/'mcp'/'cli.js').write_text('x')
        self.real=config.agent_tools_dir; config.agent_tools_dir=lambda:self.tmp
    def tearDown(self): config.agent_tools_dir=self.real
    def test_bundled_copies_win_over_whatever_is_on_the_pc(self):
        self.assertEqual(config.find_runtime('python'),str(self.tmp/'python'/'python.exe'))
        self.assertEqual(config.find_runtime('node'),str(self.tmp/'node'/'node.exe'))
    def test_bundled_folders_go_first_on_path(self):
        self.assertEqual(config.runtime_path_dirs()[0],str(self.tmp/'python'))
    def test_connectors_use_the_bundled_runtimes(self):
        from backend import skill_setup
        old=config.CONFIG.get('mcp'); config.CONFIG['mcp']={'browser':{'command':'C:/gone/node.exe'}}
        try:
            b=skill_setup.connector_config('browser'); w=skill_setup.connector_config('windows')
        finally: config.CONFIG['mcp']=old if old is not None else {}
        self.assertEqual(b['command'],str(self.tmp/'node'/'node.exe'))
        self.assertEqual(w['command'],str(self.tmp/'python'/'python.exe'))
        self.assertEqual(w['env'],{'ANONYMIZED_TELEMETRY':'false'})

if __name__=='__main__': unittest.main()
