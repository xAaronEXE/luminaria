import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import models

class ModelStorageTests(unittest.TestCase):
    def test_actual_volume_counts_duplicate_weights_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'data'; data.mkdir()
            weights=root/'weights.gguf'; weights.write_bytes(b'weights')
            projector=root/'vision.gguf'; projector.write_bytes(b'vision')
            with patch.object(models,'BASE_DATA',data):
                result=models.model_storage([
                    {'model_file':str(weights),'projector_file':str(projector)},
                    {'model_file':str(weights)}, {'model_file':str(root/'missing.gguf')}])
            self.assertEqual(result['model_bytes'],13)
            self.assertEqual(result['path'],str(root/'models'))
            self.assertGreater(result['total'],0)
            self.assertGreater(result['total'],0)
            self.assertGreaterEqual(result['used'],0)
            self.assertGreaterEqual(result['free'],0)
    def test_empty_registry_reports_disk_without_creating_model_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(models,'BASE_DATA',root/'data'):
                result=models.model_storage([])
            self.assertEqual(result['model_bytes'],0)
            self.assertFalse((root/'models').exists())

if __name__=='__main__': unittest.main()
