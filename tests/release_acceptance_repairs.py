import unittest
from backend.compaction import summarize_detailed,CompactionFailure,RESTORED
from tests.long_workflow_retention import harness,Model,seed,SMALL,count
from backend.config import CONFIG
from unittest.mock import patch

class RepairTests(unittest.IsolatedAsyncioTestCase):
 async def test_restored_references_cannot_overflow_final_summary_budget(self):
  async def tokens(messages):return (10000 if RESTORED in messages[0]['content'] else 100),'fixture'
  async def complete(messages,max_tokens):return {'content':'Goal: retain decisions and facts.\nOpen work: keep pending tasks.'}
  with self.assertRaises(CompactionFailure) as error:
   await summarize_detailed([{'role':'user','message_id':1,'content':'Keep exact/path/file.txt'}],'',4096,tokens,complete)
  self.assertEqual(error.exception.stats['failed_validations'],1)
 async def test_assembled_overflow_preserves_previous_summary_and_originals(self):
  h=harness(Model())
  try:
   with patch.dict(CONFIG,SMALL):
    chat=h.store.create_chat();seed(h.store,chat);original=h.store.messages(chat)
    async def tokens(messages,definitions=None):
     if messages and 'Working summary of prior conversation' in messages[0].get('content',''):return 100000,'fixture'
     return await count(messages,definitions)
    h.engine.token_count=tokens
    with self.assertRaises(CompactionFailure):await h.engine.compact(chat,force=True,tokens_before=200)
    self.assertIsNone(h.store.summary(chat));self.assertEqual(h.store.messages(chat),original)
    failed=h.engine.usage.compaction()['recent'][0]
    self.assertGreater(failed['failed_validations'],0)
  finally:h.close()
 async def test_validation_retry_failures_preserve_attempt_metrics(self):
  async def tokens(messages):return 100,'fixture'
  async def complete(messages,max_tokens):return {'content':'invalid'}
  with self.assertRaises(CompactionFailure) as error:
   await summarize_detailed([{'role':'user','message_id':1,'content':'keep'}],'',4096,tokens,complete)
  self.assertEqual(error.exception.stats['attempts'],2);self.assertEqual(error.exception.stats['failed_validations'],2)

if __name__=='__main__':unittest.main()
