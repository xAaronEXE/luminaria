"""Acceptance set for web_fetch: saved pages and generated documents served through a mock transport."""
import unittest
from pathlib import Path
import httpx
from backend import retrieval

FIXTURES=Path(__file__).parent/'fixtures'/'web'

def pdf(text,encrypt=False):
 stream=f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
 objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
  b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
  b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
 out=b'%PDF-1.4\n';offsets=[]
 for i,body in enumerate(objects,1):offsets.append(len(out));out+=f'{i} 0 obj\n'.encode()+body+b'\nendobj\n'
 xref=len(out);out+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()+b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
 out+=f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
 if encrypt:
  from pypdf import PdfReader,PdfWriter
  import io
  writer=PdfWriter();writer.append(PdfReader(io.BytesIO(out)));writer.encrypt('secret');buffer=io.BytesIO();writer.write(buffer);out=buffer.getvalue()
 return out

async def chunks(block,count):
 for _ in range(count):yield block

def html(name):return (FIXTURES/name).read_bytes()
SITE={
 '/article':lambda r:httpx.Response(200,content=html('article.html'),headers={'content-type':'text/html; charset=utf-8'}),
 '/no-main':lambda r:httpx.Response(200,content=html('no-main.html'),headers={'content-type':'text/html'}),
 '/app':lambda r:httpx.Response(200,content=html('app-shell.html'),headers={'content-type':'text/html'}),
 '/blank':lambda r:httpx.Response(200,content=html('blank.html'),headers={'content-type':'text/html'}),
 '/latin1':lambda r:httpx.Response(200,content='<html><head><title>Café</title></head><body><p>Crème brûlée costs 5 € — naïve façade, résumé and señor are all spelled correctly here in this paragraph of more than enough length to be the main content of the page without a container.</p></body></html>'.encode('cp1252'),headers={'content-type':'text/html; charset=windows-1252'}),
 '/meta-charset':lambda r:httpx.Response(200,content='<html><head><meta charset="iso-8859-1"><title>Grüße</title></head><body><p>Schöne Grüße aus Köln.</p></body></html>'.encode('latin-1'),headers={'content-type':'text/html'}),
 '/paper.pdf':lambda r:httpx.Response(200,content=pdf('Quarterly results show steady growth.'),headers={'content-type':'application/pdf'}),
 '/untyped.pdf':lambda r:httpx.Response(200,content=pdf('Untyped download works.'),headers={'content-type':''}),
 '/scan.pdf':lambda r:httpx.Response(200,content=pdf(''),headers={'content-type':'application/pdf'}),
 '/locked.pdf':lambda r:httpx.Response(200,content=pdf('Hidden',encrypt=True),headers={'content-type':'application/pdf'}),
 '/broken.pdf':lambda r:httpx.Response(200,content=b'%PDF-1.4 not really',headers={'content-type':'application/pdf'}),
 '/image.png':lambda r:httpx.Response(200,content=b'\x89PNG',headers={'content-type':'image/png'}),
 '/huge':lambda r:httpx.Response(200,content=b'x',headers={'content-type':'text/html','content-length':str(retrieval.HTML_LIMIT+1)}),
 '/stream-huge':lambda r:httpx.Response(200,content=chunks(b'a'*1_000_000,6),headers={'content-type':'text/plain'}),
 '/data.json':lambda r:httpx.Response(200,json={'answer':42},headers={'content-type':'application/json'}),
 '/moved':lambda r:httpx.Response(301,headers={'location':'https://site.test/article'}),
 '/loop':lambda r:httpx.Response(302,headers={'location':'https://site.test/loop'}),
 '/long':lambda r:httpx.Response(200,text='word '*10000,headers={'content-type':'text/plain'}),
}

class Site:
 def __init__(self):self.hits=[]
 def __call__(self,request):
  self.hits.append(request.url.path);return SITE.get(request.url.path,lambda r:httpx.Response(404))(request)

async def nowait(s):pass

