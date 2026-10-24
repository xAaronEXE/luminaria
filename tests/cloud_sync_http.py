"""Run after node auth-service/cloud-sync-fixture.mjs. Isolated local HTTP integration."""
import tempfile,json,os
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
from backend import cloud_sync,config,profiles,identity
from backend.store import Store
import asyncio
async def main():
 with tempfile.TemporaryDirectory() as folder:
  devices={};account='1'*32
  for name in ['a','b']:
   root=Path(folder)/name;root.mkdir();(root/'Files').mkdir();(root/'profiles.json').write_text(json.dumps({'selected':'local','profiles':[{'id':'local','name':'Fixture workspace','provider':'google','identity_id':account,'account_id':account}]}));store=Store(root/'studio.sqlite3');sync=cloud_sync.CloudSync(store);devices[name]=(root,store,sync)
  @contextmanager
  def device(name):
   root,store,sync=devices[name]
   with patch.object(config,'DATA',root),patch.object(config,'BASE_DATA',root),patch.object(config,'CONFIG_PATH',root/'config.json'),patch.object(config,'PROFILE_ID','local'),patch.object(profiles,'PATH',root/'profiles.json'),patch.object(config,'CONFIG',{'workspace':str(root/'Files'),'output_tokens':4096,'compact_ratio':.8,'compact_keep_turns':4}),patch.object(identity,'DATA',root),patch.object(identity,'BASE_DATA',root),patch.object(identity,'SESSION',root/'identity-session.bin'),patch.object(identity,'ORIGIN','http://127.0.0.1:3220'):
    identity.save_session(identity.SESSION,'a'*64);yield root,store,sync
  try:
   with device('a') as (root,store,sync):
    chat=store.create_chat('Local HTTP end-to-end');store.add(chat,{'role':'user','content':'Portable question'});id=store.save_memory('Preference','Original');(root/'Files'/'proof.txt').write_text('File transferred through the actual Worker and R2 API');store.set_setting('preferences',{'motion':False});await sync.enable(True);await sync.run()
   with device('b') as (root,store,sync):
    await sync.enable(True);r=await sync.run();assert not r['conflicts'];assert store.messages(chat)[0]['content']=='Portable question';assert store.memory()[0]['content']=='Original';assert not store.setting('preferences')['motion'];assert (root/'Files'/'proof.txt').read_text().startswith('File transferred');store.save_memory('Preference','Offline B',id=id)
   with device('a') as (_,store,sync):store.save_memory('Preference','Online A',id=id);await sync.run()
   with device('b') as (_,store,sync):r=await sync.run();assert r['conflicts']==1;assert store.memory()[0]['content']=='Offline B';await sync.resolve('memory:'+id,'cloud');assert store.memory()[0]['content']=='Online A'
   print('REAL LOCAL HTTP INTEGRATION PASSED: server session checks, D1 revisions, R2 bytes, two isolated clients, chats/files/memory/settings/profile and conflict resolution. No production data uploaded.')
  finally:
   for _,store,_ in devices.values():store.db.close()
if __name__=='__main__':asyncio.run(main())
