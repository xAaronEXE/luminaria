import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from backend import benchmark_store,quality

GOOD={'only-ok':'OK','three-lines':'Apple\nBanana\nPassion fruit','no-letter-e':'A calm sky shows its many moods today',
      'json-only':'```json\n{"name": "Mia", "age": 7}\n```','four-caps':'GOLDEN LIGHT SLOWLY RISING','two-exclaims':'Rain is falling hard! I love its sound!'}
ARGS={'get_weather':{'city':'Paris'},'add_event':{'title':'Dentist','date':'2026-03-14','time':'15:30'},
      'convert_currency':{'amount':250,'from_currency':'USD','to_currency':'EUR'},'search_files':{'query':'quarterly budget'},
      'send_email':{'to':'sam@example.com','subject':'Lunch','body':'Running 10 minutes late.'}}

def item_for(body):
    prompt=body['messages'][0]['content']
    return next(i for i in quality.ALL if i['prompt'] in prompt)

def server(reply):
    def handle(request):
        body=json.loads(request.content); item=item_for(body)
        assert body['temperature']==0 and body['chat_template_kwargs']=={'enable_thinking':False}
        assert ('tools' in body)==('call' in item)
        return httpx.Response(200,json={'choices':[{'message':reply(item)}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))

def perfect(item):
    if 'check' in item: return {'content':GOOD[item['id']]}
    if 'call' in item:
        if item['call'] is None: return {'content':'12 times 12 is 144.'}
        return {'content':'','tool_calls':[{'id':'1','type':'function','function':{'name':item['call'],'arguments':json.dumps(ARGS[item['call']])}}]}
    return {'content':'Working it out.\nANSWER: **'+item['answer'].upper()+'**'}

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.patches=[patch.object(benchmark_store,'PATH',Path(self.folder.name)/'b.sqlite3'),patch.object(quality,'registry',lambda:[{'id':'m','quantization':'Q4_K_M'}])]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in self.patches:p.stop()
        self.folder.cleanup()

    def test_perfect_answers_score_100_in_every_area(self):
        result=asyncio.run(quality.evaluate('m',server(perfect)))
        self.assertEqual(result['score'],100)
        for key,area in result['areas'].items():
            with self.subTest(area=key):self.assertEqual(area['passed'],area['total'])
        self.assertEqual(benchmark_store.evaluations('m')[0]['score'],100)
        self.assertEqual(benchmark_store.history('m'),[],'kept apart from speed results')

    def test_each_area_counts_equally(self):
        def reply(item):
            if item['kind']=='tools': return {'content':'I cannot help with that.'}   # fails all tool use, except answering directly
            return perfect(item)
        result=asyncio.run(quality.evaluate('m',server(reply)))
        tools=result['areas']['tools']
        self.assertEqual((tools['passed'],tools['total']),(0,6))
        self.assertEqual(result['score'],round(100*5/6))

    def test_tool_use_grading(self):
        call=lambda name,args:{'content':'','tool_calls':[{'function':{'name':name,'arguments':json.dumps(args)}}]}
        item=lambda i:next(x for x in quality.CALLS if x['id']==i)
        self.assertTrue(quality.grade(item('weather'),call('get_weather',{'city':'Paris, France'}))['passed'])
        self.assertFalse(quality.grade(item('weather'),call('search_files',{'query':'Paris weather'}))['passed'],'wrong tool')
        self.assertFalse(quality.grade(item('currency'),call('convert_currency',{'amount':250,'from_currency':'EUR','to_currency':'USD'}))['passed'],'wrong direction')
        self.assertTrue(quality.grade(item('weather'),{'content':'{"name": "get_weather", "arguments": {"city": "Paris"}}'})['passed'],'JSON written in the text counts')
        self.assertFalse(quality.grade(item('no-tool-needed'),call('get_weather',{'city':'x'}))['passed'],'calling a tool when none is needed fails')
        self.assertTrue(quality.grade(item('no-tool-needed'),{'content':'144'})['passed'])

    def test_instruction_checks(self):
        item=lambda i:next(x for x in quality.CHECKED if x['id']==i)
        cases=[('only-ok','OK.',False),('only-ok','<think>hmm</think>OK',True),('three-lines','1. Apple\n2. Pear\n3. Fig',False),('three-lines','Apple\nPear',False),
               ('no-letter-e','The ocean is wide and blue today',False),('json-only','{"name":"Mia","age":"7"}',False),('json-only','Here: {"name":"Mia","age":7}',False),
               ('four-caps','GOLDEN LIGHT RISING',False),('four-caps','Golden Light Slowly Rising',False),('two-exclaims','Rain! More rain. Yes!',False)]
        for id,content,passed in cases:
            with self.subTest(id=id,content=content):self.assertEqual(quality.grade(item(id),{'content':content})['passed'],passed)
        for id,content in GOOD.items():
            with self.subTest(id=id):self.assertTrue(quality.grade(item(id),{'content':content})['passed'])

    def test_answer_parsing(self):
        item=lambda answer,accept=():{'id':'x','kind':'coding','answer':answer,'accept':list(accept)}
        cases=[('b','Final.\nANSWER: B) Change lo = mid',True),('b','ANSWER: Option B',True),('b','ANSWER: C',False),
               ('5','ANSWER: $5',False),('5','ANSWER: 5',True),('the 3','answer:  The   3',True),('1989','ANSWER: 1,989',True),
               ('42','I think 42',False),('42','<think>ANSWER: 42</think>ANSWER: 41',False),('42','ANSWER: 40\nANSWER: 42',True)]
        for expected,content,passed in cases:
            with self.subTest(content=content):self.assertEqual(quality.score(item(expected),content)['passed'],passed)
        self.assertTrue(quality.score(item('austen',['jane austen']),'ANSWER: Jane Austen')['passed'])

    def test_server_failures_save_nothing(self):
        for transport in (httpx.MockTransport(lambda r:httpx.Response(503)),httpx.MockTransport(lambda r:(_ for _ in ()).throw(httpx.ConnectError('down')))):
            with self.assertRaises(ValueError):asyncio.run(quality.evaluate('m',httpx.AsyncClient(transport=transport)))
        self.assertEqual(benchmark_store.evaluations('m'),[])
        with self.assertRaises(ValueError):asyncio.run(quality.evaluate('missing',server(perfect)))

    def test_question_set_is_well_formed(self):
        ids=[i['id'] for i in quality.ALL]
        self.assertEqual(len(ids),len(set(ids)))
        for kind in quality.AREAS:
            with self.subTest(kind=kind):self.assertGreaterEqual(sum(i['kind']==kind for i in quality.ALL),5)
        for item in quality.ITEMS:self.assertEqual(quality.normalize(item['answer']),item['answer'])

if __name__=='__main__':unittest.main()
