import asyncio,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import screenshot

def chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return p.chromium.executable_path
    except Exception: return None

class Screenshot(unittest.TestCase):
    def test_only_local_pages(self):
        with tempfile.TemporaryDirectory() as d:
            page=Path(d)/'index.html'; page.write_text('<h1>Hi</h1>')
            self.assertTrue(screenshot.target(str(page),lambda p:p).startswith('file://'))
            self.assertEqual(screenshot.target('http://localhost:5173/',lambda p:p),'http://localhost:5173/')
            for bad in ('https://example.com','http://192.168.1.5/','http://evil.localhost.example.com/',str(Path(d)/'missing.html'),''):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError): screenshot.target(bad,lambda p:p)
    @unittest.skipUnless(os.name=='nt','headless Edge screenshot runs on Windows')
    def test_takes_a_real_screenshot(self):
        with tempfile.TemporaryDirectory() as d:
            page=Path(d)/'index.html'; page.write_text('<body style="background:#123"><h1 style="color:white">Built by Luminaria</h1></body>')
            out=asyncio.run(screenshot.take(str(page),lambda p:p,Path(d)/'shots',800,600))
            self.assertGreater(out.stat().st_size,1000)
            self.assertEqual(out.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')

if __name__=='__main__':unittest.main()
