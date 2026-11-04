"""AI score: a fixed test of a model's overall ability across six areas, run on this PC and graded automatically.
Reasoning, math, coding, knowledge, following instructions and tool use each count equally toward a score out of 100.
Every question has one checkable answer. Model output is never executed; tool calls are only read, never run."""
import datetime,json,re,time
import httpx
from .config import CONFIG
from .models import registry
from .benchmark_store import record_evaluation

VERSION='AI score v2'
INSTRUCTION='Think it through briefly, then end with one final line in exactly this form:\nANSWER: <answer>'
AREAS={'reasoning':'Reasoning','math':'Math','coding':'Coding','knowledge':'Knowledge','instructions':'Following instructions','tools':'Tool use'}

# Answer questions: graded on the final "ANSWER:" line. 'answer' is the expected value; 'accept' lists other correct spellings.
ITEMS=[
 # Reasoning
 {'id':'arrival-time','kind':'reasoning','answer':'17:15','prompt':'A train leaves at 14:40 and the trip takes 2 hours 35 minutes. What time does it arrive? Give the time as HH:MM in 24-hour format.'},
 {'id':'syllogism','kind':'reasoning','answer':'no','prompt':'All bloops are razzies. Some razzies are lazzies. Must some bloops be lazzies? Answer yes or no.'},
 {'id':'bat-ball','kind':'reasoning','answer':'5','prompt':'A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How many cents does the ball cost? Give a number only.'},
 {'id':'sequence','kind':'reasoning','answer':'42','prompt':'What number comes next: 2, 6, 12, 20, 30, ? Give a number only.'},
 {'id':'ordering','kind':'reasoning','answer':'cara','prompt':'Ann is taller than Ben. Ben is taller than Cara. Dan is shorter than Cara. Who is the second shortest? Give the name only.'},
 {'id':'knights','kind':'reasoning','answer':'a','prompt':'On an island, knights always tell the truth and knaves always lie. A says: "B is a knave." B says: "A and I are the same kind." Which one is the knight? Answer A or B.'},
 # Math
 {'id':'discount','kind':'math','answer':'66','prompt':'A jacket costs $80. It is discounted by 25%, then the sale price is raised by 10%. What is the final price in dollars? Give a number only.'},
 {'id':'fractions','kind':'math','answer':'19/12','prompt':'What is 3/4 + 5/6? Give the answer as a fraction in lowest terms.'},
 {'id':'machines','kind':'math','answer':'3','prompt':'Three machines make 3 widgets in 3 minutes. How many minutes do 100 machines need to make 100 widgets? Give a number only.'},
 {'id':'dice','kind':'math','answer':'1/6','prompt':'Two fair six-sided dice are rolled. What is the probability that the sum is 7? Give a fraction in lowest terms.'},
 {'id':'equation','kind':'math','answer':'17','prompt':'Solve for x: 3(x - 4) = 2x + 5. Give a number only.'},
 {'id':'inclusion-exclusion','kind':'math','answer':'47','prompt':'How many integers from 1 to 100 inclusive are divisible by 3 or by 5? Give a number only.'},
 # Coding
 {'id':'py-filter-sum','kind':'coding','answer':'24','prompt':'What does this Python program print?\n```python\ndef f(xs):\n    out = []\n    for x in xs:\n        if x % 3 == 0:\n            continue\n        out.append(x * 2)\n    return sum(out)\nprint(f([1, 2, 3, 4, 5, 6]))\n```'},
 {'id':'js-default-sort','kind':'coding','answer':'1,10,9','prompt':'What does this JavaScript print?\n```js\nconsole.log([10, 9, 1].sort().join(","))\n```'},
 {'id':'py-word-count','kind':'coding','answer':'the 3','prompt':'What does this Python program print?\n```python\nd = {}\nfor w in "the cat the hat the end".split():\n    d[w] = d.get(w, 0) + 1\nprint(max(d, key=d.get), d["the"])\n```'},
 {'id':'py-slice','kind':'coding','answer':'arnml','prompt':'What does this Python program print?\n```python\ns = "luminaria"\nprint(s[::-2])\n```'},
 {'id':'binary-search-bug','kind':'coding','answer':'b','prompt':'This binary search can loop forever. Which change fixes it? Answer with the letter only.\n```python\ndef find(a, t):\n    lo, hi = 0, len(a)\n    while lo < hi:\n        mid = (lo + hi) // 2\n        if a[mid] < t:\n            lo = mid\n        else:\n            hi = mid\n    return lo\n```\nA) Change `while lo < hi` to `while lo <= hi`\nB) Change `lo = mid` to `lo = mid + 1`\nC) Change `hi = mid` to `hi = mid - 1`\nD) Change `hi = len(a)` to `hi = len(a) - 1`'},
 {'id':'py-mutable-default','kind':'coding','answer':'[1, 2]','accept':['[1,2]'],'prompt':'What does this Python program print?\n```python\ndef add(x, items=[]):\n    items.append(x)\n    return items\nadd(1)\nprint(add(2))\n```'},
 # Knowledge
 {'id':'gold','kind':'knowledge','answer':'au','prompt':'What is the chemical symbol for gold?'},
 {'id':'australia','kind':'knowledge','answer':'canberra','prompt':'What is the capital city of Australia?'},
 {'id':'berlin-wall','kind':'knowledge','answer':'1989','prompt':'In what year did the Berlin Wall fall? Give the year only.'},
 {'id':'austen','kind':'knowledge','answer':'austen','accept':['jane austen'],'prompt':'Who wrote the novel "Pride and Prejudice"? Give the author\'s last name.'},
 {'id':'carbon','kind':'knowledge','answer':'carbon','prompt':'Which chemical element has atomic number 6?'},
 {'id':'http-404','kind':'knowledge','answer':'404','prompt':'Which HTTP status code means "Not Found"? Give the number only.'},
]

