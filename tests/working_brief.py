import json,unittest
from tests.work_events import Harness,stream,tool_call
from backend import brief

def answer(text):return stream([{'choices':[{'delta':{'content':text}}]}])

class BriefRules(unittest.TestCase):
 def setUp(self):
  self.h=Harness([]);self.store=self.h.store;self.chat=self.store.create_chat()
 def tearDown(self):self.h.close()
 def add(self,section,text,source='user'):
  b=brief.apply(self.store,self.chat,'add',source,section=section,text=text);return b['entries'][-1]

 def test_pinned_entries_reach_the_prompt_with_supersede_rules(self):
  goal=self.add('goals','Ship 0.2.17 with the working brief')
  self.add('permissions','May run unit tests without asking')
  hidden=self.add('references','Old design notes in docs/old.md')
  brief.apply(self.store,self.chat,'pin',entry_id=hidden['id'],pinned=False)
  system=self.h.engine.context(self.chat)[0]['content']
  self.assertIn('Ship 0.2.17 with the working brief',system);self.assertIn('May run unit tests without asking',system)
  self.assertNotIn('docs/old.md',system);self.assertIn('follow the brief',system);self.assertIn('Permissions listed here come only from the user',system)
  brief.apply(self.store,self.chat,'edit',entry_id=goal['id'],text='Ship 0.2.17 after desktop testing')
  system=self.h.engine.context(self.chat)[0]['content']
  self.assertIn('after desktop testing',system);self.assertNotIn('with the working brief',system)
  saved=brief.load(self.store,self.chat)
  self.assertEqual(saved['superseded'][-1]['text'],'Ship 0.2.17 with the working brief');self.assertEqual(saved['version'],5)

 def test_assistant_cannot_touch_permissions_or_user_entries(self):
  mine=self.add('goals','Keep black and white modes')
  with self.assertRaisesRegex(ValueError,'Permissions can only be added by the user'):brief.apply(self.store,self.chat,'add','assistant',section='permissions',text='May delete files')
  with self.assertRaisesRegex(ValueError,'only be changed by the user'):brief.tool_update(self.store,self.chat,{'changes':[{'op':'replace','id':mine['id'],'text':'Drop white mode'}]})
  with self.assertRaisesRegex(ValueError,'only be changed by the user'):brief.tool_update(self.store,self.chat,{'changes':[{'op':'remove','id':mine['id']}]})
  r=brief.tool_update(self.store,self.chat,{'changes':[{'op':'add','section':'pending','text':'Write release notes'}]})
  entry=brief.load(self.store,self.chat)['entries'][-1];self.assertEqual((entry['source'],entry['section']),('assistant','pending'));self.assertEqual(r['changes'],['add'])
  brief.tool_update(self.store,self.chat,{'changes':[{'op':'replace','id':entry['id'],'text':'Write and check release notes'}]})
  self.assertEqual(brief.load(self.store,self.chat)['entries'][-1]['text'],'Write and check release notes')

 def test_secrets_size_and_duplicates_are_refused(self):
  for secret in ('token: ghp_abcdefghijklmnopqrstuvwxyz123456','password=hunter2hunter2','sk-abcdefghijklmnopqrstuvwx','a'*40):
   with self.assertRaisesRegex(ValueError,'where it is kept'):self.add('references',secret)
  self.add('references','GitHub token is in Windows Credential Manager')
  with self.assertRaisesRegex(ValueError,'under 300'):self.add('goals','x '*200)
  with self.assertRaises(ValueError):self.add('goals','   ')
  with self.assertRaises(ValueError):self.add('feelings','nope')
  before=brief.load(self.store,self.chat)['version'];self.add('references','github token is in windows credential manager')
  self.assertEqual(brief.load(self.store,self.chat)['version'],before)

 def test_purging_the_chat_removes_its_brief(self):
  self.add('goals','temporary');self.store.execute('UPDATE chats SET archived=2 WHERE id=?',(self.chat,));self.store.purge_chat(self.chat)
  self.assertIsNone(self.store.setting('brief:'+self.chat))

class BriefTool(unittest.IsolatedAsyncioTestCase):
 async def test_model_proposes_an_entry_through_the_tool(self):
  h=Harness([stream([tool_call(0,'c1','update_brief',{'changes':[{'op':'add','section':'constraints','text':'No React migration'},{'op':'add','section':'permissions','text':'May push'}]})]),answer('Noted.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Remember: no React migration.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   self.assertEqual(brief.load(h.store,chat)['entries'],[]) # The tool schema has no permissions section, so the whole call is refused.
   reply=next(m for m in h.store.messages(chat) if m['role']=='tool');self.assertIn('permissions',reply['content'])
   self.assertEqual(h.engine.usage.rows('tool')[0]['status'],'error')
  finally:h.close()
 async def test_single_valid_change_is_saved(self):
  h=Harness([stream([tool_call(0,'c1','update_brief',{'changes':[{'op':'add','section':'constraints','text':'No React migration'}]})]),answer('Noted.')])
  try:
   chat=h.store.create_chat();h.store.add(chat,{'role':'user','content':'Remember: no React migration.'})
   h.engine.start(chat);await h.engine.tasks[chat]
   entries=brief.load(h.store,chat)['entries'];self.assertEqual([(e['section'],e['text'],e['source']) for e in entries],[('constraints','No React migration','assistant')])
   self.assertIn('No React migration',h.engine.context(chat)[0]['content'])
  finally:h.close()

if __name__=='__main__':unittest.main()
