"""Retention across compaction on a realistic long workflow.

The fake summarizer behaves like a weak local model: it writes the named
sections but drops exact file paths and declined actions. The checks verify
what survives anyway: the working brief, restored exact references, recent
turns verbatim, tool-call pairs, a pending approval, and the last good summary
when summarizing fails.
"""
import json,unittest
from unittest.mock import patch
import httpx
from tests.work_events import Harness,stream
from backend import brief
from backend.config import CONFIG
from backend.engine import compact_prefix

FILLER=' '.join(['context']*120)
SUMMARY=('Goal: update the build so the installer packages the backend.\n'
         'Constraints and permissions: keep the user approval flow.\n'
         'Decisions: the build script changes first.\n'
         'Open work: run the packaged app on Windows.\n'
         'Important references: see source messages.')

def seed(store,chat,turns=14):
 add=lambda m:store.add(chat,m)
 add({'role':'user','content':'Goal: update build.ps1 so PyInstaller collects ddgs and primp. '+FILLER})
 add({'role':'assistant','content':'I will read build.ps1 first. '+FILLER})
 add({'role':'user','content':'Correction: the entry point is backend/app.py, not server.py. '+FILLER})
 add({'role':'assistant','content':None,'tool_calls':[{'id':'w1','type':'function','function':{'name':'write_file','arguments':json.dumps({'path':'server.py','content':'x'})}}]})
 add({'role':'tool','tool_call_id':'w1','content':'Action 0123456789abcdef0123456789abcdef: {"denied": true, "message": "User declined or approval expired. Do not bypass this decision."}'})
 add({'role':'assistant','content':None,'tool_calls':[{'id':'r1','type':'function','function':{'name':'run_command','arguments':json.dumps({'command':'pytest'})}}]})
 add({'role':'tool','tool_call_id':'r1','content':'Process interrupted. Action outcome unknown; inspect files/state before retrying. Do not assume it executed.'})
 for i in range(turns):
  add({'role':'user','content':f'Step {i}: keep going with docs/release-notes/0.2.17.md and check tests/usage_insights.py. '+FILLER})
  add({'role':'assistant','content':f'Step {i} done. '+FILLER})

class Model:
 """Routes summarizer requests and normal turns; counts tokens as bytes/4."""
 def __init__(self,summary=SUMMARY,fail=False):
  self.summary=summary;self.fail=fail;self.summaries=0;self.turns=0;self.fragments=[]
 async def __call__(self,request):
  body=json.loads(request.content)
  if body['messages'][0]['content'].startswith('Summarize this conversation'):
   self.summaries+=1;self.fragments.append(json.loads(body['messages'][1]['content'])['source_messages'])
   return stream([{'choices':[{'delta':{'content':'no sections here, just words words words words' if self.fail else self.summary}}]}])
  self.turns+=1
  return stream([{'choices':[{'delta':{'content':'Continuing with the pending work.'}}]}])

async def count(messages,definitions=None):
 return len(json.dumps(messages,ensure_ascii=False))//4+len(json.dumps(definitions or []))//4,'test estimate'

def harness(model):
 h=Harness([]);h.engine.client=httpx.AsyncClient(transport=httpx.MockTransport(model));h.engine.token_count=count
 return h

SMALL={'context':12000,'output_tokens':512,'compact_ratio':0.8,'compact_keep_turns':2}

