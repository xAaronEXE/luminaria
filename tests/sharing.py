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

if __name__=='__main__': unittest.main()
