import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class WorkspaceFallbackTests(unittest.TestCase):
 def test_file_in_place_of_working_folder_does_not_stop_startup(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'lumi').write_text('not a folder')
   (Path(d)/'config.json').write_text(json.dumps({'workspace':str(Path(d)/'lumi')}))
   code="from backend import config as c;import json;print(json.dumps([c.CONFIG['workspace'],c.WORKSPACE_PROBLEM]))"
   out=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'STUDIO_DATA':d},capture_output=True,text=True,check=True).stdout
   workspace,problem=json.loads(out.strip().splitlines()[-1])
   self.assertTrue(Path(workspace).is_dir());self.assertNotEqual(workspace,str(Path(d)/'lumi'))
   self.assertIn('could not be opened',problem)

if __name__=='__main__':unittest.main()
