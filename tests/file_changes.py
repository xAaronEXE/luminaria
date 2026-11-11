import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend import changes,config
from backend.store import Store

class Changes(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory(); self.root=Path(self.dir.name)
        self.store=Store(self.root/'s.sqlite3'); self.data=self.root/'data'
        self.run={'id':'r1','chat':'c1','step_id':'s1'}
    def tearDown(self):
        try: self.store.db.close()
        except Exception: pass
        self.dir.cleanup()
    def change(self,path,text=None,run=None):
        run=run or self.run
        changes.before(self.store,self.data,run,path)
        if text is None: Path(path).unlink()
        else: changes.atomic_write(path,text)
        changes.after(self.store,run,path)

    def test_atomic_write_replaces_whole_file_and_leaves_no_temp(self):
        f=self.root/'a.txt'; f.write_text('old')
        changes.atomic_write(f,'new content')
        self.assertEqual(f.read_text(),'new content')
        self.assertEqual([p.name for p in self.root.iterdir() if 'luminaria-tmp' in p.name],[])

    def test_failed_write_keeps_the_original(self):
        f=self.root/'a.txt'; f.write_text('original')
        with patch('os.replace',side_effect=OSError('disk')):
            with self.assertRaises(OSError): changes.atomic_write(f,'half')
        self.assertEqual(f.read_text(),'original')
        self.assertEqual([p.name for p in self.root.iterdir() if 'luminaria-tmp' in p.name],[])

    def test_locked_file_is_retried(self):
        f=self.root/'a.txt'; f.write_text('x'); real=os.replace; calls=[]
        def flaky(a,b):
            calls.append(1)
            if len(calls)<3: raise PermissionError('in use')
            return real(a,b)
        with patch('os.replace',flaky),patch('time.sleep'): changes.atomic_write(f,'y')
        self.assertEqual(f.read_text(),'y')

    def test_undo_restores_changed_removes_created_and_brings_back_deleted(self):
        changed=self.root/'changed.txt'; changed.write_text('v1'); created=self.root/'new.txt'; deleted=self.root/'gone.txt'; deleted.write_text('keep me')
        self.change(changed,'v2'); self.change(changed,'v3'); self.change(created,'hello'); self.change(deleted)
        s=changes.summary(self.store,'c1')
        self.assertEqual({f['path']:f['action'] for f in s['files']},{str(changed):'changed',str(created):'created',str(deleted):'deleted'})
        self.assertEqual(s['undoable'],3)
        result=changes.undo(self.store,self.data,'c1')
        self.assertEqual(changed.read_text(),'v1','restored to before the task, not the middle edit')
        self.assertFalse(created.exists()); self.assertEqual(deleted.read_text(),'keep me')
        self.assertEqual(len(result['restored']),3)
        self.assertEqual(len(list((self.data/'undo-trash').rglob('*new.txt'))),1,'a created file is moved aside, not destroyed')
        self.assertEqual(changes.summary(self.store,'c1')['files'],[],'nothing is undone twice')

    def test_file_changed_afterwards_is_a_conflict_and_left_alone(self):
        f=self.root/'a.txt'; f.write_text('v1'); self.change(f,'v2'); f.write_text('the user edited this')
        self.assertEqual(changes.summary(self.store,'c1')['files'][0]['undo'],'conflict')
        result=changes.undo(self.store,self.data,'c1')
        self.assertEqual(f.read_text(),'the user edited this'); self.assertEqual(result['conflicts'],[str(f)]); self.assertEqual(result['restored'],[])

    def test_only_the_latest_task_is_undone_by_default(self):
        a=self.root/'a.txt'; a.write_text('a1'); b=self.root/'b.txt'; b.write_text('b1')
        self.change(a,'a2'); self.change(b,'b2',{'id':'r2','chat':'c1'})
        changes.undo(self.store,self.data,'c1')
        self.assertEqual((a.read_text(),b.read_text()),('a2','b1'))

    def test_large_file_is_not_promised(self):
        f=self.root/'big.bin'; f.write_text('x'*100)
        with patch.object(changes,'SNAPSHOT_LIMIT',10): self.change(f,'y')
        self.assertEqual(changes.summary(self.store,'c1')['files'][0]['undo'],'too_large')
        self.assertEqual(changes.undo(self.store,self.data,'c1')['skipped'],[str(f)])

    def test_commands_are_listed_as_not_undoable(self):
        f=self.root/'a.txt'; self.change(f,'x')
        import time
        self.store.execute("INSERT INTO actions(id,chat,name,args,tier,status,result,created) VALUES('x1','c1','run_command','{}','auto','done',NULL,?)",(time.time()+1,))
        self.assertEqual(changes.summary(self.store,'c1')['cannot_undo'],[{'what':'A command it ran','count':1}])

class Guards(unittest.TestCase):
    def test_command_guard(self):
        env={'WINDIR':'C:\\Windows','SystemRoot':'C:\\Windows'}
        with patch.dict(os.environ,env):
            for bad in ('Get-Content $env:WINDIR\\win.ini','type C:/Windows/System32/drivers/etc/hosts','del C:\\Windows\\notepad.exe','cat ~/.ssh/id_rsa',
                        'Start-Process cmd -Verb RunAs','runas /user:Administrator cmd','cmdkey /list','dir "%APPDATA%\\Microsoft\\Credentials"'):
                with self.subTest(bad=bad):
                    with self.assertRaises(PermissionError): config.command_guard(bad)
            for fine in ('python build.py','pip install requests','dir C:\\Users\\me\\Documents','Get-ChildItem "C:\\Program Files\\Git"','npm test','echo windowsill'):
                with self.subTest(fine=fine): config.command_guard(fine)

    def test_program_files_always_asks_but_is_not_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            pf=Path(d)/'Program Files'; pf.mkdir()
            with patch.dict(os.environ,{'PROGRAMFILES':str(pf)}):
                self.assertTrue(config.always_ask('write_file',{'path':str(pf/'App'/'config.ini')}))
                self.assertTrue(config.always_ask('delete_file',{'path':str(pf/'x.txt')}))
                self.assertFalse(config.always_ask('read_file',{'path':str(pf/'x.txt')}))
                self.assertFalse(config.always_ask('write_file',{'path':str(Path(d)/'elsewhere.txt')}))
                self.assertNotIn(pf.resolve(),config.protected_roots())

    def test_system_housekeeping_folders_are_off_limits(self):
        self.assertTrue(config.system_area(Path('/$Recycle.Bin/x')))
        self.assertTrue(config.system_area(Path('/System Volume Information/a')))
        self.assertFalse(config.system_area(Path('/Projects/Recovery notes/a.txt')))


class Drives(unittest.TestCase):
    def test_unticked_drive_is_refused_and_required_drives_stay(self):
        from pathlib import PureWindowsPath
        with patch.object(config,'drive_of',lambda p:(PureWindowsPath(str(p)).drive or 'C:').upper()):
            with patch.dict(config.CONFIG,{'drives':['D:'],'workspace':'C:\\Luminaria\\Files'}),patch.object(config,'DATA',Path('C:/Luminaria/data')):
                self.assertEqual(config.allowed_drives(),{'D:','C:'},'the drive holding Luminaria always stays on')
            with patch.dict(config.CONFIG,{'drives':'all'}): self.assertIsNone(config.allowed_drives())
    def test_workspace_path_refuses_a_drive_that_is_off(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(config.CONFIG,{'workspace':d}),patch.object(config,'allowed_drives',lambda:{'Z:'}):
                with self.assertRaises(PermissionError): config.workspace_path('notes.txt',roam=True)

if __name__=='__main__':unittest.main()
