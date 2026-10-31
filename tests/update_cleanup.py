import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import updates

class Cleanup(unittest.TestCase):
    def test_removes_installed_and_older_keeps_newer_and_logs(self):
        folder=updates.DATA/'updates'; folder.mkdir(exist_ok=True)
        old=updates.CONFIG['version']; updates.CONFIG['version']='0.2.48'
        names=['Luminaria-0.2.47-Setup.exe','Luminaria-0.2.48-Setup.exe','Luminaria-0.2.49-Setup.exe','Luminaria-0.2.49-Setup.exe.partial','update-handoff.ps1','setup.log','handoff.log','notes.txt']
        for n in names:(folder/n).write_text('x')
        try: removed=updates.cleanup()
        finally: updates.CONFIG['version']=old
        left=sorted(p.name for p in folder.iterdir())
        self.assertEqual(left,['Luminaria-0.2.49-Setup.exe','handoff.log','notes.txt','setup.log'])
        self.assertEqual(len(removed),4)
if __name__=='__main__': unittest.main()
