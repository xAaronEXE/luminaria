import unittest
from backend.engine import repeat_cut, clip_reply, SKILL_COMMAND, WANTS_WORK, HANDOFF, code_lines, last_user_text, with_nudge, NUDGES

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

class LoopGuard(unittest.TestCase):
    def test_looping_plan_is_cut_to_one_copy(self):
        block='Goal\nThoroughly plan Luminaria.\nSteps\n'+''.join(f'{i}. Step number {i} with a fairly long description of the work.\n' for i in range(12))
        text='Here is the plan.\n'+block*3+block[:250]
        cut=repeat_cut(text)
        self.assertIsNotNone(cut);self.assertEqual(cut.count('Step number 5 '),1)
    def test_normal_text_is_left_alone(self):
        self.assertIsNone(repeat_cut(' '.join(f'word{i}' for i in range(2000))))
        self.assertIsNone(repeat_cut('short reply'))
    def test_old_long_replies_are_clipped(self):
        self.assertEqual(clip_reply('hi'),'hi')
        out=clip_reply('x'*40000,263);self.assertLess(len(out),3300);self.assertIn('message 263',out)

if __name__=='__main__': unittest.main()
