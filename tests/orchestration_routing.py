import json,tempfile,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import httpx
from tests.work_events import Harness,stream
from backend import orchestration as o

ROOT=Path(tempfile.mkdtemp())
def model(id,strengths,parameters,variant='standard',active='',vision=False):
 f=ROOT/(id+'.gguf');f.write_bytes(b'x')
 m={'id':id,'name':id,'model_file':str(f),'strengths':strengths,'parameters':parameters,'active_parameters':active,'variant':variant}
 if vision:p=ROOT/(id+'.mmproj');p.write_bytes(b'x');m['projector_file']=str(p)
 return m
MODELS=[model('qwen3-4b',['Reasoning','Writing'],'4.0B'),model('qwen3-14b',['Reasoning','Writing','Tools'],'14.8B'),
 model('coder-7b',['Coding','Tools'],'7.6B'),model('coder-30b',['Coding','Tools'],'30.5B',active='3.3B'),
 model('gemma-12b',['Writing','Reasoning','Vision'],'11.8B',vision=True),
 model('qwen3-8b-abl',['Reasoning','Writing','Tools'],'8.2B','abliterated'),model('coder-7b-abl',['Coding','Tools'],'7.6B','abliterated'),
 {'id':'missing','name':'missing','model_file':str(ROOT/'nope.gguf'),'strengths':['Coding'],'parameters':'70B'}]

def client(reply,calls):
 async def handler(request):
  calls.append(json.loads(request.content))
  return httpx.Response(200,json={'choices':[{'message':{'content':reply}}]})
 return httpx.AsyncClient(transport=httpx.MockTransport(handler))

class PoolTests(unittest.TestCase):
 def test_modes_filter_installed_models(self):
  ids=lambda s:{m['id'] for m in o.pool(MODELS,s)}
  self.assertNotIn('missing',ids(None))
  self.assertEqual(ids({'mode':'abliterated'}),{'qwen3-8b-abl','coder-7b-abl'})
  self.assertNotIn('coder-7b-abl',ids({'mode':'standard'}))
  self.assertEqual(ids({'mode':'custom','models':['coder-7b','missing']}),{'coder-7b'})
 def test_variant_inferred_for_unlabelled_local_files(self):
  self.assertEqual(o.variant({'id':'x','name':'Huihui Qwen'}),'abliterated');self.assertEqual(o.variant({'id':'y','name':'Llama'}),'standard')
 def test_invalid_pools_are_rejected(self):
  for bad in ({'mode':'everything'},{'mode':'custom','models':[]},{'mode':'custom','models':[3]},'all'):
   with self.assertRaises(ValueError):o.normalize_pool(bad)

class ProfileTests(unittest.TestCase):
 def test_greeting_is_quick_and_confident(self):
  p=o.keyword_profile('hey!');self.assertEqual((p['needs'],p['complexity'],p['confident']),(['chat'],'low',True))
 def test_code_fence_is_decisive_coding(self):
  p=o.keyword_profile('Why does this fail?\n```python\nprint(x)\n```');self.assertEqual(p['needs'][0],'coding');self.assertTrue(p['confident'])
 def test_large_project_is_high_complexity(self):
  self.assertEqual(o.keyword_profile('Design a full application from scratch with a python api and a react frontend')['complexity'],'high')

class RankTests(unittest.TestCase):
 def best(self,profile,choices=None,evidence=None):return o.rank(o.pool(choices or MODELS,None),profile,evidence)[0]['id']
 def test_coding_goes_to_a_coding_model(self):
  self.assertIn(self.best({'needs':['coding'],'complexity':'medium'}),('coder-7b','coder-30b','coder-7b-abl'))
 def test_demanding_coding_prefers_the_larger_coder(self):
  self.assertEqual(self.best({'needs':['coding','tools'],'complexity':'high'}),'coder-30b')
 def test_quick_chat_prefers_a_light_model(self):
  self.assertEqual(self.best({'needs':['chat'],'complexity':'low'}),'qwen3-4b')
 def test_measured_quality_changes_the_choice(self):
  base=o.rank(o.pool(MODELS,{'mode':'custom','models':['coder-7b','qwen3-14b']}),{'needs':['reasoning'],'complexity':'medium'},None)[0]['id']
  self.assertEqual(base,'qwen3-14b')
  evidence=lambda id:{'quality':{'reasoning':{'passed':6,'total':6}}} if id=='coder-7b' else {'quality':{'reasoning':{'passed':0,'total':6}}}
  self.assertEqual(o.rank(o.pool(MODELS,{'mode':'custom','models':['coder-7b','qwen3-14b']}),{'needs':['reasoning'],'complexity':'medium'},evidence)[0]['id'],'coder-7b')

