import json
import unittest

import httpx

from backend.model_protocol import continuation_scope, prepare_messages
from tests.work_events import Harness, stream, tool_call


def answer(text):
    return stream([{'choices': [{'delta': {'content': text}, 'finish_reason': 'stop'}]}])


class ModelLedTests(unittest.IsolatedAsyncioTestCase):
    async def test_mode_controls_tool_inventory_not_request_wording(self):
        h = Harness([])
        observed = []

        def respond(request):
            body = json.loads(request.content)
            if body.get("max_tokens") != 64:
                observed.append(body)
            return answer('Useful response.')

        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                h.engine.client = client
                for prompt, mode in [('Research the topic.', None), ('Research the topic.', 'agent'),
                                     ('Inspect the workspace.', 'agent'), ('Inspect the workspace.', 'direct')]:
                    chat = h.store.create_chat()
                    h.store.add(chat, {'role': 'user', 'content': prompt})
                    before = len(observed)
                    h.engine.start(chat, execution_mode=mode)
                    await h.engine.tasks[chat]
                    if mode == 'agent':
                        self.assertIn('Useful response.', [m['content'] for m in h.store.messages(chat)])
                    del observed[before + 1:]
                self.assertNotEqual(observed[0]['tools'], observed[1]['tools'])
                self.assertEqual(observed[1]['tools'], observed[2]['tools'])
                self.assertNotIn('tools', observed[3])
                self.assertEqual(observed[3]['messages'], [{'role': 'user', 'content': 'Inspect the workspace.'}])
        finally:
            h.close()

    async def test_multiple_streamed_calls_are_dispatched_after_complete_batch(self):
        first = tool_call(0, 'read-a', 'read_file', {'path': 'a.txt'})
        first['choices'][0]['delta']['tool_calls'][0]['function']['arguments'] = '{"path":'
        second = tool_call(1, 'list', 'list_files', {'path': '.'})
        remainder = {'choices': [{'delta': {'tool_calls': [
            {'index': 0, 'function': {'arguments': '"a.txt"}'}}
        ]}, 'finish_reason': 'tool_calls'}]}
        h = Harness([stream([first, second, remainder]), answer('Done.')])
        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'user', 'content': 'Look around.'})
            h.engine.start(chat, execution_mode='agent')
            await h.engine.tasks[chat]
            self.assertCountEqual([a['name'] for a in h.store.actions(chat)], ['read_file', 'list_files'])
        finally:
            h.close()

    async def test_interrupted_batch_never_dispatches_its_complete_prefix(self):
        first = tool_call(0, 'list', 'list_files', {'path': '.'})
        second = tool_call(1, 'read', 'read_file', {'path': 'a.txt'})
        second['choices'][0]['delta']['tool_calls'][0]['function']['arguments'] = '{"path":'
        h = Harness([stream([first, second])])
        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'user', 'content': 'Look around.'})
            h.engine.start(chat, execution_mode='agent')
            await h.engine.tasks[chat]
            self.assertEqual(h.store.actions(chat), [])
            self.assertEqual(h.engine.public_run(chat)['phase'], 'Checkpoint')
        finally:
            h.close()

    async def test_direct_ignores_unsolicited_calls(self):
        h = Harness([stream([tool_call(0, 'ignored', 'list_files', {'path': '.'})])])
        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'user', 'content': 'Hello'})
            h.engine.start(chat, execution_mode='direct')
            await h.engine.tasks[chat]
            self.assertEqual(h.store.actions(chat), [])
        finally:
            h.close()

    async def test_productive_agent_run_passes_legacy_limit(self):
        h = Harness([stream([tool_call(0, f'read-{i}', 'read_file', {'path': f'fixture-{i}.txt'})])
                     for i in range(20)] + [answer('Finished inspection.')])
        try:
            chat = h.store.create_chat()
            from pathlib import Path
            from backend.config import CONFIG
            for i in range(20):
                (Path(CONFIG['workspace']) / f'fixture-{i}.txt').write_text(str(i))
            h.store.add(chat, {'role': 'user', 'content': 'Look around.'})
            h.engine.start(chat, execution_mode='agent')
            await h.engine.tasks[chat]
            self.assertEqual(len(h.store.actions(chat)), 20)
            self.assertEqual(h.engine.public_run(chat)['phase'], 'Complete')
        finally:
            h.close()

    def test_continuation_reasoning_is_scoped(self):
        scope = continuation_scope('model', 'https://api.deepseek.com', 'run-a')
        messages = [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'one'}],
                     'reasoning': 'provider state', 'continuation_scope': scope}]
        matched = prepare_messages(messages, scope)[0]
        self.assertEqual((matched['reasoning_content'], matched['content']), ('provider state', ''))
        other = continuation_scope('model', 'https://api.deepseek.com', 'run-b')
        self.assertNotIn('reasoning_content', prepare_messages(messages, other)[0])
        self.assertNotIn('reasoning', prepare_messages(messages, None)[0])

    async def test_repeated_identical_reads_checkpoint(self):
        h = Harness([stream([tool_call(0, f'read-{i}', 'list_files', {'path': '.'})]) for i in range(5)])
        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'user', 'content': 'Look around.'})
            h.engine.start(chat, execution_mode='agent')
            await h.engine.tasks[chat]
            self.assertEqual(h.engine.public_run(chat)['checkpoint']['reason'], 'no_progress')
        finally:
            h.close()

    async def test_deepseek_tool_round_trip_preserves_provider_state(self):
        from contextlib import asynccontextmanager
        from unittest.mock import patch
        from backend.config import CONFIG

        requests = []
        h = Harness([])
        service = {'id': 'deepseek', 'url': 'https://api.deepseek.com', 'name': 'DeepSeek',
                   'files': True, 'models': ['deepseek-flash']}
        @asynccontextmanager
        async def model_stream(body):
            requests.append(body)
            if len(requests) == 1:
                call = tool_call(0, 'read', 'list_files', {'path': '.'})
                call['choices'][0]['delta']['reasoning_content'] = 'Inspect the workspace first.'
                yield stream([call])
            else:
                yield answer('Inspection complete.')

        try:
            chat = h.store.create_chat()
            h.store.add(chat, {'role': 'user', 'content': 'Look around.'})
            with patch.dict(CONFIG, services=[service], model='svc:deepseek/deepseek-flash'), patch.object(h.engine,'model_stream',model_stream):
                h.engine.start(chat, reasoning=True, execution_mode='agent')
                await h.engine.tasks[chat]
            self.assertEqual(len(requests), 2)
            self.assertNotIn('tool_choice', requests[0])
            self.assertEqual(requests[0]['thinking'], {'type': 'enabled'})
            call, result = requests[1]['messages'][-2:]
            self.assertEqual(call['reasoning_content'], 'Inspect the workspace first.')
            self.assertEqual(call['content'], '')
            self.assertEqual(result['tool_call_id'], 'read')
        finally:
            h.close()
