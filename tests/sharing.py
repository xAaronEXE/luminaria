import asyncio,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import sharing
from backend.config import CONFIG

class Sharing(unittest.TestCase):
    def test_pairing_key_is_required(self):
        with patch.object(sharing,'share_key',lambda:'k123'):
            c=TestClient(sharing.share_app())
            self.assertEqual(c.get('/v1/models').status_code,401)
            self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer wrong'}).status_code,401)
            self.assertEqual(c.get('/v1/models',headers={'Authorization':'Bearer k123'}).status_code,200)
            self.assertEqual(c.get('/api/state').status_code,404)   # nothing else on this PC is reachable
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