class FitTests(unittest.TestCase):
 def test_models_larger_than_gpu_memory_lose_on_normal_tasks(self):
  big=model('fit-big',['Coding','Tools'],'30.5B');Path(big['model_file']).write_bytes(b'x'*4000)
  small=model('fit-small',['Coding','Tools'],'7.6B');Path(small['model_file']).write_bytes(b'x'*1000)
  profile={'needs':['coding'],'complexity':'medium'}
  self.assertEqual(o.rank([big,small],profile,None)[0]['id'],'fit-big')
  ranked=o.rank([big,small],profile,None,vram=2000)
  self.assertEqual(ranked[0]['id'],'fit-small');self.assertTrue(any('GPU memory' in f for f in ranked[1]['factors']))

class ChooseTests(unittest.IsolatedAsyncioTestCase):
 async def test_router_describes_and_scorer_picks_from_pool(self):
  calls=[];c=client('{"needs":["coding"],"complexity":"high","reason":"big refactor"}',calls)
  d=await o.choose(c,'http://x','qwen3-4b',MODELS,'Can you help me restructure how the modules in my project fit together','qwen3-4b',{'mode':'abliterated'})
  self.assertEqual(d['model_id'],'coder-7b-abl');self.assertEqual(d['method'],'router');self.assertTrue(d['router_called'])
  self.assertEqual(len(calls),1);self.assertEqual(calls[0]['model'],'qwen3-4b');self.assertEqual(d['pool_size'],2)
 async def test_obvious_requests_skip_the_router(self):
  calls=[];c=client('{}',calls)
  d=await o.choose(c,'http://x','qwen3-4b',MODELS,'thanks!','qwen3-14b')
  self.assertEqual(calls,[]);self.assertEqual(d['method'],'keywords');self.assertFalse(d['router_called'])
 async def test_bad_router_output_falls_back_to_keywords(self):
  calls=[];c=client('I think you should use a big model',calls)
  d=await o.choose(c,'http://x','qwen3-4b',MODELS,'Write a short story about a lighthouse keeper and summarize it','qwen3-4b')
  self.assertEqual(d['method'],'keywords');self.assertIn(d['model_id'],{m['id'] for m in o.installed(MODELS)})
 async def test_images_restrict_to_vision_models(self):
  d=await o.choose(client('{"needs":["writing"],"complexity":"low"}',[]),'http://x','qwen3-4b',MODELS,'What is in this picture? Describe it nicely for a caption','qwen3-4b',vision=True)
  self.assertEqual(d['model_id'],'gemma-12b')
 async def test_empty_pool_is_an_error(self):
  with self.assertRaises(ValueError):await o.choose(client('{}',[]),'http://x','qwen3-4b',MODELS,'hi','qwen3-4b',{'mode':'custom','models':['missing']})

class EngineTests(unittest.IsolatedAsyncioTestCase):
 async def run_with(self,config):
  from backend import models
  from backend.config import CONFIG
  h=Harness([stream([{'choices':[{'delta':{'content':'ok'}}]}])]*2)
  registry=[MODELS[0],MODELS[2]];chooser=AsyncMock(return_value={'model_id':'coder-7b','reason':'Coding','router_called':False,'method':'keywords'})
  try:
   with patch.dict(CONFIG,{'orchestrator_model':'qwen3-4b',**config}),patch.object(models,'registry',return_value=registry),patch('backend.orchestration.choose',new=chooser):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'fix my code'})
    h.engine.start(chat);await h.engine.tasks[chat]
    return chooser,h.engine.runs[chat],[e['type'] for e in h.work()]
  finally:h.close()
 async def test_auto_off_skips_routing(self):
  chooser,run,types=await self.run_with({'orchestration_enabled':False})
  chooser.assert_not_called();self.assertNotIn('routing.started',types);self.assertNotIn('routing',run)
 async def test_pool_and_evidence_reach_the_router(self):
  pool={'mode':'standard','models':[]}
  chooser,run,types=await self.run_with({'orchestration_enabled':True,'orchestration_pool':pool})
  args=chooser.call_args.args;self.assertEqual(args[6],pool);self.assertTrue(callable(args[7]));self.assertFalse(args[8])
  self.assertEqual(run['model_id'],'coder-7b');self.assertIn('routing.completed',types)

if __name__=='__main__':unittest.main()
