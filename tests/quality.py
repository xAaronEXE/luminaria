import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import benchmark_store,quality

def server(answer):
 def handle(request):
  prompt=json.loads(request.content)['messages'][0]['content']
  item=next(i for i in quality.ITEMS if i['prompt'] in prompt)
  body=json.loads(request.content)
  assert body['temperature']==0 and body['chat_template_kwargs']=={'enable_thinking':False}
  return httpx.Response(200,json={'choices':[{'message':{'content':answer(item)}}]})
 return httpx.AsyncClient(transport=httpx.MockTransport(handle))

class QualityTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory()
  self.patches=[patch.object(benchmark_store,'PATH',Path(self.folder.name)/'b.sqlite3'),patch.object(quality,'registry',lambda:[{'id':'m','quantization':'Q4_K_M'}])]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches:p.stop()
  self.folder.cleanup()

 def test_answers_are_graded_exactly_and_stored_apart_from_speed(self):
  def answer(item):
   if item['kind']=='coding':return 'Working it out.\nANSWER: **'+item['answer'].upper()+'**'
   return 'ANSWER: wrong' if item['id']=='syllogism' else 'Some steps\nANSWER: '+item['answer']+'.'
  result=asyncio.run(quality.evaluate('m',server(answer)))
  self.assertEqual(result['coding'],{'passed':6,'total':6});self.assertEqual(result['reasoning'],{'passed':5,'total':6})
  missed=[i for i in result['items'] if not i['passed']]
  self.assertEqual([(i['id'],i['given'],i['expected']) for i in missed],[('syllogism','wrong','no')])
  self.assertEqual(benchmark_store.evaluations('m')[0]['coding']['passed'],6)
  self.assertEqual(benchmark_store.history('m'),[])

 def test_answer_parsing(self):
  item=lambda answer:{'id':'x','kind':'coding','answer':answer}
  cases=[('b','Final.\nANSWER: B) Change lo = mid',True),('b','ANSWER: Option B',True),('b','ANSWER: C',False),
         ('5','ANSWER: $5',False),('5','ANSWER: 5',True),('the 3','answer:  The   3',True),
         ('42','I think 42',False),('42','<think>ANSWER: 42</think>ANSWER: 41',False),('42','ANSWER: 40\nANSWER: 42',True)]
  for expected,content,passed in cases:
   with self.subTest(content=content):self.assertEqual(quality.score(item(expected),content)['passed'],passed)

 def test_server_failures_save_nothing(self):
  for transport in (httpx.MockTransport(lambda r:httpx.Response(503)),httpx.MockTransport(lambda r:(_ for _ in ()).throw(httpx.ConnectError('down')))):
   with self.assertRaises(ValueError):asyncio.run(quality.evaluate('m',httpx.AsyncClient(transport=transport)))
  self.assertEqual(benchmark_store.evaluations('m'),[])
  with self.assertRaises(ValueError):asyncio.run(quality.evaluate('missing',server(lambda i:'')))

 def test_question_set_is_well_formed(self):
  self.assertEqual(len({i['id'] for i in quality.ITEMS}),12)
  self.assertEqual(sum(i['kind']=='coding' for i in quality.ITEMS),6)
  for item in quality.ITEMS:self.assertEqual(quality.normalize(item['answer']),item['answer'])

if __name__=='__main__':unittest.main()
