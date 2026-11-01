import unittest
from backend import fit
from backend.model_catalog import CATALOG,cache_bytes
from backend.model_catalog_data import REPOS
from backend.hardware import smart_candidates

GB,MB=fit.GB,fit.MB
def pc(vram_gb,ram_gb,name='Test GPU',free=None):
 return fit.machine({'devices':[{'name':name,'total_bytes':int(vram_gb*GB),'free_bytes':int((free or vram_gb-0.6)*GB)}] if vram_gb else [],'ram_bytes':int(ram_gb*GB)})

def plan(model_id,label,hw):
 entry=next(e for e in CATALOG if e['id']==model_id);quant=next(q for q in entry['quants'] if q['label']==label);facts=REPOS[entry['repo']]
 active,total=fit.parse_billions(entry['active_parameters']),fit.parse_billions(entry['parameters'])
 model={'bytes':quant['bytes'],'layers':facts['layers'],'architecture':facts['architecture'],'context_supported':facts['context'],'active_ratio':active/total if active and total else None}
 return fit.estimate(model,hw,lambda c:cache_bytes(facts,c))

class FitEstimateTests(unittest.TestCase):
 def test_small_model_on_mid_gpu_is_recommended_with_long_context(self):
  p=plan('qwen3-8b','Q4_K_M',pc(12,16))
  self.assertEqual((p['rating'],p['placement']),('recommended','gpu'));self.assertGreaterEqual(p['context'],32768)

 def test_moe_model_keeps_attention_on_gpu_and_moves_experts(self):
  p=plan('qwen3-30b-a3b','Q4_K_M',pc(16,32))
  self.assertEqual(p['placement'],'moe');self.assertGreater(p['cpu_moe'],0);self.assertLess(p['cpu_moe'],48)
  dense=plan('qwen3-32b','Q4_K_M',pc(16,32))
  self.assertEqual(dense['placement'],'split');self.assertGreater(p['speed'],dense['speed'])

 def test_too_large_when_memory_runs_out(self):
  self.assertEqual(plan('qwen3-32b','Q6_K',pc(6,16))['rating'],'too_large')

 def test_integrated_graphics_plans_for_cpu(self):
  hw=pc(8,16,name='Intel(R) Iris(R) Xe Graphics');self.assertTrue(hw['integrated'])
  self.assertEqual(plan('qwen3-4b','Q4_K_M',hw)['placement'],'cpu')

 def test_cpu_only_pc_is_rated_and_unknown_gpu_is_not_guessed(self):
  self.assertNotEqual(plan('qwen3-4b','Q4_K_M',pc(0,16))['rating'],'unknown')
  blind=fit.machine({'gpus':[{'name':'Some GPU','vram_bytes':None}],'ram_bytes':32*GB})
  self.assertEqual(plan('qwen3-8b','Q4_K_M',blind)['rating'],'unknown')

 def test_user_override_and_registry_fallback(self):
  hw=fit.machine({'gpus':[{'name':'AMD Radeon RX 7800 XT','vram_bytes':None}],'registry_vram':[{'name':'AMD Radeon RX 7800 XT','vram_bytes':16*GB}],'ram_bytes':32*GB})
  self.assertEqual(hw['vram_total'],16*GB)
  mine=fit.machine({'ram_bytes':32*GB},{'vram_bytes':8*GB});self.assertEqual((mine['vram_total'],mine['source']),(8*GB,'you'))

 def test_measured_speed_outranks_estimate(self):
  estimate=plan('qwen3-14b','Q8_0',pc(16,32))
  self.assertEqual(fit.public(estimate,{'tps':4})['rating'],'slow')
  self.assertTrue(fit.public(estimate,{'tps':30})['measured'])

 def test_more_memory_never_makes_a_rating_worse(self):
  for model_id,label in (('qwen3-14b','Q4_K_M'),('qwen3-30b-a3b','Q4_K_M'),('gemma-3-12b','Q6_K')):
   ranks=[fit.ORDER.index(plan(model_id,label,pc(v,32))['rating']) for v in (6,8,12,16,24)]
   self.assertEqual(ranks,sorted(ranks,reverse=True),(model_id,ranks))

 def test_tuner_measures_around_the_fit_point(self):
  moe=fit.public(plan('qwen3-30b-a3b','Q4_K_M',pc(16,32)));c=smart_candidates({**moe,**moe['settings']},48,8)
  self.assertEqual(c['gpu_layers'],[-1]);self.assertEqual(len(c['cpu_moe']),3);self.assertEqual(c['threads'],[6,8])
  split=fit.public(plan('qwen3-32b','Q4_K_M',pc(16,32)));c=smart_candidates({**split,**split['settings']},64,8)
  self.assertEqual(c['cpu_moe'],[0]);self.assertEqual(len(c['gpu_layers']),3)

if __name__=='__main__':unittest.main()

class ModelLimitTests(unittest.TestCase):
    GB=1024**3
    def hw(self,free=None): return {'gpu':'card','vram_total':16*self.GB,'vram_free':free,'integrated':False,'ram_total':32*self.GB,'cores':8,'source':'llama.cpp'}
    def model(self,size_gb,supported): return {'bytes':int(size_gb*self.GB),'layers':32,'architecture':'llama','context_supported':supported,'active_ratio':None}
    def cache(self,ctx): return int(ctx*0.0001*self.GB)
    def test_short_context_model_is_not_unstable_and_is_disclosed(self):
        out=fit.public(fit.estimate(self.model(4,4096),self.hw(),self.cache))
        self.assertEqual(out['rating'],'recommended');self.assertIn('limit of the model itself, not your PC',out['model_limit'])
    def test_pc_cutting_context_short_is_still_unstable(self):
        big=lambda ctx:int(ctx*0.0012*self.GB)  # heavy context cache: only a sliver fits next to the weights
        out=fit.public(fit.estimate(self.model(13.4,131072),self.hw(),big))
        self.assertIn(out['rating'],('unstable','slow','good'));self.assertEqual(out['model_limit'],'')
    def test_rating_does_not_swing_with_free_memory(self):
        a=fit.estimate(self.model(9,32768),self.hw(None),self.cache)['rating'];b=fit.estimate(self.model(9,32768),self.hw(4*self.GB),self.cache)['rating']
        self.assertEqual(a,b)
