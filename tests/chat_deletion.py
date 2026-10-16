import os,tempfile,unittest
from pathlib import Path

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
os.environ.setdefault('STUDIO_PORT','3210')

from fastapi.testclient import TestClient
from langgraph.checkpoint.base import empty_checkpoint
from backend import app as server

def seed(store,title):
 chat=store.create_chat(title)
 store.add(chat,{'role':'user','content':'secret '+title})
 store.save_summary(chat,1,'summary of '+title)
 store.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(chat+'-a',chat,'write_file','{}','ask','done',None,0))
 run=chat+'-run'
 store.save_run({'id':run,'chat':chat,'phase':'Finished','finished':True})
 return chat,run

class ChatDeletionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(server.app,base_url='http://127.0.0.1:3210',headers={'X-Studio-Token':server.TOKEN})
  cls.client.__enter__()
 @classmethod
 def tearDownClass(cls):
  cls.client.__exit__(None,None,None);FOLDER.cleanup()

 def checkpoint(self,run):
  saver=server.engine.graph.checkpointer
  config={'configurable':{'thread_id':run,'checkpoint_ns':''}}
  self.client.portal.call(saver.aput,config,empty_checkpoint(),{},{})
  return lambda:self.client.portal.call(saver.aget_tuple,{'configurable':{'thread_id':run}})

 def count(self,table,chat):
  return server.store.rows(f'SELECT COUNT(*) n FROM {table} WHERE chat=?',(chat,))[0]['n']

 def test_only_trashed_chats_can_be_erased_and_everything_goes(self):
  store=server.store;doomed,run=seed(store,'doomed');kept,kept_run=seed(store,'kept')
  saved=self.checkpoint(run);other=self.checkpoint(kept_run)
  self.assertIsNotNone(saved())
  refused=self.client.delete('/api/chats/'+doomed)
  self.assertEqual(refused.status_code,400);self.assertIn('trash',refused.json()['error'])
  self.client.post('/api/chats/'+doomed+'/organize',json={'action':'delete'})
  self.assertEqual(self.client.delete('/api/chats/'+doomed).status_code,200)
  for table in ('messages','summaries','actions','runs'):
   self.assertEqual(self.count(table,doomed),0,table);self.assertEqual(self.count(table,kept),1,table)
  self.assertFalse(store.rows('SELECT id FROM chats WHERE id=?',(doomed,)))
  self.assertFalse((store.data_directory/'runs'/run).exists())
  self.assertTrue((store.data_directory/'runs'/kept_run).exists())
  self.assertIsNone(saved());self.assertIsNotNone(other())
  self.assertEqual(self.client.delete('/api/chats/'+doomed).status_code,404)

 def test_empty_trash_leaves_archived_and_active_chats(self):
  store=server.store
  first,_=seed(store,'one');second,_=seed(store,'two');archived,_=seed(store,'archived');active,_=seed(store,'active')
  for chat in (first,second):self.client.post('/api/chats/'+chat+'/organize',json={'action':'delete'})
  self.client.post('/api/chats/'+archived+'/organize',json={'action':'archive'})
  result=self.client.post('/api/chats/trash/empty')
  self.assertEqual(result.json(),{'deleted':2})
  remaining={r['id'] for r in store.rows('SELECT id FROM chats')}
  self.assertNotIn(first,remaining);self.assertNotIn(second,remaining)
  self.assertIn(archived,remaining);self.assertIn(active,remaining)
  self.assertEqual(self.client.post('/api/chats/trash/empty').json(),{'deleted':0})

 def test_run_folder_cleanup_stays_inside_runs(self):
  store=server.store;chat=store.create_chat('escape')
  outside=Path(FOLDER.name)/'keep-me';outside.mkdir()
  store.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('../keep-me',chat,'{}','Finished',0))
  store.execute('UPDATE chats SET archived=2 WHERE id=?',(chat,))
  store.purge_chat(chat)
  self.assertTrue(outside.is_dir())

if __name__=='__main__':unittest.main()
