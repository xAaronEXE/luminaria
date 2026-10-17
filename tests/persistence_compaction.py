import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import attachments,benchmark_store
from backend.compaction import summarize

class PersistenceTests(unittest.TestCase):
 def test_legacy_benchmarks_import_once_and_new_results_survive_reopen(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(benchmark_store,'PATH',Path(folder)/'benchmarks.sqlite3'):
   old=[{'test':'old','tps':10}]
   self.assertEqual(len(benchmark_store.history('model',old)),1)
   self.assertEqual(len(benchmark_store.history('model',old)),1)
   benchmark_store.record('model',{'test':'new','tps':12})
   self.assertEqual([x['test'] for x in benchmark_store.history('model',old)],['new','old'])
   self.assertEqual(benchmark_store.history('other'),[])
 def test_text_attachment_keeps_full_file_and_bounds_prompt(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);workspace=root/'Files';workspace.mkdir()
   def bounded(path):
    p=(workspace/path).resolve()
    if not p.is_relative_to(workspace):raise ValueError('outside')
    return p
   with patch.object(attachments,'DATA',root),patch.object(attachments,'workspace_path',bounded):
    raw=('FACT_'+('x'*20000)).encode();item=attachments.save_text('plan.md',raw)
    self.assertEqual((workspace/item['path']).read_bytes(),raw)
    exact=b'\xef\xbb\xbfline one\r\nline two\n';other=attachments.save_text('lines.txt',exact)
    self.assertEqual((workspace/other['path']).read_bytes(),exact)
    preview=attachments.text_part(item['id'])['text'];self.assertIn('Preview limited',preview);self.assertLess(len(preview),17000)
    for name,data in [('file.exe',b'hello'),('file.txt',b'\x00'),('file.txt',b'\xff'),('file.txt',b'x'*512001)]:
     with self.assertRaises(ValueError):attachments.save_text(name,data)
    with self.assertRaises(ValueError):attachments.text_part('../config.json')

class CompactionTests(unittest.IsolatedAsyncioTestCase):
 async def test_oversized_message_is_fully_consumed_in_bounded_calls(self):
  consumed=[]
  async def count(messages):return sum(len(m['content']) for m in messages), 'test byte budget'
  async def complete(messages,max_tokens):
   payload=json.loads(messages[1]['content']);consumed.append(payload['transcript_fragment'])
   return {'content':'Goal: verified goals kept.\nOpen work: pending tasks remain preserved.'}
  transcript=[{'message_id':1,'role':'user','content':'A'*18000+'END_SENTINEL'}]
  result=await summarize(transcript,'',4096,count,complete)
  self.assertEqual(''.join(consumed),json.dumps(transcript[0],ensure_ascii=False))
  self.assertIn('pending tasks',result);self.assertGreater(len(consumed),1)
 async def test_invalid_summary_fails_instead_of_silently_advancing(self):
  async def count(messages):return 500,'test'
  async def complete(messages,max_tokens):return {'content':''}
  with self.assertRaises(ValueError):await summarize([{'content':'important'}],'prior',4096,count,complete)
if __name__=='__main__':unittest.main()
