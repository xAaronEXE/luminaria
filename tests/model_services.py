import unittest
from unittest.mock import patch
from backend import services
from backend.config import CONFIG
from backend.engine import text_only

SVC=[{'id':'groq','name':'Groq','url':'https://api.groq.com/openai/v1','files':False,'models':['llama-3.3-70b-versatile','qwen-2.5-coder-32b'],'context':32768}]
class ModelServices(unittest.TestCase):
    def test_models_and_requests(self):
        with patch.dict(CONFIG,services=SVC),patch.object(services,'read_secrets',lambda n:{'key':'sk-1'}):
            ids=[m['id'] for m in services.remote_models()]
            self.assertIn('svc:groq/qwen-2.5-coder-32b',ids)
            self.assertIn('Coding',next(m for m in services.remote_models() if 'coder' in m['id'])['strengths'])
            url,headers,body=services.request('svc:groq/llama-3.3-70b-versatile',{'model':'x','messages':[],'dry_multiplier':.8,'chat_template_kwargs':{},'temperature':.4})
            self.assertEqual(url,'https://api.groq.com/openai/v1/chat/completions');self.assertEqual(headers,{'Authorization':'Bearer sk-1'})
            self.assertEqual(body,{'model':'llama-3.3-70b-versatile','messages':[],'temperature':.4})
            self.assertFalse(services.may_see_files('svc:groq/llama-3.3-70b-versatile'));self.assertTrue(services.may_see_files('qwen3-14b'))
    def test_private_service_sees_only_conversation_text(self):
        msgs=[{'role':'system','content':'RULES\n\nPLACE C:\\Users\\a MEMORY'},{'role':'user','content':'hi'},
              {'role':'assistant','content':None,'tool_calls':[{'id':'1'}]},{'role':'tool','content':'secret file text'},{'role':'assistant','content':'done'}]
        out=text_only(msgs,'RULES\n\nPLACE C:\\Users\\a MEMORY','RULES\n\nprivate')
        self.assertEqual([m['role'] for m in out],['system','user','assistant'])
        self.assertNotIn('secret',str(out));self.assertNotIn('Users',out[0]['content'])
    def test_bad_address(self):
        with self.assertRaises(ValueError): services._url('ftp://x')
        self.assertEqual(services._url('https://openrouter.ai/api/v1/chat/completions'),'https://openrouter.ai/api/v1')

if __name__=='__main__': unittest.main()
