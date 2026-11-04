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

class Selected(unittest.TestCase):
    def lib(self):
        q=lambda key,rating,installed=False,size=100:{'id':key+'-q','best_fit':True,'installed':installed,'downloadable':True,'bytes':size,'fit':{'rating':rating}}
        return {'models':[{'key':'a','name':'A','quants':[q('a','recommended')]},{'key':'b','name':'B','quants':[q('b','unstable')]},
                          {'key':'c','name':'C','quants':[q('c','too_large')]},{'key':'d','name':'D','quants':[q('d','recommended',True)]},
                          {'key':'e','name':'E','quants':[q('e','good')]}],'budget':{'remaining':10**12}}
    def test_download_selected_only_queues_chosen_models_that_fit(self):
        queued=[]
        with patch.object(model_library,'library',lambda store:self.lib()),patch.object(model_library,'enqueue',queued.append),\
             patch.object(model_library,'models_folder',lambda:Path(tempfile.gettempdir())):
            plan=model_library.download_all(None,False,['a','b','c','d'])
            done=model_library.download_all(None,True,['a','b','c','d'])
        self.assertEqual(plan['count'],2,'installed and too-large models are left out; an unstable one the user chose is kept')
        self.assertEqual(sorted(queued),['a-q','b-q']);self.assertEqual(done['queued'],2)
    def test_download_all_without_keys_keeps_good_fits_only(self):
        with patch.object(model_library,'library',lambda store:self.lib()),patch.object(model_library,'models_folder',lambda:Path(tempfile.gettempdir())):
            self.assertEqual(model_library.download_all(None,False)['count'],2)   # a and e
    def test_remove_selected_continues_after_a_failure(self):
        calls=[]
        def remove(ident,confirm):
            calls.append(ident)
            if ident=='bad':raise ValueError('Model not found')
        with patch.object(model_library,'remove',remove):
            with self.assertRaises(ValueError):model_library.remove_selected(['x'],False)
            result=model_library.remove_selected(['x','bad','y','x'],True)
        self.assertEqual(calls,['x','bad','y']);self.assertEqual(result['removed'],2);self.assertEqual(len(result['failed']),1)

if __name__=='__main__':unittest.main()
