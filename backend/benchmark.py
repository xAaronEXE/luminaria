"""Bounded generation benchmark; never reports synthetic token counts."""
import json,time,datetime
import httpx
from .config import CONFIG
from .models import registry,save

async def measure(id):
    models=registry(); model=next((m for m in models if m['id']==id),None)
    if not model: raise ValueError('Model not found')
    start=time.monotonic(); first=None; usage={}; timing={}
    body={'model':id,'messages':[{'role':'user','content':'Explain how a hash table works, including collisions, resizing and practical tradeoffs. Write several detailed paragraphs.'}], 'max_tokens':256,'temperature':0,'stream':True,'stream_options':{'include_usage':True},'chat_template_kwargs':{'enable_thinking':False}}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300,connect=10),trust_env=False) as client:
        async with client.stream('POST',CONFIG['endpoint']+'/chat/completions',headers={'Authorization':'Bearer '+CONFIG.get('model_api_key','local-only')},json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith('data: ') or line=='data: [DONE]': continue
                data=json.loads(line[6:]); usage=data.get('usage') or usage; timing=data.get('timings') or timing
                if first is None and any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in data.get('choices',[])): first=time.monotonic()
    elapsed=time.monotonic()-start; count=usage.get('completion_tokens')
    if not count or first is None: raise ValueError('Server did not return token usage; no benchmark score saved')
    result={'test':'Fixed short generation · '+datetime.date.today().isoformat(),'tps':round(count/elapsed,1),'measurement':'end-to-end (includes load and prompt processing)','first_token_seconds':round(first-start,2),'completion_tokens':count,'prompt_tokens':usage.get('prompt_tokens'),'elapsed':round(elapsed,2),'context':model['context']}
    if timing.get('predicted_per_second'): result['decode_tps']=round(timing['predicted_per_second'],1)
    model.setdefault('benchmarks',[]).insert(0,result);save(models);return result