def _plain(content):
    """The reply without any thinking block or code fences around it."""
    text=re.sub(r'<think>.*?</think>','',content or '',flags=re.S).strip()
    return re.sub(r'^```[a-z]*\s*|\s*```$','',text).strip()

def _words(text): return re.findall(r"[A-Za-z']+",text)

def _json_is(text,expected):
    try: return json.loads(_plain(text))==expected
    except ValueError: return False

def _lines_ok(text):
    lines=[l.strip() for l in _plain(text).splitlines() if l.strip()]
    return len(lines)==3 and not any(re.match(r'^([-*•]|\d+[.)])',l) for l in lines) and all(len(_words(l))<=3 for l in lines)

# Following instructions: graded by checking the reply itself.
CHECKED=[
 {'id':'only-ok','kind':'instructions','prompt':'Reply with only the word OK in capital letters. Nothing else.','check':lambda t:_plain(t)=='OK'},
 {'id':'three-lines','kind':'instructions','prompt':'List exactly three fruits, one per line, with no numbers, bullets or other text.','check':_lines_ok},
 {'id':'no-letter-e','kind':'instructions','prompt':'Write one sentence of at least six words about the ocean without using the letter "e" anywhere. Reply with the sentence only.',
  'check':lambda t:bool(_plain(t)) and 'e' not in _plain(t).lower() and len(_words(_plain(t)))>=6},
 {'id':'json-only','kind':'instructions','prompt':'Give a JSON object with the keys "name" and "age" for a person named Mia who is 7 years old. "age" must be a number. Output only the JSON.',
  'check':lambda t:_json_is(t,{'name':'Mia','age':7})},
 {'id':'four-caps','kind':'instructions','prompt':'Describe a sunrise in exactly four words, all in capital letters. Reply with those four words only.',
  'check':lambda t:len(_words(_plain(t)))==4 and all(w.isupper() for w in _words(_plain(t)))},
 {'id':'two-exclaims','kind':'instructions','prompt':'Write exactly two sentences about rain. Both must end with an exclamation mark, and use no other sentence-ending punctuation.',
  'check':lambda t:_plain(t).count('!')==2 and _plain(t).endswith('!') and not re.search(r'[.?]',_plain(t))},
]

def _fn(name,description,props,required):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':props,'required':required}}}
TOOLS=[
 _fn('get_weather','Current weather for a city.',{'city':{'type':'string'}},['city']),
 _fn('add_event','Add an event to the calendar.',{'title':{'type':'string'},'date':{'type':'string','description':'YYYY-MM-DD'},'time':{'type':'string','description':'HH:MM, 24-hour'}},['title','date','time']),
 _fn('convert_currency','Convert an amount of money between currencies.',{'amount':{'type':'number'},'from_currency':{'type':'string','description':'ISO code, e.g. USD'},'to_currency':{'type':'string','description':'ISO code, e.g. EUR'}},['amount','from_currency','to_currency']),
 _fn('search_files','Search the user\'s files by text.',{'query':{'type':'string'}},['query']),
 _fn('send_email','Send an email.',{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},['to','subject','body']),
]
def _low(v): return str(v or '').strip().lower()
def _num(v):
    try: return float(str(v).replace(',',''))
    except ValueError: return None

# Tool use: graded on the tool call the model makes (never run), or on answering without one when no tool is needed.
CALLS=[
 {'id':'weather','kind':'tools','prompt':'What is the weather like in Paris right now?','call':'get_weather','args':lambda a:'paris' in _low(a.get('city'))},
 {'id':'calendar','kind':'tools','prompt':'Add "Dentist" to my calendar on 2026-03-14 at 15:30.','call':'add_event',
  'args':lambda a:'dentist' in _low(a.get('title')) and _low(a.get('date'))=='2026-03-14' and _low(a.get('time')).startswith('15:30')},
 {'id':'currency','kind':'tools','prompt':'How much is 250 US dollars in euros?','call':'convert_currency',
  'args':lambda a:_num(a.get('amount'))==250 and _low(a.get('from_currency'))=='usd' and _low(a.get('to_currency'))=='eur'},
 {'id':'right-tool','kind':'tools','prompt':'Find my documents that mention the quarterly budget.','call':'search_files','args':lambda a:'budget' in _low(a.get('query'))},
 {'id':'email','kind':'tools','prompt':'Email sam@example.com with the subject "Lunch" and tell him I am running 10 minutes late.','call':'send_email',
  'args':lambda a:_low(a.get('to'))=='sam@example.com' and 'lunch' in _low(a.get('subject')) and '10' in _low(a.get('body'))},
 {'id':'no-tool-needed','kind':'tools','prompt':'What is 12 times 12? Answer directly.','call':None,'answer':'144'},
]

