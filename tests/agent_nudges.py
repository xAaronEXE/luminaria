import unittest
from backend.engine import SKILL_COMMAND, WANTS_WORK, HANDOFF, code_lines, last_user_text, with_nudge, NUDGES

CODE='```python\n'+'\n'.join(f'line{i}=1' for i in range(20))+'\n```'
class AgentNudges(unittest.TestCase):
    def test_skill_command(self):
        self.assertEqual(SKILL_COMMAND.match('/skill before-you-build I want a bot').group(1),'before-you-build')
        self.assertEqual(SKILL_COMMAND.match('  /skill documents').group(1),'documents')
        self.assertIsNone(SKILL_COMMAND.match('please use /skill documents'))
    def test_code_in_chat_is_caught_only_when_work_was_asked(self):
        self.assertTrue(WANTS_WORK.search('can you code it all?') and code_lines(CODE)>=12)
        self.assertTrue(WANTS_WORK.search('can you do it all, get it all put together.'))
        self.assertIsNone(WANTS_WORK.search('what does a python for loop look like'))
        self.assertLess(code_lines('```\nx=1\n```'),12)
    def test_handoff(self):
        self.assertTrue(HANDOFF.search('Open a command prompt and type python bot.py'))
        self.assertTrue(HANDOFF.search('You can install it using pip install requests'))
        self.assertIsNone(HANDOFF.search('I saved bot.py on your Desktop and ran it.'))
    def test_nudge_text_follows_kind(self):
        out=with_nudge([{'role':'system','content':'x'}],{'nudge_pending':True,'nudge_kind':'code'})
        self.assertEqual(out[-1]['content'],NUDGES['code'])
        self.assertEqual(last_user_text([{'role':'user','content':[{'type':'text','text':'hi'}]},{'role':'assistant','content':'yo'}]),'hi')

if __name__=='__main__': unittest.main()