class LongWorkflow(unittest.IsolatedAsyncioTestCase):
 async def test_details_survive_two_compactions(self):
  model=Model();h=harness(model)
  try:
   with patch.dict(CONFIG,SMALL):
    chat=h.store.create_chat();seed(h.store,chat)
    brief.apply(h.store,chat,'add','user',section='permissions',text='May run unit tests without asking')
    brief.apply(h.store,chat,'add','user',section='pending',text='Test the packaged installer on Windows')
    h.store.add(chat,{'role':'user','content':'Continue.'})
    h.engine.start(chat);await h.engine.tasks[chat]
    run=h.engine.runs[chat];self.assertEqual(run['phase'],'Complete',run.get('error'))
    first=h.store.summary(chat);self.assertIsNotNone(first)
    for exact in ('build.ps1','backend/app.py','docs/release-notes/0.2.17.md','tests/usage_insights.py','Declined by the user: action 0123456789abcdef0123456789abcdef'):
     self.assertIn(exact,first['content'],exact)
    self.assertIn('Source messages: 1 through',first['content']);self.assertIn('summarized in',first['content'])
    self.assertGreater(model.summaries,1);self.assertTrue(all('–' in f or f.isdigit() or 'part' in f for f in model.fragments))
    system=h.engine.context(chat)[0]['content']
    self.assertIn('May run unit tests without asking',system);self.assertIn('Test the packaged installer on Windows',system)
    recent=h.store.messages(chat,first['through_id'])
    self.assertEqual(recent[-1]['content'],'Continuing with the pending work.');self.assertIn('Continue.',[m['content'] for m in recent])
    answered={m.get('tool_call_id') for m in recent if m['role']=='tool'}
    self.assertTrue(all(c['id'] in answered for m in recent for c in m.get('tool_calls') or []))
    metrics=[r for r in h.engine.usage.rows('compaction') if r['status']=='done']
    self.assertTrue(metrics);m=metrics[0]['data']
    self.assertLess(m['tokens_after'],m['tokens_before']);self.assertGreater(m['chunks'],1);self.assertGreaterEqual(m['restored'],4)

    # Second round: more work, then compaction again. Earlier exact details must not drift away.
    for i in range(14,26):
     h.store.add(chat,{'role':'user','content':f'Step {i}: more work. '+FILLER});h.store.add(chat,{'role':'assistant','content':f'Step {i} done. '+FILLER})
    h.store.add(chat,{'role':'user','content':'Continue again.'})
    h.engine.start(chat);await h.engine.tasks[chat]
    second=h.store.summary(chat);self.assertGreater(second['through_id'],first['through_id'])
    for exact in ('build.ps1','backend/app.py','Declined by the user: action 0123456789abcdef0123456789abcdef'):
     self.assertIn(exact,second['content'],exact)
    self.assertIn('May run unit tests without asking',h.engine.context(chat)[0]['content'])
    self.assertEqual(len(h.store.messages(chat)),len({m['id'] for m in h.store.messages(chat)})) # Nothing deleted or duplicated.
    self.assertEqual(h.store.messages(chat)[0]['content'][:12],'Goal: update')
    self.assertEqual(h.engine.usage.compaction()['failed'],0)
  finally:h.close()

 async def test_failed_summary_keeps_history_and_the_task_continues_when_it_fits(self):
  model=Model(fail=True);h=harness(model)
  try:
   with patch.dict(CONFIG,{**SMALL,'context':16000,'compact_ratio':0.3}):
    chat=h.store.create_chat();seed(h.store,chat,turns=6);before=len(h.store.messages(chat))
    h.store.add(chat,{'role':'user','content':'Continue.'})
    h.engine.start(chat);await h.engine.tasks[chat]
    run=h.engine.runs[chat];self.assertEqual(run['phase'],'Complete',run.get('error'))
    self.assertIsNone(h.store.summary(chat));self.assertEqual(len(h.store.messages(chat)),before+2)
    self.assertEqual(model.summaries,2) # One retry, then give up.
    failed=h.engine.usage.compaction();self.assertEqual((failed['failed'],failed['completed']),(1,0));self.assertIn('no sections',failed['recent'][0]['reason'])
  finally:h.close()

 async def test_a_previous_good_summary_survives_a_failed_one(self):
  model=Model();h=harness(model)
  try:
   with patch.dict(CONFIG,SMALL):
    chat=h.store.create_chat();seed(h.store,chat)
    first=await h.engine.compact(chat,force=True)
    self.assertTrue(first['compacted']);saved=h.store.summary(chat)
    for i in range(6):h.store.add(chat,{'role':'user','content':f'later {i} '+FILLER});h.store.add(chat,{'role':'assistant','content':'ok'})
    model.fail=True
    with self.assertRaisesRegex(ValueError,'validation failed'):await h.engine.compact(chat,force=True)
    self.assertEqual(h.store.summary(chat)['id'],saved['id'])
  finally:h.close()

 async def test_one_input_too_large_is_explained(self):
  h=harness(Model())
  try:
   with patch.dict(CONFIG,{**SMALL,'context':4096}):
    chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'x'*40000})
    h.engine.start(chat);await h.engine.tasks[chat]
    run=h.engine.runs[chat];self.assertEqual(run['phase'],'Error')
    self.assertIn('the latest message',run['error']);self.assertIn('4,096',run['error']);self.assertIn('Full history is saved',run['error'])
  finally:h.close()

class Boundaries(unittest.TestCase):
 def test_cut_never_passes_an_unanswered_tool_call(self):
  msgs=[{'id':1,'role':'user','content':'a'},{'id':2,'role':'assistant','content':'b'},{'id':3,'role':'user','content':'c'},
   {'id':4,'role':'assistant','content':None,'tool_calls':[{'id':'p1'}]},{'id':5,'role':'user','content':'d'},{'id':6,'role':'assistant','content':'e'},{'id':7,'role':'user','content':'f'}]
  self.assertEqual([m['id'] for m in compact_prefix(msgs,keep_turns=1)],[1,2])
  msgs.insert(4,{'id':45,'role':'tool','tool_call_id':'p1','content':'ok'})
  self.assertEqual([m['id'] for m in compact_prefix(msgs,keep_turns=1)],[1,2,3,4,45,5,6])

if __name__=='__main__':unittest.main()