class WebFetchAcceptance(unittest.IsolatedAsyncioTestCase):
 def setUp(self):retrieval._cache.clear();self.site=Site();self.client=httpx.AsyncClient(transport=httpx.MockTransport(self.site),follow_redirects=True,max_redirects=6)
 async def asyncTearDown(self):await self.client.aclose();retrieval._cache.clear()
 async def get(self,path,**kw):return await retrieval.fetch('https://site.test'+path,client=self.client,sleep=nowait,**kw)

 async def test_article_keeps_content_and_drops_page_chrome(self):
  r=await self.get('/article')
  self.assertEqual((r['status'],r['title'],r['content_type']),('ok','Tuning llama.cpp threads on Ryzen','text/html'))
  for kept in ('# Tuning llama.cpp threads','## Measure before changing','- Use physical cores','llama-server -m model.gguf -t 8','41.2'):self.assertIn(kept,r['text'])
  for dropped in ('cookies','Archive','newsletter','Copyright','ten GPU tips','analytics'):self.assertNotIn(dropped,r['text'])

 async def test_page_without_main_uses_densest_block(self):
  r=await self.get('/no-main')
  self.assertEqual(r['status'],'ok');self.assertIn('Version 4.2',r['text']);self.assertIn('Known issue',r['text'])
  self.assertNotIn('Download',r['text']);self.assertNotIn('Privacy',r['text'])

 async def test_declared_and_meta_encodings_decode_correctly(self):
  r=await self.get('/latin1');self.assertEqual(r['title'],'Café');self.assertIn('Crème brûlée costs 5 €',r['text']);self.assertIn('señor',r['text'])
  r=await self.get('/meta-charset');self.assertEqual(r['title'],'Grüße');self.assertIn('Schöne Grüße aus Köln',r['text'])

 async def test_pdf_text_is_extracted_with_page_count(self):
  r=await self.get('/paper.pdf')
  self.assertEqual((r['status'],r['content_type'],r['pages']),('ok','application/pdf',1));self.assertIn('Quarterly results show steady growth',r['text'])
  self.assertIn('Untyped download works',(await self.get('/untyped.pdf'))['text'])

 async def test_pdf_failures_are_distinct(self):
  self.assertEqual((await self.get('/scan.pdf'))['category'],'extraction')
  self.assertEqual((await self.get('/locked.pdf'))['category'],'auth')
  self.assertEqual((await self.get('/broken.pdf'))['category'],'extraction')

 async def test_javascript_shell_blank_and_unsupported_are_distinct(self):
  app=await self.get('/app');self.assertEqual(app['category'],'needs_javascript');self.assertIn('browser',app['guidance'])
  blank=await self.get('/blank');self.assertEqual(blank['status'],'empty');self.assertNotIn('category',blank)
  image=await self.get('/image.png');self.assertEqual((image['category'],image['content_type']),('unsupported','image/png'))

 async def test_size_limits_by_header_and_by_stream(self):
  self.assertEqual((await self.get('/huge'))['category'],'too_large')
  self.assertEqual((await self.get('/stream-huge'))['category'],'too_large')

 async def test_long_text_is_truncated_with_total(self):
  r=await self.get('/long');self.assertTrue(r['truncated']);self.assertEqual(len(r['text']),retrieval.TEXT_LIMIT);self.assertEqual(r['total_characters'],len(('word '*10000).strip()))

 async def test_json_is_read_as_text(self):
  r=await self.get('/data.json');self.assertEqual(r['status'],'ok');self.assertIn('42',r['text'])

 async def test_redirects_report_the_final_address(self):
  r=await self.get('/moved');self.assertEqual((r['status'],r['source'],r['redirected']),('ok','https://site.test/article',True))
  self.assertEqual((await self.get('/loop'))['category'],'network')

 async def test_missing_page_is_not_found_without_retry(self):
  r=await self.get('/gone');self.assertEqual((r['category'],r['attempts'],self.site.hits),('not_found',1,['/gone']))

 async def test_cache_reuses_recent_pages_until_refresh(self):
  first=await self.get('/article');second=await self.get('/article')
  self.assertNotIn('cached',first);self.assertTrue(second['cached']);self.assertEqual(second['retrieved_at'],first['retrieved_at']);self.assertEqual(self.site.hits,['/article'])
  third=await self.get('/article',refresh=True);self.assertNotIn('cached',third);self.assertEqual(self.site.hits,['/article','/article'])

 async def test_failures_are_not_cached(self):
  await self.get('/gone');await self.get('/gone');self.assertEqual(self.site.hits,['/gone','/gone'])

 async def test_private_addresses_are_refused_before_any_request(self):
  for url in ('http://127.0.0.1/admin','http://localhost:3211/api','file:///C:/Windows/win.ini','http://[::1]/','http://169.254.169.254/latest','ftp://site.test/x'):
   r=await retrieval.fetch(url,client=self.client);self.assertEqual(r['category'],'invalid_input',url)
  self.assertEqual(self.site.hits,[])

if __name__=='__main__':unittest.main()
