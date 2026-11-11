import hashlib, shutil, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import model_library, models
from backend.model_catalog import CATALOG

class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

def serve(payload, delay=0, step=8):
    ranges = []
    class Handler(QuietHandler):
        def do_GET(self):
            data = payload
            start = 0
            status = 200
            header = self.headers.get('Range')
            if header:
                ranges.append(header)
                start = int(header.split('=', 1)[1].split('-', 1)[0])
                data = payload[start:]
                status = 206
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{len(payload) - 1}/{len(payload)}')
            self.end_headers()
            view = memoryview(data)
            try:
                for offset in range(0, len(view), step):
                    if delay: time.sleep(delay)
                    self.wfile.write(view[offset:offset + step])
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, ranges, f'http://127.0.0.1:{httpd.server_address[1]}/model.gguf'

def wait_until(predicate, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if predicate(): return
        time.sleep(0.02)
    raise AssertionError('timed out')

class ModelLibraryTests(unittest.TestCase):
    def setUp(self):
        model_library.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.patches = [
            patch.object(models, 'BASE_DATA', self.data),
            patch.object(models, 'PATH', self.data / 'models.json'),
        ]
        for item in self.patches: item.start()
    def tearDown(self):
        model_library.reset()
        for item in self.patches: item.stop()
        self.tmp.cleanup()
    def test_catalog_keeps_standard_and_abliterated_separate(self):
        self.assertTrue(any(item['variant'] == 'standard' for item in CATALOG))
        self.assertTrue(any(item['variant'] == 'abliterated' and item['caveat'] for item in CATALOG))
        view = model_library.library(None)
        self.assertIn('Qwen3 8B', [item['name'] for item in view['models']])
        self.assertEqual(view['budget']['limit'], 100 * 1024 ** 3)
        self.assertGreater(view['storage']['total'], 0)
        self.assertGreaterEqual(view['storage']['free'], 0)
        self.assertFalse((self.root / 'models').exists())
        folder = self.root / 'models'
        folder.mkdir()
        (folder / 'Qwen3-4B-Q4_K_M.gguf').write_bytes(b'installed')
        installed = model_library.library(None)
        standard = next(item for item in installed['models'] if item['id'] == 'qwen3-4b')
        quant = next(item for item in standard['quants'] if item['id'] == 'qwen3-4b-q4')
        self.assertEqual(standard['variant'], 'standard')
        self.assertTrue(quant['installed'])
        self.assertFalse(quant['verified'])
        self.assertTrue(all(item['caveat'] for item in installed['models'] if item['variant'] == 'abliterated'))
    def test_disk_and_budget_stop_before_any_download(self):
        with self.assertRaisesRegex(ValueError, 'Not enough free space'):
            model_library.check_room(100, 0, 50, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, 'download budget'):
            model_library.check_room(80, 0, 1 << 40, 40, 0, 0, budget=100)
    def test_adjustable_budget_persists_and_accounts_for_reservations(self):
        model_library.set_download_budget(200)
        self.assertEqual(model_library.library(None)['budget']['limit'], 200 * 1024**3)
        with patch.object(model_library, '_reservations', return_value=(60 * 1024**3, 0)), patch.object(model_library, '_catalog_spent', return_value=60 * 1024**3):
            with self.assertRaisesRegex(ValueError, 'active or queued'):
                model_library.set_download_budget(100)
        self.assertEqual(model_library.download_budget(), 200 * 1024**3)
    def test_redirect_host_must_stay_with_the_publisher(self):
        self.assertTrue(model_library.host_allowed('https://cdn-lfs.huggingface.co/file', 'https://huggingface.co/org/repo/resolve/main/file.gguf'))
        self.assertFalse(model_library.host_allowed('https://example.com/file', 'https://huggingface.co/org/repo/resolve/main/file.gguf'))
        self.assertTrue(model_library.host_allowed('http://127.0.0.1:9/file', 'http://127.0.0.1:9/file'))
    def test_published_file_must_match_the_catalog(self):
        entry, quant = model_library.quant_by_id('qwen3-4b-q4')
        def handler(request):
            return httpx.Response(302, headers={'x-linked-size': '10', 'x-linked-etag': '"' + quant['sha256'] + '"'})
        client = httpx.Client
        with patch.object(model_library.httpx, 'Client', lambda *args, **kwargs: client(transport=httpx.MockTransport(handler))):
            with self.assertRaisesRegex(ValueError, 'no longer matches'):
                model_library.resolve(entry, quant)
    def test_download_verifies_and_registers_inside_models_folder(self):
        payload = b'gguf-weights-for-test'
        digest = hashlib.sha256(payload).hexdigest()
        httpd, ranges, url = serve(payload)
        entry, quant = self.quant(digest, len(payload))
        try:
            self.patch_quant(entry, quant, url)
            model_library.enqueue(quant['id'])
            final = self.root / 'models' / quant['filename']
            wait_until(final.is_file)
            self.assertEqual(final.read_bytes(), payload)
            self.assertEqual((self.root / 'models' / (quant['filename'] + '.sha256')).read_text().strip(), digest)
            self.assertEqual(models.registry()[0]['id'], quant['id'])
            self.assertEqual(models.registry()[0]['variant'], 'abliterated')
            self.assertFalse(ranges)
        finally:
            httpd.shutdown(); httpd.server_close()
    def test_checksum_mismatch_deletes_the_partial_file(self):
        payload = b'not-the-catalog-bytes'
        digest = hashlib.sha256(b'the-real-bytes').hexdigest()
        httpd, _, url = serve(payload)
        entry, quant = self.quant(digest, len(payload))
        try:
            self.patch_quant(entry, quant, url)
            model_library.enqueue(quant['id'])
            wait_until(lambda: any(job['status'] == 'error' for job in model_library.jobs_view()))
            self.assertFalse((self.root / 'models' / quant['filename']).exists())
            self.assertFalse((self.root / 'models' / '.partial' / (quant['id'] + '.part')).exists())
            self.assertEqual(models.registry(), [])
            self.assertIn('Checksum mismatch', model_library.jobs_view()[0]['error'])
        finally:
            httpd.shutdown(); httpd.server_close()
    def test_resume_continues_from_the_partial_file(self):
        payload = b'0123456789abcdef'
        digest = hashlib.sha256(payload).hexdigest()
        httpd, ranges, url = serve(payload)
        entry, quant = self.quant(digest, len(payload))
        partial = self.root / 'models' / '.partial' / (quant['id'] + '.part')
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:6])
        try:
            self.patch_quant(entry, quant, url)
            model_library.enqueue(quant['id'])
            final = self.root / 'models' / quant['filename']
            wait_until(final.is_file)
            self.assertEqual(final.read_bytes(), payload)
            self.assertEqual(ranges, ['bytes=6-'])
        finally:
            httpd.shutdown(); httpd.server_close()
    def test_cancel_keeps_the_partial_download(self):
        payload = b'x' * (128 * 1024)
        digest = hashlib.sha256(payload).hexdigest()
        httpd, _, url = serve(payload, delay=0.25, step=32 * 1024)
        entry, quant = self.quant(digest, len(payload))
        partial = self.root / 'models' / '.partial' / (quant['id'] + '.part')
        try:
            self.patch_quant(entry, quant, url)
            model_library.enqueue(quant['id'])
            wait_until(lambda: partial.exists() and partial.stat().st_size > 0)
            model_library.cancel(quant['id'])
            wait_until(lambda: model_library.jobs_view()[0]['status'] == 'paused')
            self.assertTrue(partial.exists())
            self.assertFalse((self.root / 'models' / quant['filename']).exists())
            self.assertEqual(models.registry(), [])
        finally:
            httpd.shutdown(); httpd.server_close()
    def test_enqueue_rejects_tight_disk_and_budget_without_a_partial(self):
        entry, quant = self.quant('a' * 64, 5000)
        usage = shutil.disk_usage(self.data)._replace(free=100)
        with patch.object(model_library, 'quant_by_id', lambda ident: (entry, quant) if ident == quant['id'] else (None, None)), \
             patch.object(model_library, 'resolve', lambda entry, quant: {'url': 'http://127.0.0.1/file', 'size': quant['bytes'], 'sha256': quant['sha256']}), \
             patch.object(model_library.shutil, 'disk_usage', lambda path: usage):
            with self.assertRaisesRegex(ValueError, 'Not enough free space'):
                model_library.enqueue(quant['id'])
        self.assertFalse((self.root / 'models').exists())
        with patch.object(model_library, 'BUDGET', 1000), \
             patch.object(model_library, 'quant_by_id', lambda ident: (entry, quant) if ident == quant['id'] else (None, None)), \
             patch.object(model_library, 'resolve', lambda entry, quant: {'url': 'http://127.0.0.1/file', 'size': quant['bytes'], 'sha256': quant['sha256']}):
            with self.assertRaisesRegex(ValueError, 'download budget'):
                model_library.enqueue(quant['id'])
        self.assertFalse((self.root / 'models' / '.partial').exists())
    def test_remove_requires_confirmation_and_stops_the_active_model_first(self):
        payload = b'remove-me'
        digest = hashlib.sha256(payload).hexdigest()
        entry, quant = self.quant(digest, len(payload))
        folder = self.root / 'models'
        folder.mkdir()
        target = folder / quant['filename']
        target.write_bytes(payload)
        with patch.object(model_library, 'quant_by_id', lambda ident: (entry, quant) if ident == quant['id'] else (None, None)):
            model_library._register(entry, quant, target)
            stopped = []
            with patch.dict(model_library.CONFIG, model=quant['id'], model_file=str(target)):
                with self.assertRaisesRegex(ValueError, 'Confirm removal'):
                    model_library.remove(quant['id'], False)
                self.assertTrue(target.exists())
                # The model in use can be removed: its server is stopped first and the selection cleared.
                with patch('backend.runtime.stop_owned', lambda: stopped.append(1)), \
                     patch('backend.config.save_config', lambda changes: model_library.CONFIG.update(changes)):
                    result = model_library.remove(quant['id'], True)
                self.assertEqual(stopped, [1])
                self.assertEqual((model_library.CONFIG['model'], model_library.CONFIG['model_file']), ('', ''))
                self.assertIn('No model is installed now', result['message'])
        self.assertTrue(result['deleted'])
        self.assertFalse(target.exists())
        self.assertEqual(models.registry(), [])
    def test_catalog_is_pinned_and_context_comes_from_file_metadata(self):
        from backend.model_catalog import CONTEXT_LIMIT, cache_bytes
        from backend.model_catalog_data import REPOS
        self.assertGreaterEqual(sum(item['variant'] == 'standard' for item in CATALOG), 12)
        self.assertGreaterEqual(sum(item['variant'] == 'abliterated' for item in CATALOG), 12)
        for entry in CATALOG:
            url = model_library.canonical_url(entry, entry['quants'][0])
            self.assertIn('/resolve/' + entry['revision'] + '/', url)
            self.assertNotIn('/resolve/main/', url)
            self.assertEqual(entry['context_supported'], REPOS[entry['repo']]['context'])
            self.assertEqual(entry['context'], min(CONTEXT_LIMIT, entry['context_supported']))
            for quant in entry['quants']:
                self.assertEqual(quant['memory_bytes'], quant['bytes'] + entry['cache_bytes'])
            if entry['projector']:
                self.assertIn('/resolve/' + entry['projector']['revision'] + '/', model_library.canonical_url(entry, entry['projector']))
        phi = next(item for item in CATALOG if item['id'] == 'phi-4')
        self.assertEqual(phi['context'], 16384)
        plain = {'architecture': 'llama', 'layers': 2, 'kv_heads': 1, 'key_length': 16, 'value_length': 16, 'sliding_window': 0}
        self.assertEqual(cache_bytes(plain, 1000), round(2 * 1000 * 32 * 34 / 32))
        windowed = plain | {'architecture': 'gemma3', 'layers': 6, 'sliding_window': 100}
        self.assertEqual(cache_bytes(windowed, 1000), round((1 * 1000 + 5 * 256) * 32 * 34 / 32))
    def test_existing_quantization_ids_stay_stable(self):
        ids = {quant['id'] for entry in CATALOG for quant in entry['quants']}
        for ident in ('qwen3-8b-q4', 'qwen3-4b-q8', 'qwen25-coder-7b-q6', 'qwen25-coder-3b-q4',
                      'qwen25-coder-7b-abliterated-q8', 'qwen25-7b-abliterated-q4', 'qwen25-coder-14b-abliterated-q6'):
            self.assertIn(ident, ids)
    def test_vision_projector_attaches_to_registered_models_and_is_protected(self):
        payload = b'gguf-projector'
        digest = hashlib.sha256(payload).hexdigest()
        entry, quant = self.quant(hashlib.sha256(b'weights').hexdigest(), 7)
        projector = {'id': 'test-mmproj', 'label': 'Vision projector', 'kind': 'projector', 'filename': 'test-mmproj.gguf',
                     'bytes': len(payload), 'sha256': digest, 'repo': 'example/base', 'revision': 'b' * 40, 'note': ''}
        entry = entry | {'projector': projector, 'revision': 'a' * 40, 'quants': [quant]}
        folder = self.root / 'models'; folder.mkdir()
        weights = folder / quant['filename']; weights.write_bytes(b'weights')
        httpd, _, url = serve(payload)
        lookup = lambda ident: (entry, quant) if ident == quant['id'] else (entry, projector) if ident == projector['id'] else (None, None)
        try:
            with patch.object(model_library, 'CATALOG', [entry]), patch.object(model_library, 'quant_by_id', lookup), \
                 patch.object(model_library, 'resolve', lambda entry, item: {'url': url, 'size': item['bytes'], 'sha256': item['sha256']}):
                self.assertEqual(model_library.canonical_url(entry, projector), f'https://huggingface.co/example/base/resolve/{"b" * 40}/test-mmproj.gguf')
                model_library._register(entry, quant, weights)
                self.assertEqual(models.registry()[0]['projector_file'], '')
                model_library.enqueue(projector['id'])
                final = folder / projector['filename']
                wait_until(lambda: models.registry()[0]['projector_file'] == str(final))
                self.assertEqual(final.read_bytes(), payload)
                view = model_library.library(None)['models'][0]
                self.assertTrue(view['projector']['verified'])
                self.assertEqual([item['id'] for item in model_library.library(None)['models']], [entry['id']])
                with self.assertRaisesRegex(ValueError, 'used together with a model'):
                    model_library.prepare(projector['id'])
                self.assertEqual(model_library.prepare(quant['id'])['projector_file'], str(final))
                with patch.dict(model_library.CONFIG, projector_file=str(final)):
                    with self.assertRaisesRegex(ValueError, 'using this vision projector'):
                        model_library.remove(projector['id'], True)
                with patch.dict(model_library.CONFIG, projector_file=''):
                    result = model_library.remove(projector['id'], True)
                self.assertTrue(result['deleted'])
                self.assertFalse(final.exists())
                self.assertTrue(weights.exists())
                self.assertEqual(models.registry()[0]['projector_file'], '')
        finally:
            httpd.shutdown(); httpd.server_close()
    def quant(self, digest, size):
        entry = {'id': 'test-abliterated', 'name': 'Test Abliterated', 'variant': 'abliterated', 'parameters': '1B',
                 'purpose': 'Test', 'description': 'Test weights.', 'strengths': ['Test'], 'context': 32768, 'vision': False,
                 'repo': 'example/test', 'license': 'Test', 'provenance': 'Test publisher', 'hardware': 'Test', 'caveat': 'Test caveat',
                 'family': 'Test', 'active_parameters': '', 'context_supported': 32768, 'cache_bytes': 0, 'architecture': 'llama',
                 'revision': 'a' * 40, 'projector': None}
        quant = {'id': 'test-abliterated-q4', 'label': 'Q4_K_M', 'filename': 'test-abliterated-q4.gguf', 'bytes': size, 'sha256': digest, 'memory': 'Test'}
        return entry, quant
    def patch_quant(self, entry, quant, url):
        quant_patch = patch.object(model_library, 'quant_by_id', lambda ident, entry=entry, quant=quant: (entry, quant) if ident == quant['id'] else (None, None))
        resolve_patch = patch.object(model_library, 'resolve', lambda entry, quant, url=url: {'url': url, 'size': quant['bytes'], 'sha256': quant['sha256']})
        quant_patch.start(); resolve_patch.start()
        self.patches.extend([quant_patch, resolve_patch])

if __name__ == '__main__':
    unittest.main()
