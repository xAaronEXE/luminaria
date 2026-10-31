import unittest,tempfile,os
from unittest.mock import patch
os.environ.setdefault('STUDIO_DATA',tempfile.mkdtemp())
from backend import marketplace as m
SAMPLE={'servers':[{'server':{'name':'io.github.acme/weather','description':'Weather','packages':[{'registryType':'npm','identifier':'@acme/weather','version':'1.2.0','environmentVariables':[]}]}},
 {'server':{'name':'io.github.acme/keyed','description':'Needs key','packages':[{'registryType':'pypi','identifier':'keyed','environmentVariables':[{'name':'API_KEY','isRequired':True}]}]}},
 {'server':{'name':'io.github.acme/remote','description':'Hosted','remotes':[{'url':'https://x.example/mcp'}]}}],'metadata':{'nextCursor':'abc'}}
class Market(unittest.TestCase):
 def test_registry_parsing(self):
  with patch.object(m,'_get',return_value=SAMPLE),patch.object(m,'CACHE',__import__("pathlib").Path(tempfile.mkdtemp())):
   r=m.search_mcp('acme')
  self.assertEqual([i['installable'] for i in r['items']],[True,True,False]);self.assertEqual(r['next'],'abc')
  self.assertEqual(r['items'][1]['packages'][0]['needs'],['API_KEY'])
 def test_connector_command(self):
  name,cmd,args=m.connector_for('io.github.acme/weather',{'kind':'npm','identifier':'@acme/weather','version':'1.2.0'})
  self.assertEqual(name,'m_weather');self.assertIn('npx',cmd);self.assertEqual(args,['-y','@acme/weather@1.2.0'])
 def test_skill_listing_and_describe(self):
  tree={'tree':[{'type':'blob','path':'skills/pdf/SKILL.md'},{'type':'blob','path':'skills/pdf/other.py'},{'type':'blob','path':'README.md'}]}
  with patch.object(m,'_get',return_value=tree),patch.object(m,'CACHE',__import__("pathlib").Path(tempfile.mkdtemp())):
   rows=m.repo_skills('a/b')
  self.assertEqual([r['name'] for r in rows],['pdf'])
  self.assertEqual(m.describe('---\nname: x\ndescription: Does things\n---\n# X'),'Does things')
 def test_rejects_bad_input(self):
  for bad in ('../x','a/b/c',''):
   with self.assertRaises(ValueError):m.valid_repo(bad)
  with self.assertRaises(ValueError):m.skill_text('a/b','../../etc/passwd')
if __name__=='__main__':unittest.main()
