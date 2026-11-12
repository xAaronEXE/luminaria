import asyncio,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import sharing
from backend.config import CONFIG

class Sharing(unittest.TestCase):
    def test_pairing_keys_are_independent_and_revocable(self):
        import hashlib
        saved={}
        def write(_name, value):
            saved.clear()
            saved.update(value)
        with patch.object(sharing,'read_secrets',lambda _:saved.copy()), patch.object(sharing,'write_secrets',write):
            first=sharing.issue_peer('First PC')
            second=sharing.issue_peer('Second PC')
            c=TestClient(sharing.share_app())
            self.assertEqual(c.get('/v1/models').status_code,401)
            self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer wrong'}).status_code,401)
            for token in (first,second):
                self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer '+token}).status_code,200)
            sharing.revoke_peer(hashlib.sha256(first.encode()).hexdigest())
            self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer '+first}).status_code,401)
            self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer '+second}).status_code,200)
            self.assertEqual(c.post('/luminaria/lend',headers={'Authorization':'Bearer '+second},json={'on':True}).status_code,405)
            self.assertEqual(c.get('/api/state').status_code,404)

    def test_pin_mismatch_stops_pairing_before_the_code_is_sent(self):
        with patch('backend.peer_tls.verify_peer',side_effect=ValueError('fingerprint mismatch')), \
                patch('backend.sharing.httpx.AsyncClient') as client:
            with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                asyncio.run(sharing.pair('pc.local','123456',fingerprint='a'*64))
            client.assert_not_called()

    def test_pinned_certificate_completes_a_real_tls_handshake(self):
        import socket
        import ssl
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from backend import peer_tls

        with TemporaryDirectory() as folder, patch.object(peer_tls,'BASE_DATA',Path(folder)):
            cert,key=peer_tls.identity()
            server=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server.load_cert_chain(cert,key)
            pem=cert.read_text()
            with socket.create_server(('127.0.0.1',0)) as listener, ThreadPoolExecutor(1) as executor:
                listener.settimeout(3)
                address=listener.getsockname()

                def receive():
                    for _ in range(2):
                        raw,_=listener.accept()
                        with raw, server.wrap_socket(raw,server_side=True):
                            pass

                accepted=executor.submit(receive)
                self.assertEqual(peer_tls.verify_peer(*address,peer_tls.fingerprint(pem)),pem)
                with socket.create_connection(address,timeout=3) as raw:
                    with peer_tls.client_context(pem).wrap_socket(raw,server_hostname=address[0]) as client:
                        self.assertIsNotNone(client.cipher())
                accepted.result(timeout=3)

    def test_rpc_peers_are_validated(self):
        with patch.dict(CONFIG,rpc_peers='192.168.1.20, gaming-pc:50060'):
            self.assertEqual(sharing.rpc_peers(),['192.168.1.20:50052','gaming-pc:50060'])
        with patch.dict(CONFIG,rpc_peers='1.2.3.4; rm -rf /'):
            with self.assertRaises(ValueError): sharing.rpc_peers()

    def test_unreachable_gpu_lender_is_omitted(self):
        from backend.runtime import reachable_rpc_peers
        from unittest.mock import MagicMock

        with patch('backend.runtime.socket.create_connection', side_effect=[OSError('offline'), MagicMock()]) as connect:
            self.assertEqual(reachable_rpc_peers(['offline:50052', 'online:50052']),
                             (['online:50052'], ['offline:50052']))
        self.assertEqual(connect.call_count, 2)

    def test_disabling_split_clears_local_settings_before_contacting_peers(self):
        from unittest.mock import AsyncMock
        from backend import services

        apply = AsyncMock()
        def paired():
            apply.assert_awaited_once_with({'rpc_peers': '', 'split_models': False})
            return []
        with patch.object(sharing, 'apply', apply), patch.object(services, 'services', paired):
            result = asyncio.run(sharing.set_split(False))
        self.assertEqual(result, {'peers': [], 'problems': []})

class RpcServerName(unittest.TestCase):
    def test_finds_new_and_old_names(self):
        import os,tempfile
        from pathlib import Path
        d=Path(tempfile.mkdtemp());ext='.exe' if os.name=='nt' else ''
        (d/('llama-server'+ext)).write_bytes(b'')
        with patch('backend.runtime.resolve_executable',lambda:str(d/('llama-server'+ext))):
            self.assertIsNone(sharing.rpc_executable())
            (d/('ggml-rpc-server'+ext)).write_bytes(b'');self.assertEqual(sharing.rpc_executable().name,'ggml-rpc-server'+ext)

if __name__=='__main__': unittest.main()
