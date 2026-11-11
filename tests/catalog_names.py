import re,unittest
from backend.model_sources_discovered import DISCOVERED
from backend.model_sources import SOURCES

def problem(name):
    if re.search(r'[0-9a-f]{10,}',name.lower()): return 'looks like a hash'
    if not re.search(r'[A-Za-z]{2,}',name): return 'has no real name, only a size'
    if len(name)>80: return 'is too long'
    if name.lower().replace(' ','') in {'huggingface','model','gguf','llm','base','instruct','chat','main','default','output'}: return 'is a generic word, not a model name'
    return None

class CatalogNames(unittest.TestCase):
    def test_every_model_has_a_readable_name(self):
        bad=[(e['repo'],e['name'],problem(e['name'])) for e in list(DISCOVERED)+list(SOURCES) if problem(e['name'])]
        self.assertEqual(bad,[],'Catalog names must be readable. Rebuild with display_name(repo).')

if __name__=='__main__':unittest.main()
