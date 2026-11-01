import asyncio,unittest
from backend.tools import Toolbox,EXTRA_TOOLS

def names(tools,enabled): return {d['function']['name'] for d in tools.definitions(enabled)}

class ToolGating(unittest.TestCase):
    def setUp(self): self.t=Toolbox(None,{})
    def test_everyday_set_hides_extras(self):
        shown=names(self.t,set())
        self.assertFalse(shown & EXTRA_TOOLS)
        for core in ('read_file','write_file','list_files','inspect_file','discover_tools','load_skill','remember'):
            self.assertIn(core,shown)
    def test_more_unlocks_everything(self):
        shown=names(self.t,{'more'})
        self.assertTrue({'delete_file','create_schedule','history_read'} <= shown)
    def test_discover_more_and_skill_unlocks(self):
        run={'enabled':set()}
        listed=asyncio.run(self.t.dispatch('discover_tools',{'category':'more'},run))
        self.assertIn('more',run['enabled'])
        self.assertTrue({x['name'] for x in listed} <= EXTRA_TOOLS)
        run={'enabled':{'finish_skill'}}
        shown=names(self.t,run['enabled'])
        self.assertIn('finish_skill',shown); self.assertNotIn('delete_file',shown)

if __name__=='__main__': unittest.main()
