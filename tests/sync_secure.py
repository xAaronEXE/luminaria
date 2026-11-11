import asyncio,json,tempfile,unittest
from pathlib import Path
from backend import sync_secure as S

class Keys(unittest.TestCase):
    def test_key_round_trip_and_typos(self):
        key=S.new_key(); text=S.format_key(key)
        self.assertEqual(len(text.split('-')),S.KEY_GROUPS)
        self.assertEqual(S.parse_key(text),key)
        self.assertEqual(S.parse_key(text.lower().replace('-',' ')),key,'case and spacing do not matter')
        broken=list(text); i=next(i for i,c in enumerate(broken) if c not in '-'); broken[i]='A' if broken[i]!='A' else 'B'
        with self.assertRaises(ValueError): S.parse_key(''.join(broken))
        with self.assertRaises(ValueError): S.parse_key('hello')
    def test_key_id_is_stable_and_reveals_nothing(self):
        key=S.new_key(); self.assertEqual(S.key_id(key),S.key_id(key)); self.assertNotIn(key.hex()[:10],S.key_id(key))

class Encrypted(unittest.TestCase):
    def test_folder_round_trip_hides_content_and_names(self):
        async def go():
            with tempfile.TemporaryDirectory() as d:
                key=S.new_key(); store=S.EncryptedStore(key,S.FolderStore(d,S.key_id(key)))
                src=Path(d)/'secret plans.txt'; src.write_text('the launch date is March 3')
                import hashlib; digest=hashlib.sha256(src.read_bytes()).hexdigest()
                local='file:abc'; data={'scope':'workspace','path':'Projects/secret plans.txt','blob':digest,'size':26}
                v=await store.put(local,0,data,False,src); self.assertEqual(v,1)
                on_disk=' '.join(p.read_text(errors='ignore') for p in Path(d).rglob('*') if p.is_file() and p.suffix in ('.json','.bin'))
                for leak in ('secret plans','launch date','Projects','workspace',digest): self.assertNotIn(leak,on_disk)
                remote=S.remote_name(key,local); rows=await store.records(); self.assertEqual(rows[remote]['version'],1)
                row=await store.get(remote); self.assertEqual((row['key'],row['data']['path']),(local,'Projects/secret plans.txt'))
                self.assertEqual(await store.get_blob(row),src.read_bytes()); self.assertNotIn('remote_blob',row['data'])
                with self.assertRaises(S.Conflict): await store.put(local,0,data,False,src)
                self.assertEqual(await store.put(local,1,data,True),2)
                other=S.EncryptedStore(S.new_key(),S.FolderStore(d,S.key_id(key)))
                with self.assertRaises(ValueError): await other.get(remote)
        asyncio.run(go())
    def test_sync_program_conflict_copies_are_ignored(self):
        async def go():
            with tempfile.TemporaryDirectory() as d:
                key=S.new_key(); folder=S.FolderStore(d,S.key_id(key)); store=S.EncryptedStore(key,folder)
                await store.put('memory:m1',0,{'title':'x'},False)
                original=next((folder.root/'records').glob('*.json'))
                (folder.root/'records'/(original.stem+' (1).json')).write_text(original.read_text())
                (folder.root/'records'/(original.stem+'-LAPTOP.json')).write_text(original.read_text())
                (folder.root/'records'/'memory.half.json.ab12.tmp').write_text('{')
                self.assertEqual(len(await store.records()),1)
        asyncio.run(go())
    def test_swapped_record_is_rejected(self):
        async def go():
            with tempfile.TemporaryDirectory() as d:
                key=S.new_key(); folder=S.FolderStore(d,S.key_id(key)); store=S.EncryptedStore(key,folder)
                await store.put('memory:a',0,{'t':'a'},False); await store.put('memory:b',0,{'t':'b'},False)
                a,b=(folder._record_path(S.remote_name(key,k)) for k in ('memory:a','memory:b'))
                b.write_text(a.read_text())
                with self.assertRaises(ValueError): await store.get(S.remote_name(key,'memory:b'))
        asyncio.run(go())

if __name__=='__main__':unittest.main()
