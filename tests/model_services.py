import unittest
from unittest.mock import patch
from backend import services
from backend.config import CONFIG
from backend.services import PrivateMessages, private_chat

SVC=[{'id':'groq','name':'Groq','url':'https://api.groq.com/openai/v1','files':False,'models':['llama-3.3-70b-versatile','qwen-2.5-coder-32b'],'context':32768}]
class ModelServices(unittest.TestCase):
    def test_models_and_requests(self):
        with patch.dict(CONFIG,services=SVC),patch.object(services,'read_secrets',lambda n:{'key':'sk-1'}):
            ids=[m['id'] for m in services.remote_models()]
            self.assertIn('svc:groq/qwen-2.5-coder-32b',ids)
            self.assertIn('Coding',next(m for m in services.remote_models() if 'coder' in m['id'])['strengths'])
            url,headers,body=services.request('svc:groq/llama-3.3-70b-versatile',{'model':'x','messages':PrivateMessages(),'dry_multiplier':.8,'chat_template_kwargs':{},'temperature':.4})
            self.assertEqual(url,'https://api.groq.com/openai/v1/chat/completions');self.assertEqual(headers,{'Authorization':'Bearer sk-1'})
            self.assertEqual(body,{'model':'llama-3.3-70b-versatile','messages':[],'temperature':.4})
            self.assertFalse(services.may_see_files('svc:groq/llama-3.3-70b-versatile'));self.assertTrue(services.may_see_files('qwen3-14b'))
    def test_private_request_excludes_workspace_data_and_keeps_public_tool_pairs(self):
        model = 'svc:groq/llama-3.3-70b-versatile'
        call = {'id': 'public', 'type': 'function',
                'function': {'name': 'research', 'arguments': '{"question":"public question"}'}}
        history = [
            {'role': 'user', 'attachments': True, 'content': [
                {'type': 'text', 'text': 'User question'},
                {'type': 'text', 'text': 'document contents'},
                {'type': 'image_ref', 'id': 'private image'}]},
            {'role': 'assistant', 'content': 'derived from local tool output'},
            {'role': 'tool', 'content': 'private tool output'},
            {'role': 'user', 'plan_step': True, 'content': 'private plan step'},
            {'role': 'user', 'screenshot': True, 'content': 'private screenshot'},
            {'role': 'assistant', 'private_model': model, 'content': None, 'tool_calls': [call]},
            {'role': 'tool', 'private_model': model, 'tool_call_id': 'public', 'content': 'public result'},
        ]
        out = private_chat(history, model, 'file-free system rules')
        with patch.dict(CONFIG, services=SVC):
            _, _, body = services.request(model, {'messages': out})
            with self.assertRaisesRegex(ValueError, 'file-free request'):
                services.request(model, {'messages': history})
        self.assertEqual([m['role'] for m in body['messages']], ['system', 'user', 'assistant', 'tool'])
        self.assertIn('User question', out[1]['content'])
        self.assertNotIn('document contents', str(body))
        self.assertNotIn('private ', str(body))
        self.assertNotIn('derived', str(body))
        self.assertEqual(out[-1]['content'], 'public result')

    def test_connected_account_access_is_separate_from_file_access(self):
        model='svc:groq/llama-3.3-70b-versatile'
        service={**SVC[0],'files':True}
        messages=services.IntegrationMessages([{'role':'user','content':'connected account context'}])
        with patch.dict(CONFIG,services=[service]):
            with self.assertRaisesRegex(ValueError,'Connected-account data'):
                services.request(model,{'messages':messages})
            service['integration_data']=True
            _,_,body=services.request(model,{'messages':messages})
            self.assertEqual(body['messages'],messages)

    def test_bad_address(self):
        with self.assertRaises(ValueError): services._url('ftp://x')
        self.assertEqual(services._url('https://openrouter.ai/api/v1/chat/completions'),'https://openrouter.ai/api/v1')

class PrivateModelFlow(unittest.IsolatedAsyncioTestCase):
    async def test_retry_and_compaction_keep_private_context_out_of_transport(self):
        import json
        import httpx
        from tests.work_events import Harness, stream

        h = Harness([])
        model = 'svc:groq/llama-3.3-70b-versatile'
        requests = []
        httpx_client = httpx.AsyncClient

        async def capture(request):
            requests.append(json.loads(request.content))
            if len(requests) == 1:
                return httpx.Response(503)
            return stream([{'choices': [{'delta': {'content': 'Public answer.'}}]}])

        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'assistant', 'content': 'Private workspace output'})
            h.store.add(chat, {'role': 'user', 'attachments': True, 'content': [
                {'type': 'text', 'text': 'Typed question'},
                {'type': 'text', 'text': 'Private attachment contents'},
            ]})
            h.store.save_summary(chat, 1, 'Private summary')
            with patch.dict(CONFIG, services=SVC, model=model, orchestration_enabled=False):
                with patch('backend.engine.httpx.AsyncClient',
                           side_effect=lambda **_: httpx_client(transport=httpx.MockTransport(capture))):
                    h.engine.start(chat)
                    await h.engine.tasks[chat]
                    h.engine.start(chat, compact_only=True)
                    await h.engine.tasks[chat]
            self.assertEqual(h.store.messages(chat)[-1]['content'], 'Public answer.')
            self.assertEqual(len(requests), 2)
            self.assertFalse(h.engine.runs[chat]['compact_result']['compacted'])
            for request in requests:
                self.assertIn('Typed question', str(request['messages']))
                self.assertNotIn('Private ', str(request['messages']))
        finally:
            h.close()


if __name__=='__main__': unittest.main()
