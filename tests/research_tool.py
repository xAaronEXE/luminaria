import asyncio,unittest
from unittest.mock import patch
from backend import retrieval

PAGES={'https://a.com/1':'Intro text that is long enough to keep around here.\n\nLlama.cpp KV cache offload: use --no-kv-offload to keep the cache in system RAM, which saves VRAM but runs slower.\n\nUnrelated footer text about cookies and privacy policy here.',
       'https://b.org/2':'Flash attention with quantized KV cache q8_0 halves memory with little quality loss in llama.cpp benchmarks.'}
async def search(q): return {'status':'ok','results':[{'title':'A','url':'https://a.com/1','snippet':'a'},{'title':'A2','url':'https://a.com/3','snippet':'same site'},{'title':'B','url':'https://b.org/2','snippet':'b'}]}
async def fetch(u): return {'status':'ok','text':PAGES[u],'title':u} if u in PAGES else {'status':'error'}

class Research(unittest.TestCase):
    def test_reads_distinct_sites_and_keeps_relevant_passages(self):
        with patch.object(retrieval,'search',search),patch.object(retrieval,'fetch',fetch):
            r=asyncio.run(retrieval.research('llama.cpp kv cache offload system ram',['kv cache quantization']))
        self.assertEqual([s['url'] for s in r['sources']],['https://a.com/1','https://b.org/2'])
        self.assertIn('--no-kv-offload',r['sources'][0]['excerpt'])
        self.assertEqual(r['more_results'][0]['url'],'https://a.com/3')
        self.assertEqual(len(r['searches']),2)
    def test_empty_question(self):
        self.assertEqual(asyncio.run(retrieval.research('  '))['status'],'error')

if __name__=='__main__': unittest.main()
