import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend import model_library,models,config

class BulkRemove(unittest.TestCase):
    def setUp(self):
        self.folder=Path(tempfile.mkdtemp())/'models';self.folder.mkdir()
        self.outside=Path(tempfile.mkdtemp())/'mine.gguf';self.outside.write_bytes(b'x'*10)
        for name in ('a.gguf','b.gguf'):(self.folder/name).write_bytes(b'x'*100)
        (self.folder/'a.gguf.sha256').write_text('h');(self.folder/'.partial').mkdir();(self.folder/'.partial'/'c.part').write_bytes(b'x'*5)
        self.registry=[{'id':'a','model_file':str(self.folder/'a.gguf')},{'id':'b','model_file':str(self.folder/'b.gguf')},{'id':'mine','model_file':str(self.outside)}]
        self.saved=None
    def test_remove_all_deletes_managed_models_keeps_outside_ones_and_clears_selection(self):
        stops=[]
        with patch.object(model_library,'models_folder',lambda:self.folder),patch.object(model_library,'load_state',lambda:None),\
             patch.object(models,'registry',lambda:self.registry),patch.object(models,'save',lambda r:setattr(self,'saved',r)),\
             patch('backend.runtime.stop_owned',lambda:stops.append(1)),patch.object(config,'save_config',lambda c:config.CONFIG.update(c)):
            config.CONFIG['model']='a';config.CONFIG['model_file']=str(self.folder/'a.gguf')
            with self.assertRaises(ValueError):model_library.remove_all(False)
            result=model_library.remove_all(True)
        self.assertEqual(result['removed'],2);self.assertEqual(stops,[1])
        self.assertFalse(any(self.folder.glob('*.gguf')));self.assertFalse(any((self.folder/'.partial').iterdir()))
        self.assertTrue(self.outside.is_file(),'models added from another folder stay on disk')
        self.assertEqual([m['id'] for m in self.saved],['mine'])
        self.assertEqual(config.CONFIG['model'],'');self.assertEqual(config.CONFIG['model_file'],'')

if __name__=='__main__':unittest.main()
