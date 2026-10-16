import json,os,tempfile,unittest

FOLDER=tempfile.TemporaryDirectory()
os.environ['STUDIO_DATA']=FOLDER.name
os.environ.setdefault('STUDIO_PORT','3210')

from fastapi.testclient import TestClient
from backend import app as server

class ActionHistoryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(server.app,base_url='http://127.0.0.1:3210',headers={'X-Studio-Token':server.TOKEN})
  cls.client.__enter__()
  store=server.store
  cls.work=store.create_chat('Build the report');cls.old=store.create_chat('Old cleanup')
  rows=[(cls.work,'write_file',{'path':'report.md'},'done',{'text':'Wrote report.md'},1),
        (cls.work,'run_command',{'command':'pytest'},'error',{'text':'2 failed'},2),
        (cls.old,'delete_file',{'path':'100%_done.txt'},'denied',None,3),
        (cls.work,'web_search',{'query':'llama'},'interrupted',None,4)]
  for i,(chat,name,args,status,result,created) in enumerate(rows):
   store.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(f'{i:032x}',chat,name,json.dumps(args),'approve',status,json.dumps(result) if result else None,created))
  store.execute('UPDATE chats SET archived=2 WHERE id=?',(cls.old,))
 @classmethod
 def tearDownClass(cls):
  cls.client.__exit__(None,None,None);FOLDER.cleanup()

 def names(self,query=''):
  r=self.client.get('/api/actions'+query);self.assertEqual(r.status_code,200,r.text);return [a['name'] for a in r.json()]

 def test_lists_every_chat_newest_first(self):
  self.assertEqual(self.names(),['web_search','delete_file','run_command','write_file'])
  row=self.client.get('/api/actions').json()[1]
  self.assertEqual((row['chat_title'],row['chat_place']),('Old cleanup','trash'))

 def test_problem_and_status_filters(self):
  self.assertEqual(self.names('?status=problems'),['web_search','delete_file','run_command'])
  self.assertEqual(self.names('?status=done'),['write_file'])
  self.assertEqual(self.client.get('/api/actions?status=bogus').status_code,400)

 def test_search_matches_tools_arguments_and_titles_literally(self):
  self.assertEqual(self.names('?q=pytest'),['run_command'])
  self.assertEqual(self.names('?q=report'),['web_search','run_command','write_file'])
  self.assertEqual(self.names('?q=100%25_'),['delete_file'])
  self.assertEqual(self.names('?q=%25'),['delete_file'])
  self.assertEqual(self.names('?q=%25_d'),['delete_file'])

 def test_output_is_summarized(self):
  row=next(a for a in self.client.get('/api/actions?status=done').json())
  self.assertEqual(row['output'],'Wrote report.md');self.assertFalse(row['truncated'])
  self.assertEqual(len(self.client.get('/api/actions?limit=2').json()),2)

if __name__=='__main__':unittest.main()
