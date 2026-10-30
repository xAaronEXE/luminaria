import json,unittest
from backend.context_shaping import shape,attach_state,for_summary,STATE_HEADER

def call(id,name,args):return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
def turn(user,*steps):
 out=[{'role':'user','content':user}]
 for id,name,args,result in steps:
  out.append({'role':'assistant','content':'','tool_calls':[call(id,name,args)]})
  out.append({'role':'tool','tool_call_id':id,'content':f'Action {id}aaaaaaaa: '+result})
 return out

BIG='line\n'*2000

class ContextShapingTests(unittest.TestCase):
 def test_older_tool_output_is_shortened_with_a_pointer(self):
  messages=turn('one',('c1','run_command',{'command':'dir'},'START'+BIG+'END'))+turn('two')+turn('three')
  shaped,stats=shape(messages,keep_turns=2)
  old=shaped[2]['content']
  self.assertTrue(old.startswith('Action c1aaaaaaaa: [Older output shortened'))
  self.assertIn('history_read action_id=c1aaaaaaaa',old);self.assertIn('START',old);self.assertIn('END',old)
  self.assertEqual(stats['shortened'],1);self.assertGreater(stats['chars_saved'],5000)
  self.assertEqual(messages[2]['content'][-3:],'END')  # input untouched

 def test_recent_turns_and_short_outputs_stay_whole(self):
  messages=turn('one',('c1','run_command',{},'small'))+turn('two',('c2','run_command',{},BIG))
  shaped,stats=shape(messages,keep_turns=2)
  self.assertEqual(shaped,messages);self.assertEqual(stats['shortened'],0)

 def test_reread_file_keeps_only_newest_copy(self):
  messages=turn('one',('c1','read_file',{'path':'src/App.js'},BIG),('c2','read_file',{'path':'src\\app.js'},BIG+'v2'))
  shaped,stats=shape(messages,keep_turns=2)
  self.assertIn('[Superseded',shaped[2]['content']);self.assertTrue(shaped[4]['content'].endswith('v2'))
  self.assertEqual(stats['superseded'],1)

 def test_same_history_always_gives_same_request(self):
  messages=turn('one',('c1','run_command',{},BIG))+turn('two')+turn('three')
  self.assertEqual(shape(messages)[0],shape(messages)[0])

 def test_state_goes_on_last_message_not_system(self):
  messages=[{'role':'system','content':'S'}]+turn('do it')
  attach_state(messages,['Saved plan: x'])
  self.assertEqual(messages[0]['content'],'S');self.assertIn(STATE_HEADER,messages[-1]['content']);self.assertIn('Saved plan: x',messages[-1]['content'])
  images=[{'role':'system','content':'S'},{'role':'user','content':[{'type':'text','text':'see'}]}]
  attach_state(images,['P']);self.assertEqual(images[-1]['content'][-1]['type'],'text')
  alone=[{'role':'system','content':'S'}];attach_state(alone,['P']);self.assertIn('P',alone[0]['content'])

 def test_long_single_turn_run_trims_in_batches(self):
  steps=[(f'c{i}','run_command',{'command':str(i)},BIG) for i in range(20)]
  shaped,stats=shape(turn('do a long job',*steps))
  self.assertEqual(stats['shortened'],8)            # 20 results: newest 12 whole, oldest 8 trimmed as one batch
  shaped2,_=shape(turn('do a long job',*steps[:19]))
  self.assertEqual([m['content'] for m in shaped2[:17]],[m['content'] for m in shaped[:17]])  # cut point stable between steps

 def test_summary_input_trims_long_tool_output_only(self):
  transcript=[{'role':'user','content':BIG,'message_id':1},{'role':'tool','content':'Action abcdef12: '+'x'*9000,'message_id':2},{'role':'tool','content':'Action abcdef13: {"denied": true}','message_id':3}]
  out=for_summary(transcript)
  self.assertEqual(out[0]['content'],BIG);self.assertLess(len(out[1]['content']),2600);self.assertIn('history_read action_id=abcdef12',out[1]['content'])
  self.assertEqual(out[2],transcript[2])

if __name__=='__main__':unittest.main()
