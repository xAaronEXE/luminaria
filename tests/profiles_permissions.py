import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

class ProfileAndPermissionsTests(unittest.TestCase):
 def run_config(self,folder,code):
  env={**os.environ,'STUDIO_DATA':str(folder)}
  p=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,check=True)
  return json.loads(p.stdout)
 def test_permission_change_applies_immediately(self):
  # Access mode is read live: switching takes effect on the next message, with no restart.
  with tempfile.TemporaryDirectory() as tmp:
   a=self.run_config(tmp,"import json;from backend.config import save_config,access_status;save_config({'access_mode':'full'});print(json.dumps(access_status()))")
   self.assertEqual(a,{'active':'full','selected':'full','restart_required':False})
   b=self.run_config(tmp,"import json;from backend.config import save_config,access_status;save_config({'access_mode':'review'});print(json.dumps(access_status()))")
   self.assertEqual(b,{'active':'review','selected':'review','restart_required':False})
   c=self.run_config(tmp,"import json;from backend.config import access_status;print(json.dumps(access_status()))")
   self.assertEqual(c['active'],'review')
 def test_profiles_resolve_separate_history_memory_and_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);profiles=[{'id':'a'*32,'name':'One'},{'id':'b'*32,'name':'Two'}];results=[]
   for profile in profiles:
    (root/'profiles.json').write_text(json.dumps({'selected':profile['id'],'profiles':profiles}))
    code="import json;from backend.config import DATA,CONFIG,PROFILE_ID;from backend.store import Store;s=Store(DATA/'test.sqlite3');s.create_chat(PROFILE_ID);s.save_memory('owner',PROFILE_ID);print(json.dumps({'data':str(DATA),'files':CONFIG['workspace'],'chats':s.chats(),'memory':s.memory()}))"
    results.append(self.run_config(root,code))
   self.assertNotEqual(results[0]['data'],results[1]['data']);self.assertNotEqual(results[0]['files'],results[1]['files'])
   self.assertEqual(results[0]['memory'][0]['content'],'a'*32);self.assertEqual(results[1]['memory'][0]['content'],'b'*32)
if __name__=='__main__':unittest.main()
