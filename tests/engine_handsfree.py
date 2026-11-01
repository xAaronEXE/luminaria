import os,sys,tempfile,types,unittest
os.environ['STUDIO_DATA']=tempfile.mkdtemp()
def stub(name,**attrs):
 m=types.ModuleType(name);m.__dict__.update(attrs);sys.modules.setdefault(name,m);return m
class _Any:
 def __init__(s,*a,**k):pass
 def __getattr__(s,n):return _Any()
 def __call__(s,*a,**k):return _Any()
try:
 import langgraph  # noqa
except ImportError:
 stub('langgraph');stub('langgraph.graph',StateGraph=_Any,START='s',END='e');stub('langgraph.types',interrupt=lambda x:x,Command=_Any)
try:
 import httpx  # noqa
except ImportError:
 stub('httpx',AsyncClient=_Any,Timeout=_Any,HTTPError=Exception,ConnectError=Exception)
from backend import engine as e,config
class HandsFree(unittest.TestCase):
 def setUp(self):config.CONFIG['access_mode']='full'
 def tearDown(self):config.CONFIG['access_mode']='review'
 def test_intent_detection(self):
  for text in ("I'll create the file now.","Let me run that for you","I will now search the folder","I'm going to open it","Found it. Next, I'll write the report.","Let's try to locate the generate_timeline.py file and run it again.","Let's install it."):self.assertTrue(e.Engine.announces(text),text)
  for text in ("Here is the summary.","The file was created.","Done.",
               "The folder contains 8 items. If you need to work with any specific files or directories, please let me know!",
               "Let me know if you want changes.","I can also make a chart if you'd like.","If you want, I'll create a summary next.",
               "Should I run it again?","I'll run the tests now?","Results:\n```\nI'll create the file\n```\nAll done."):self.assertFalse(e.Engine.announces(text),text)
 def test_nudge_is_bounded_and_respects_denials(self):
  eng=e.Engine.__new__(e.Engine)
  self.assertTrue(eng.should_nudge({'announced':True}))
  self.assertFalse(eng.should_nudge({'announced':True,'nudges':2}))
  self.assertFalse(eng.should_nudge({'announced':True,'denied':True}))
  self.assertFalse(eng.should_nudge({'announced':True,'plan_only':True}))
  config.CONFIG['access_mode']='review'
  self.assertTrue(eng.should_nudge({'announced':True}),'Ask me first also follows through; tools still ask for approval')
  self.assertFalse(eng.should_nudge({'announced':False}))
 def test_nudge_is_a_trailing_user_message(self):
  base=[{'role':'system','content':'s'},{'role':'user','content':'u'},{'role':'assistant','content':"I'll do it"}]
  out=e.with_nudge(base,{'nudge_pending':True})
  self.assertEqual(out[-1]['role'],'user');self.assertIn('called no tool',out[-1]['content']);self.assertEqual(len(e.with_nudge(base,{})),3)
if __name__=='__main__':unittest.main()