ALL=ITEMS+CHECKED+CALLS

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
    if value and re.fullmatch(r'\d+',item['answer']):value=value.replace(',','')
    passed=value is not None and value in [item['answer']]+[normalize(a) for a in item.get('accept',[])]
    return {'id':item['id'],'kind':item['kind'],'passed':passed,'given':(given or 'No ANSWER line')[:80],'expected':item['answer']}

def _calls(message):
    """Tool calls from the model: native ones, or a JSON call written in the text (as Luminaria also accepts)."""
    out=[]
    for c in message.get('tool_calls') or []:
        f=c.get('function') or {}; args=f.get('arguments')
        try: args=json.loads(args) if isinstance(args,str) else (args or {})
        except ValueError: args={}
        out.append((f.get('name'),args if isinstance(args,dict) else {}))
    if not out:
        for m in re.finditer(r'\{[^{}]*"name"\s*:\s*"(\w+)"[^{}]*"arguments"\s*:\s*(\{[^{}]*\})',_plain(message.get('content'))):
            try: out.append((m.group(1),json.loads(m.group(2))))
            except ValueError: pass
    return out

def grade(item,message):
    content=message.get('content') or ''
    if 'check' in item:
        passed=bool(item['check'](content))
        return {'id':item['id'],'kind':item['kind'],'passed':passed,'given':_plain(content)[:80] or 'No reply','expected':'Follows the instruction exactly'}
    if 'call' in item:
        calls=_calls(message)
        if item['call'] is None:
            passed=not calls and '144' in _plain(content)
            return {'id':item['id'],'kind':'tools','passed':passed,'given':(f'Called {calls[0][0]}' if calls else _plain(content)[:80]),'expected':'Answers without a tool'}
        hit=next((a for n,a in calls if n==item['call']),None)
        passed=hit is not None and bool(item['args'](hit))
        given=', '.join(f'{n}({json.dumps(a)[:60]})' for n,a in calls) or 'No tool call'
        return {'id':item['id'],'kind':'tools','passed':passed,'given':given[:80],'expected':f'Calls {item["call"]} with the right details'}
    return score(item,content)

def body_for(item,id):
    base={'model':id,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}
    if 'call' in item: return {**base,'messages':[{'role':'user','content':item['prompt']}],'tools':TOOLS,'tool_choice':'auto','max_tokens':384}
    if 'check' in item: return {**base,'messages':[{'role':'user','content':item['prompt']}],'max_tokens':256}
    return {**base,'messages':[{'role':'user','content':item['prompt']+'\n\n'+INSTRUCTION}],'max_tokens':640}

def summarize(results):
    areas={k:{'label':AREAS[k],'passed':sum(r['passed'] for r in results if r['kind']==k),'total':sum(r['kind']==k for r in results)} for k in AREAS}
    shares=[a['passed']/a['total'] for a in areas.values() if a['total']]
    return areas,round(100*sum(shares)/len(shares)) if shares else 0

async def evaluate(id,client=None):
    model=next((m for m in registry() if m['id']==id),None)
    if not model: raise ValueError('Model not found')
    start=time.monotonic(); results=[]
    owned=client is None
    client=client or httpx.AsyncClient(timeout=httpx.Timeout(180,connect=10),trust_env=False)
    try:
        for item in ALL:
            response=await client.post(CONFIG['endpoint']+'/chat/completions',headers={'Authorization':'Bearer '+CONFIG.get('model_api_key','local-only')},json=body_for(item,id))
            if response.status_code>=400: raise ValueError(f'The model server returned {response.status_code}; no score saved')
            results.append(grade(item,(response.json().get('choices') or [{}])[0].get('message') or {}))
    except httpx.HTTPError as error:
        raise ValueError('Could not reach the model server; no score saved') from error
    finally:
        if owned: await client.aclose()
    areas,overall=summarize(results)
    result={'test':VERSION+' · '+datetime.date.today().isoformat(),'kind':'quality','version':2,'score':overall,'areas':areas,
            'coding':{k:areas['coding'][k] for k in ('passed','total')},'reasoning':{k:areas['reasoning'][k] for k in ('passed','total')},
            'items':results,'thinking':False,'temperature':0,'elapsed':round(time.monotonic()-start,1),'model':id,'quantization':model.get('quantization'),'measured_at':time.time(),
            'scope':f'{len(ALL)} fixed questions in six areas, each counting equally, graded automatically on this PC. Code is read, not run; tool calls are checked, never run.'}
    record_evaluation(id,result); return result
