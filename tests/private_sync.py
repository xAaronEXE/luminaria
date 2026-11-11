import unittest

import httpx

from backend.cloud_sync import CloudSync
from backend.sync_secure import new_key


ORIGIN = 'https://luminaria-private.account.workers.dev'
DEVICE = 'a' * 64


class PrivateSync(unittest.IsolatedAsyncioTestCase):
    def test_only_a_bare_https_worker_origin_is_accepted(self):
        self.assertEqual(CloudSync.private_settings(ORIGIN + '/', DEVICE), (ORIGIN, DEVICE))
        for url in ('http://luminaria-private.account.workers.dev', ORIGIN + '/other',
                    ORIGIN + ':8443', 'https://user@luminaria-private.account.workers.dev',
                    'https://luminaria-private.account.workers.dev.example.org', 'https://127.0.0.1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                CloudSync.private_settings(url, DEVICE)

    def test_remote_revision_state_is_scoped_to_its_storage(self):
        key = new_key()
        first = CloudSync.local_scope(key, 'private', ORIGIN)
        second = CloudSync.local_scope(key, 'private', 'https://new.account.workers.dev')
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, CloudSync.local_scope(key, 'folder', ''))

    async def test_private_probe_sends_only_the_device_key_and_checks_the_worker_type(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={'available': True, 'account_id': 'private-sync'})

        sync = CloudSync(None)
        sync.client_factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
        await sync.probe_private(ORIGIN, DEVICE)
        self.assertEqual(str(requests[0].url), ORIGIN + '/sync/status')
        self.assertEqual(requests[0].headers['authorization'], 'Bearer ' + DEVICE)

    async def test_redirects_are_not_followed(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(302, headers={'Location': 'https://example.org/'})

        sync = CloudSync(None)
        sync.client_factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(respond), **kwargs)
        with self.assertRaises(ValueError):
            await sync.probe_private(ORIGIN, DEVICE)
        self.assertEqual(len(requests), 1)
