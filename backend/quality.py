"""Small fixed coding and reasoning check, scored by exact answers. Model output is never executed."""
import datetime,json,re,time
import httpx
from .config import CONFIG
from .models import registry
from .benchmark_store import record_evaluation

VERSION='Quality check v1'
INSTRUCTION='Think it through briefly, then end with one final line in exactly this form:\nANSWER: <answer>'

ITEMS=[
 {'id':'py-filter-sum','kind':'coding','answer':'24','prompt':'What does this Python program print?\n```python\ndef f(xs):\n    out = []\n    for x in xs:\n        if x % 3 == 0:\n            continue\n        out.append(x * 2)\n    return sum(out)\nprint(f([1, 2, 3, 4, 5, 6]))\n```'},
 {'id':'js-default-sort','kind':'coding','answer':'1,10,9','prompt':'What does this JavaScript print?\n```js\nconsole.log([10, 9, 1].sort().join(","))\n```'},
 {'id':'py-word-count','kind':'coding','answer':'the 3','prompt':'What does this Python program print?\n```python\nd = {}\nfor w in "the cat the hat the end".split():\n    d[w] = d.get(w, 0) + 1\nprint(max(d, key=d.get), d["the"])\n```'},
 {'id':'py-slice','kind':'coding','answer':'arnml','prompt':'What does this Python program print?\n```python\ns = "luminaria"\nprint(s[::-2])\n```'},
 {'id':'binary-search-bug','kind':'coding','answer':'b','prompt':'This binary search can loop forever. Which change fixes it? Answer with the letter only.\n```python\ndef find(a, t):\n    lo, hi = 0, len(a)\n    while lo < hi:\n        mid = (lo + hi) // 2\n        if a[mid] < t:\n            lo = mid\n        else:\n            hi = mid\n    return lo\n```\nA) Change `while lo < hi` to `while lo <= hi`\nB) Change `lo = mid` to `lo = mid + 1`\nC) Change `hi = mid` to `hi = mid - 1`\nD) Change `hi = len(a)` to `hi = len(a) - 1`'},
 {'id':'py-doubling','kind':'coding','answer':'10','prompt':'What does this Python program print?\n```python\ni = 1\ncount = 0\nwhile i < 1000:\n    i *= 2\n    count += 1\nprint(count)\n```'},
 {'id':'arrival-time','kind':'reasoning','answer':'17:15','prompt':'A train leaves at 14:40 and the trip takes 2 hours 35 minutes. What time does it arrive? Give the time as HH:MM in 24-hour format.'},
 {'id':'syllogism','kind':'reasoning','answer':'no','prompt':'All bloops are razzies. Some razzies are lazzies. Must some bloops be lazzies? Answer yes or no.'},
 {'id':'bat-ball','kind':'reasoning','answer':'5','prompt':'A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How many cents does the ball cost? Give a number only.'},
 {'id':'inclusion-exclusion','kind':'reasoning','answer':'47','prompt':'How many integers from 1 to 100 inclusive are divisible by 3 or by 5? Give a number only.'},
 {'id':'sequence','kind':'reasoning','answer':'42','prompt':'What number comes next: 2, 6, 12, 20, 30, ? Give a number only.'},
 {'id':'ordering','kind':'reasoning','answer':'cara','prompt':'Ann is taller than Ben. Ben is taller than Cara. Dan is shorter than Cara. Who is the second shortest? Give the name only.'},
]

def normalize(text):
    text=re.sub(r'[*`"\']','',str(text)).strip().lower()
    text=re.sub(r'\s+',' ',text).rstrip('.')
    return re.sub(r'^([a-d])\)$',r'\1',text).strip()

def final_answer(content):
    found=re.findall(r'ANSWER\s*:\s*(.+)',re.sub(r'<think>.*?</think>','',content or '',flags=re.S),re.I)
    return found[-1].strip() if found else None

def score(item,content):
    given=final_answer(content);value=normalize(given) if given is not None else None
    if value and re.fullmatch(r'[a-d]',item['answer']):value=(re.match(r'(?:option )?([a-d])\b',value) or [None,value])[1]
    return {'id':item['id'],'kind':item['kind'],'passed':value==item['answer'],'given':(given or 'No ANSWER line')[:80],'expected':item['answer']}

async def evaluate(id,client=None):
    model=next((m for m in registry() if m['id']==id),None)
    if not model: raise ValueError('Model not found')
    start=time.monotonic(); results=[]
    owned=client is None
    client=client or httpx.AsyncClient(timeout=httpx.Timeout(180,connect=10),trust_env=False)
    try:
        for item in ITEMS:
            body={'model':id,'messages':[{'role':'user','content':item['prompt']+'\n\n'+INSTRUCTION}],'max_tokens':512,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}
            response=await client.post(CONFIG['endpoint']+'/chat/completions',headers={'Authorization':'Bearer '+CONFIG.get('model_api_key','local-only')},json=body)
            if response.status_code>=400: raise ValueError(f'The model server returned {response.status_code}; no quality result saved')
            message=(response.json().get('choices') or [{}])[0].get('message') or {}
            results.append(score(item,message.get('content') or ''))
    except httpx.HTTPError as error:
        raise ValueError('Could not reach the model server; no quality result saved') from error
    finally:
        if owned: await client.aclose()
    tally=lambda kind:{'passed':sum(r['passed'] for r in results if r['kind']==kind),'total':sum(r['kind']==kind for r in results)}
    result={'test':VERSION+' · '+datetime.date.today().isoformat(),'kind':'quality','coding':tally('coding'),'reasoning':tally('reasoning'),
            'items':results,'thinking':False,'temperature':0,'elapsed':round(time.monotonic()-start,1),'model':id,'quantization':model.get('quantization'),'measured_at':time.time(),
            'scope':'12 fixed questions with exact answers. Code is read, not run. A small spot check, not a general quality score.'}
    record_evaluation(id,result); return result
