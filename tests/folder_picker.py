import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from backend.folder_picker import pick

class FolderPickerTests(unittest.TestCase):
 def test_selection_returns_existing_absolute_path_without_applying_it(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Mock();dialog=Mock(return_value=folder)
   tk=SimpleNamespace(Tk=Mock(return_value=root),filedialog=SimpleNamespace(askdirectory=dialog))
   with patch.dict('sys.modules',{'tkinter':tk}):result=pick(folder)
   self.assertEqual(result,{'cancelled':False,'path':str(Path(folder).resolve())})
   self.assertTrue(dialog.call_args.kwargs['mustexist']);root.destroy.assert_called_once()
 def test_cancellation_returns_no_path_and_releases_picker(self):
  root=Mock();tk=SimpleNamespace(Tk=Mock(return_value=root),filedialog=SimpleNamespace(askdirectory=Mock(return_value='')))
  with patch.dict('sys.modules',{'tkinter':tk}):
   self.assertEqual(pick('.'),{'cancelled':True})
   self.assertEqual(pick('.'),{'cancelled':True})
  self.assertEqual(root.destroy.call_count,2)

if __name__=='__main__':unittest.main()
