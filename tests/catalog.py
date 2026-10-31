import gzip,json,os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import catalog

SHA='a'*40
SKILLS={'count':2,'items':[
 {'id':'o/r:skills/pdf-tools/SKILL.md','name':'pdf-tools','description':'Merge, split and fill PDF forms.','repo':'o/r','path':'skills/pdf-tools/SKILL.md','sha':SHA,'license':'MIT','stars':900,
  'files':[{'path':'skills/pdf-tools/scripts/merge.py','size':20},{'path':'skills/pdf-tools/../../evil.py','size':5}]},
 {'id':'o/r:skills/seo/SKILL.md','name':'seo-audit','description':'Audit a website for search engine optimisation.','repo':'o/r','path':'skills/seo/SKILL.md','sha':SHA,'license':'MIT','stars':5,'files':[]}]}
CONNECTORS={'count':2,'items':[
 {'id':'io.github.x/notion','name':'Notion','description':'Read and write Notion pages','packages':[{'kind':'npm','identifier':'@x/notion','version':'1.0.0','needs':['NOTION_TOKEN']}],'remotes':[]},
 {'id':'io.github.y/weather','name':'Weather','description':'Weather forecasts','packages':[{'kind':'npm','identifier':'weather-mcp','version':'2.1.0','needs':[]}],'remotes':[]}]}

class Catalog(unittest.TestCase):
    def setUp(self): catalog._CACHE.clear(); catalog._CACHE.update({'skills':SKILLS,'connectors':CONNECTORS})
    def test_search_ranks_by_words_then_popularity(self):
        r=catalog.search('pdf forms')
        self.assertEqual(r['items'][0]['name'],'pdf-tools'); self.assertEqual(r['counts'],{'skills':2,'connectors':2})
        self.assertEqual(catalog.search('weather',kind='connectors')['items'][0]['name'],'Weather')
        self.assertEqual(catalog.search('zzzz')['total'],0)
    def test_connector_needing_a_key_is_not_installable(self):
        rows={r['name']:r for r in catalog.search('',kind='connectors',limit=10)['items']}
        self.assertFalse(rows['Notion']['installable']); self.assertEqual(rows['Notion']['needs'],['NOTION_TOKEN'])
        with self.assertRaises(ValueError): catalog.connector_plan(CONNECTORS['items'][0])
        name,command,args=catalog.connector_plan(CONNECTORS['items'][1])
        self.assertEqual(args,['-y','weather-mcp@2.1.0'])
    def test_skill_install_is_pinned_and_refuses_path_escape(self):
        fetched=[]
        def raw(repo,sha,path): fetched.append((sha,path)); return b'---\nname: pdf-tools\n---\nhi'
        catalog._raw,real=raw,catalog._raw
        catalog.SKILLS=Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(ValueError): catalog.install_skill(SKILLS['items'][0])
            self.assertFalse(any(p.name.startswith('.installing') for p in catalog.SKILLS.iterdir()))
            item={**SKILLS['items'][0],'files':SKILLS['items'][0]['files'][:1]}
            done=catalog.install_skill(item)
        finally: catalog._raw=real
        self.assertTrue(all(sha==SHA for sha,_ in fetched))
        folder=catalog.SKILLS/done['name']
        self.assertTrue((folder/'scripts'/'merge.py').is_file()); self.assertEqual(json.loads((folder/'SOURCE.json').read_text())['license'],'MIT')
    def test_unpinned_entries_are_refused(self):
        with self.assertRaises(ValueError): catalog._raw('o/r','main','SKILL.md')
if __name__=='__main__': unittest.main()
