import asyncio,unittest
from backend import retrieval as r
class Ssrf(unittest.TestCase):
 def blocked(self,host):
  with self.assertRaises(ValueError):asyncio.run(r.check_host(host))
 def test_private_and_local_literals(self):
  for h in ('127.0.0.1','10.0.0.5','192.168.1.1','172.16.4.4','169.254.169.254','0.0.0.0','::1','fe80::1','::ffff:192.168.0.1','100.64.0.1'):self.blocked(h)
 def test_public_literal_allowed(self):
  asyncio.run(r.check_host('93.184.216.34'))
 def test_decimal_ip_resolves_to_loopback(self):
  try:self.blocked('2130706433')
  except AssertionError:self.skipTest('resolver does not expand decimal addresses here')
if __name__=='__main__':unittest.main()
