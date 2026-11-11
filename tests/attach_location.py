import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import attachments,config,folder_picker

class AttachLocation(unittest.TestCase):
    def setUp(self):
        self.dir=Path(tempfile.mkdtemp()).resolve();self.work=self.dir/'work';self.work.mkdir();self.data=self.dir/'data';self.data.mkdir()
        self.elsewhere=self.dir/'elsewhere';self.elsewhere.mkdir()
        self.patches=[patch.dict(config.CONFIG,workspace=str(self.work)),patch.object(attachments,'DATA',self.data)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in self.patches:p.stop()
    def test_any_file_anywhere_is_attached_where_it_is(self):
        big=self.elsewhere/'Budget 2026.xlsx';big.write_bytes(b'PK\x03\x04'+b'\0'*5000)
        a=attachments.attach_location(big)
        self.assertEqual(a['location'],str(big));self.assertEqual(a['name'],'Budget 2026.xlsx')
        self.assertFalse(list(self.work.rglob('*.xlsx')),'nothing is copied')
        part=attachments.text_part(a['id'])['text']
        self.assertIn(str(big),part);self.assertIn('stays where it is',part);self.assertIn('.xlsx',part)
    def test_folder_is_attached_by_location_with_a_listing(self):
        (self.elsewhere/'Invoices').mkdir();(self.elsewhere/'Invoices'/'a.pdf').write_bytes(b'x'*10);(self.elsewhere/'Invoices'/'2025').mkdir()
        a=attachments.attach_location(self.elsewhere/'Invoices')
        part=attachments.text_part(a['id'])['text']
        self.assertIn('Attached folder',part);self.assertIn('2025/',part);self.assertIn('a.pdf',part)
        self.assertEqual(json.loads((self.data/'attachments'/(a['id']+'.json')).read_text())['kind'],'folder_location')
    def test_small_text_files_include_a_preview(self):
        f=self.elsewhere/'notes.md';f.write_text('# Plan\nShip it',encoding='utf-8')
        self.assertIn('Ship it',attachments.text_part(attachments.attach_location(f)['id'])['text'])
    def test_missing_and_protected_places_are_refused(self):
        with self.assertRaises(ValueError):attachments.attach_location(self.elsewhere/'gone.txt')
        with patch.object(config,'protected_roots',lambda:[self.elsewhere]):
            with self.assertRaises(PermissionError):attachments.attach_location(self.elsewhere)
    def test_browser_upload_of_any_type_is_kept_and_attached(self):
        a=attachments.save_any('..\\evil/Clip (1).mp4',b'\x00\x01video')
        saved=Path(a['location'])
        self.assertTrue(saved.is_file() and saved.parent==self.work/'Attachments');self.assertTrue(saved.name.endswith('Clip (1).mp4'))
        self.assertEqual(saved.read_bytes(),b'\x00\x01video')

class Picker(unittest.TestCase):
    def test_uses_the_app_window_dialog_and_falls_back(self):
        with patch.object(folder_picker,'_native',lambda kind,initial,multiple=False:[str(Path.home())]) as _:
            self.assertEqual(folder_picker.pick('C:/nowhere'),{'cancelled':False,'path':str(Path.home().resolve())})
        with patch.object(folder_picker,'_native',lambda *a,**k:[]):
            self.assertEqual(folder_picker.pick('.'),{'cancelled':True})
        with patch.object(folder_picker,'_native',lambda *a,**k:None),patch.object(folder_picker,'_tk',lambda kind,initial,multiple:[str(Path.home())]):
            self.assertEqual(folder_picker.choose('folder'),[str(Path.home().resolve())])
        def broken(*a,**k):raise RuntimeError('no window')
        with patch.object(folder_picker,'_native',broken),patch.object(folder_picker,'_tk',lambda kind,initial,multiple:[]):
            self.assertEqual(folder_picker.choose('file',multiple=True),[])

if __name__=='__main__':unittest.main()
