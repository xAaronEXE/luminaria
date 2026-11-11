import asyncio,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
from contextlib import contextmanager
import httpx
from backend import cloud_sync,config,profiles,identity
from backend.store import Store
class CloudTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.remote={};self.blobs={};self.receipts={};self.calls=0
  self.devices={}
  for name in ['a','b']:
   folder=self.root/name;folder.mkdir();(folder/'Files').mkdir();store=Store(folder/'studio.sqlite3');sync=cloud_sync.CloudSync(store)
   sync.account=AsyncMock(return_value=('account','a'*64));sync.client_factory=lambda **kwargs:httpx.AsyncClient(transport=httpx.MockTransport(self.server),**kwargs)
   self.devices[name]=(folder,store,sync)
 def tearDown(self):
  for _,store,_ in self.devices.values():store.db.close()
  self.tmp.cleanup()
 @contextmanager
 def device(self,name):
  folder,store,sync=self.devices[name]
  with patch.object(config,'DATA',folder),patch.object(config,'BASE_DATA',folder),patch.object(config,'CONFIG_PATH',folder/'config.json'),patch.object(config,'PROFILE_ID','local'),patch.object(profiles,'PATH',folder/'profiles.json'),patch.object(config,'CONFIG',{'workspace':str(folder/'Files'),'output_tokens':4096,'compact_ratio':.8,'compact_keep_turns':4}):yield folder,store,sync
 def server(self,request):
  self.calls+=1;path=request.url.path.removeprefix('/sync/')
  if path=='status':return httpx.Response(200,json={'available':True})
  if path=='records':return httpx.Response(200,json={'records':[{'kind':k.split(':')[0],'id':k.split(':')[1],'version':v['version'],'deleted':v['deleted']} for k,v in sorted(self.remote.items())],'next':None})
  if path.startswith('blobs/'):
   digest=path.split('/')[1]
   if request.method=='PUT':
    data=request.read();assert hashlib.sha256(data).hexdigest()==digest;self.blobs[digest]=data;return httpx.Response(200,json={'hash':digest})
   return httpx.Response(200,content=self.blobs[digest])
  key=path.removeprefix('records/').replace('/',':',1)
  if request.method=='GET':return httpx.Response(200,json=self.remote[key])
  value=json.loads(request.read());mutation=value['mutation']
  if mutation in self.receipts:return httpx.Response(200,json=self.receipts[mutation])
  current=self.remote.get(key,{'version':0})
  if current['version']!=value['base']:return httpx.Response(409,json={'conflict':True})
  version=current['version']+1;self.remote[key]={'version':version,'data':value['data'],'deleted':value['deleted']};self.receipts[mutation]={'version':version};return httpx.Response(200,json={'version':version})
 async def enabled(self,name):
  with self.device(name) as (_,_,sync):await sync.enable(True)
 async def test_two_devices_sync_chats_files_memory_settings_and_profile(self):
  with self.device('a') as (folder,store,sync):
   chat=store.create_chat('Portable chat');first=store.add(chat,{'role':'user','content':'Remember the decision'});store.add(chat,{'role':'assistant','content':'Saved'});store.save_summary(chat,first,'Decision preserved');store.save_memory('Preference','Short replies');store.set_setting('preferences',{'motion':False});profiles.save({'selected':'local','profiles':[{'id':'local','name':'Cloud workspace','provider':'local'}]});(folder/'Files'/'note.txt').write_text('file body');(folder/'Files'/'empty.txt').write_bytes(b'');store.execute('INSERT INTO actions(id,chat,name,args,tier,status,result,created) VALUES(?,?,?,?,?,?,?,?)',('action',chat,'read_file','{}','auto','done','{}',1));await sync.enable(True);await sync.run()
  with self.device('b') as (folder,store,sync):
   await sync.enable(True);result=await sync.run();self.assertFalse(result['conflicts']);self.assertEqual(store.chats()[0]['title'],'Portable chat');self.assertEqual(store.messages(chat)[0]['content'],'Remember the decision');self.assertEqual(store.summary(chat)['through_id'],store.messages(chat)[0]['id']);self.assertEqual(store.memory()[0]['content'],'Short replies');self.assertFalse(store.setting('preferences')['motion']);self.assertEqual(profiles.registry()['profiles'][0]['name'],'Cloud workspace');self.assertEqual((folder/'Files'/'note.txt').read_text(),'file body');self.assertEqual((folder/'Files'/'empty.txt').read_bytes(),b'')
  with self.device('a') as (_,_,sync):before=len(self.receipts);await sync.run();self.assertEqual(len(self.receipts),before)
 async def test_offline_changes_conflict_and_resolution_preserves_recovery_copy(self):
  with self.device('a') as (_,store,sync):id=store.save_memory('Shared','original');await sync.enable(True);await sync.run()
  with self.device('b') as (_,_,sync):await sync.enable(True);await sync.run()
  with self.device('a') as (_,store,sync):store.save_memory('Shared','from A',id=id);await sync.run()
  with self.device('b') as (folder,store,sync):
   store.save_memory('Shared','from B',id=id);r=await sync.run();self.assertEqual(r['conflicts'],1);self.assertEqual(store.memory()[0]['content'],'from B');await sync.resolve('memory:'+id,'cloud');self.assertEqual(store.memory()[0]['content'],'from A');self.assertTrue(list((folder/'cloud-sync-conflicts').glob('*.json')))
 async def test_credentials_permissions_and_model_weights_are_not_exported(self):
  with self.device('a') as (folder,store,sync):
   for name in ['.env','token.json','model.gguf','config.json']:(folder/'Files'/name).write_text('secret')
   config.CONFIG.update(model_api_key='secret',external_tools=True,access_mode='full');store.set_setting('preferences',{'motion':True,'microphone':'private-device'});rows,blobs,excluded=sync.export();self.assertEqual(excluded,4);self.assertFalse(any(k.startswith('file:') for k in rows));self.assertNotIn('secret',json.dumps(rows));self.assertNotIn('microphone',rows['settings:portable']['preferences']);self.assertNotIn('external_tools',rows['settings:portable']['config'])
 async def test_offline_error_preserves_data_and_queue(self):
  with self.device('a') as (_,store,sync):
   store.save_memory('Keep','local');await sync.enable(True)
   def fail(request):raise httpx.ConnectError('offline')
   sync.client_factory=lambda **kwargs:httpx.AsyncClient(transport=httpx.MockTransport(fail),**kwargs)
   with self.assertRaises(ValueError):await sync.run()
   self.assertEqual(store.memory()[0]['content'],'local');self.assertFalse(sync.state('account')['records'])
 async def test_running_tasks_defer_sync(self):
  with self.device('a') as (_,_,sync):await sync.enable(True);sync.busy=lambda:True;self.calls=0;await sync.run();self.assertEqual(self.calls,0)
 def test_remote_path_traversal_and_sensitive_paths_rejected(self):
  with self.device('a') as (folder,_,sync):
   for name in ['../outside','/absolute','C:/outside','a\\b','CON.txt','trailing.']:
    with self.assertRaises(ValueError):cloud_sync.safe_path(folder,name)
   with self.assertRaises(ValueError):sync.apply('file:'+'0'*64,{'scope':'workspace','path':'.env','size':0},False,b'')
 async def test_remote_memory_deletion_propagates(self):
  with self.device('a') as (_,store,sync):id=store.save_memory('Delete','value');await sync.enable(True);await sync.run()
  with self.device('b') as (_,_,sync):await sync.enable(True);await sync.run()
  with self.device('a') as (_,store,sync):store.execute('DELETE FROM memories WHERE id=?',(id,));await sync.run()
  with self.device('b') as (_,store,sync):await sync.run();self.assertFalse(store.memory())
 async def test_account_mismatch_cannot_enable_sync(self):
  with self.device('a') as (_,store,sync),patch.object(identity,'status',AsyncMock(return_value={'signed_in':True,'account':{'id':'other'},'connections':[]})):
   del sync.account
   with self.assertRaisesRegex(ValueError,'Attach'):await sync.enable(True)
 async def test_retry_after_lost_response_does_not_duplicate_a_write(self):
  with self.device('a') as (_,store,sync):
   store.save_memory('Retry','value');await sync.enable(True);failed=False
   def lost(request):
    nonlocal failed
    result=self.server(request)
    if '/records/memory/' in request.url.path and request.method=='PUT' and not failed:failed=True;raise httpx.ReadError('response lost')
    return result
   sync.client_factory=lambda **kwargs:httpx.AsyncClient(transport=httpx.MockTransport(lost),**kwargs)
   with self.assertRaises(ValueError):await sync.run()
   await sync.run();rows=[r for k,r in self.remote.items() if k.startswith('memory:')];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['version'],1)
 async def test_pause_sync_works_offline(self):
  with self.device('a') as (_,_,sync):
   await sync.enable(True);sync.account=AsyncMock(side_effect=ValueError('offline'));await sync.enable(False);self.assertFalse(sync.state('account')['enabled'])
 async def test_remote_actions_are_inert_and_do_not_restore_executing_runs(self):
  with self.device('a') as (_,store,sync):
   chat=store.create_chat('Inert history');store.add(chat,{'role':'user','content':'Test'});store.execute('INSERT INTO actions(id,chat,name,args,tier,status,result,created) VALUES(?,?,?,?,?,?,?,?)',('action',chat,'write_file','{}','approval','running','{}',1));await sync.enable(True);await sync.run()
  with self.device('b') as (_,store,sync):
   await sync.enable(True);await sync.run();self.assertEqual(store.actions(chat)[0]['status'],'interrupted');self.assertFalse(store.rows('SELECT * FROM runs'));self.assertFalse(store.rows('SELECT * FROM schedules'))
 async def test_budget_pause_keeps_data_and_backs_off(self):
  with self.device('a') as (_,store,sync):
   store.save_memory('Safe','local');await sync.enable(True)
   attempts=0
   def exhausted(request):
    nonlocal attempts
    attempts+=1;return httpx.Response(429,json={'budget_exhausted':True})
   sync.client_factory=lambda **kwargs:httpx.AsyncClient(transport=httpx.MockTransport(exhausted),**kwargs)
   with self.assertRaises(ValueError):await sync.run()
   self.assertGreater(sync.state('account')['not_before'],0);await sync.run();self.assertEqual(attempts,1);self.assertEqual(store.memory()[0]['content'],'local')
 async def test_pausing_inflight_sync_cannot_reenable_it(self):
  with self.device('a') as (_,store,sync):
   store.save_memory('Pause','keep local');await sync.enable(True);entered=asyncio.Event();release=asyncio.Event()
   async def slow(request):
    if '/blobs/' in request.url.path:entered.set();await release.wait()
    return self.server(request)
   chat=store.create_chat('File upload pause');store.add(chat,{'role':'user','content':'Test'})
   sync.client_factory=lambda **kwargs:httpx.AsyncClient(transport=httpx.MockTransport(slow),**kwargs)
   task=asyncio.create_task(sync.run());await asyncio.wait_for(entered.wait(),3);await sync.enable(False);release.set()
   with self.assertRaises(ValueError):await task
   self.assertFalse(sync.state('account')['enabled']);self.assertFalse(any(k.startswith('chat:') for k in self.remote))
 async def test_file_deletion_is_recoverable_and_not_resurrected(self):
  with self.device('a') as (folder,_,sync):(folder/'Files'/'delete.txt').write_text('recover me');await sync.enable(True);await sync.run()
  with self.device('b') as (_,_,sync):await sync.enable(True);await sync.run()
  with self.device('a') as (folder,_,sync):(folder/'Files'/'delete.txt').unlink();await sync.run()
  with self.device('b') as (folder,_,sync):
   await sync.run();self.assertFalse((folder/'Files'/'delete.txt').exists());self.assertEqual(next((folder/'cloud-sync-trash').iterdir()).read_text(),'recover me');before=len(self.receipts);await sync.run();self.assertEqual(len(self.receipts),before)
 async def test_cloud_chat_deletion_stays_in_local_trash(self):
  with self.device('a') as (_,store,sync):chat=store.create_chat('Delete chat');store.add(chat,{'role':'user','content':'Retain in trash'});await sync.enable(True);await sync.run()
  with self.device('b') as (_,_,sync):await sync.enable(True);await sync.run()
  with self.device('a') as (_,store,sync):store.execute('UPDATE chats SET archived=2 WHERE id=?',(chat,));store.purge_chat(chat);await sync.run()
  with self.device('b') as (_,store,sync):
   await sync.run();self.assertEqual(store.rows('SELECT archived FROM chats WHERE id=?',(chat,))[0]['archived'],2);self.assertEqual(store.messages(chat)[0]['content'],'Retain in trash');before=len(self.receipts);await sync.run();self.assertEqual(len(self.receipts),before)
 def test_remote_settings_cannot_grant_device_access(self):
  with self.device('a') as (_,store,sync):
   with self.assertRaises(ValueError):sync.apply('settings:portable',{'preferences':{'motion':False},'config':{'external_tools':True}},False)
   self.assertIsNone(store.setting('preferences'));self.assertNotIn('external_tools',config.CONFIG)
 def test_bad_cloud_summary_rolls_back_conversation_import(self):
  import zlib
  with self.device('a') as (_,store,sync):
   chat=store.create_chat('Original');id=store.add(chat,{'role':'user','content':'Keep original'});store.save_summary(chat,id,'Original summary');rows,blobs,_=sync.export();data=rows['chat:'+chat];value=json.loads(zlib.decompress(blobs[data['blob']].read_bytes()));value['chat']['title']='Bad replacement';value['summaries'][0]['through']=999
   with self.assertRaises(IndexError):sync.apply('chat:'+chat,data,False,zlib.compress(cloud_sync.canonical(value)))
   self.assertEqual(store.messages(chat)[0]['content'],'Keep original');self.assertEqual(store.chats()[0]['title'],'Original');self.assertEqual(store.summary(chat)['content'],'Original summary')
if __name__=='__main__':unittest.main()
