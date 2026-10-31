import json,unittest
from tests.engine_handsfree import *  # noqa: F401,F403  (installs the langgraph stub)
from backend.engine import text_tool_calls

NAMES={'list_files','read_file'}
class TextToolCalls(unittest.TestCase):
    def one(self,text):
        calls,rest=text_tool_calls(text,NAMES); self.assertEqual(len(calls),1); return calls[0],rest
    def test_fenced_json_like_the_screenshot(self):
        c,rest=self.one('```json\n{\n  "name": "list_files",\n  "arguments": {\n    "path": "F:\\\\"\n  }\n}\n```')
        self.assertEqual(c['function']['name'],'list_files'); self.assertEqual(json.loads(c['function']['arguments']),{'path':'F:\\'}); self.assertEqual(rest,'')
    def test_tool_call_tags_and_surrounding_text(self):
        c,rest=self.one('Let me look.\n<tool_call>{"name":"read_file","arguments":{"path":"a.txt"}}</tool_call>')
        self.assertEqual(rest,'Let me look.')
    def test_string_arguments_and_function_wrapper(self):
        c,_=self.one('{"function":{"name":"list_files","arguments":"{\\"path\\":\\".\\"}"}}')
        self.assertEqual(json.loads(c['function']['arguments']),{'path':'.'})
    def test_unknown_tools_and_ordinary_json_are_left_alone(self):
        for text in ('{"name":"delete_everything","arguments":{}}','Here is config: {"a": 1}','{"name":"list_files","arguments":[1]}'):
            calls,rest=text_tool_calls(text,NAMES); self.assertEqual(calls,[]); self.assertEqual(rest,text)
if __name__=='__main__': unittest.main()
