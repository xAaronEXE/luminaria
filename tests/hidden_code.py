import unittest
from backend.engine import hide_run_code,clean_message as slim

CODE='Here is the script:\n\n```python\nimport os\nfor f in os.listdir("."):\n    print(f)\nprint("done")\n```\n\nRunning it now.'
CALL=[{'id':'1','type':'function','function':{'name':'run_code','arguments':'{}'}}]

class HiddenCode(unittest.TestCase):
    def test_code_that_is_also_run_is_kept_out_of_the_chat_and_the_context(self):
        out=hide_run_code({'role':'assistant','content':CODE,'tool_calls':CALL},'make a script that lists my files')
        self.assertEqual(out['content'],'Here is the script:\n\nRunning it now.')
        self.assertIn('os.listdir',out['hidden_code'][0])
        self.assertNotIn('hidden_code',slim(out),'the model never gets the code back as context')
    def test_code_stays_when_the_user_asked_to_see_it(self):
        for asked in ('write it and show me the code','can I see the script?','paste the code here','explain the code as you go'):
            with self.subTest(asked=asked): self.assertEqual(hide_run_code({'role':'assistant','content':CODE,'tool_calls':CALL},asked)['content'],CODE)
    def test_replies_without_tools_and_short_snippets_are_untouched(self):
        self.assertEqual(hide_run_code({'role':'assistant','content':CODE},'make a script')['content'],CODE)
        short='Use `x`:\n```\npip install x\n```'
        self.assertEqual(hide_run_code({'role':'assistant','content':short,'tool_calls':CALL},'install x')['content'],short)
    def test_unclosed_fence_is_handled(self):
        out=hide_run_code({'role':'assistant','content':'Saving:\n```python\na=1\nb=2\nc=3\nd=4','tool_calls':CALL},'build it')
        self.assertEqual(out['content'],'Saving:')

if __name__=='__main__':unittest.main()
