"""The plan runner: Luminaria, not the model, decides when a step is finished."""
import asyncio,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from backend.engine import Engine,CONFIG
from backend import plan_runner as PR

class Store:
    def __init__(self,plan): self.s={'plan:c':plan}; self.msgs=[]; self.actions=[]; self.saved=[]
    def setting(self,k,d=None): return json.loads(json.dumps(self.s.get(k,d)))
    def set_setting(self,k,v): self.s[k]=json.loads(json.dumps(v))
    def add(self,chat,m): self.msgs.append({**m,'id':len(self.msgs)+1}); return len(self.msgs)
    def messages(self,chat,after=0): return [m for m in self.msgs if m['id']>after]
    def save_run(self,run): self.saved.append(json.loads(json.dumps({k:v for k,v in run.items() if k!='enabled'})))
    def rows(self,sql,args=()):
        if 'step IN (' in sql:
            return [dict(name=a['name'],args=json.dumps(a['args']),status=a['status']) for a in self.actions if a['step'] in args[1:]]
        assert 'FROM actions WHERE chat=? AND step=?' in sql
        return [dict(a,args=json.dumps(a['args']),result=json.dumps(a['result']) if a['result'] else None) for a in self.actions if a['step']==args[1] and a['created']>=args[2]]
    def act(self,step,name,args,status='done',result=None):
        self.actions.append({'id':str(len(self.actions)),'chat':'c','step':step,'name':name,'args':args,'status':status,'result':result,'created':time.time()})

class PlanRunner(unittest.TestCase):
    def setUp(self):
        self.dir=Path(tempfile.mkdtemp())
        def m(id,strengths,params='14B'):
            f=self.dir/(id+'.gguf');f.write_bytes(b'x');return {'id':id,'name':id,'strengths':strengths,'parameters':params,'model_file':str(f)}
        self.models=[m('chat-writer',['Writing']),m('qwen25-coder-14b',['Coding','Tools']),m('qwen3-14b',['Reasoning','Tools','Writing'])]
        self.calls=[]
    def engine(self,steps,script):
        """script: one function per model turn; it acts on the store the way a model's tool calls would."""
        e=Engine.__new__(Engine);e.store=Store({'goal':'Ship a todo app','steps':steps});e.broadcast=lambda ev:None;turns=iter(script)
        async def run_step(run,model,instruction,reasoning=False,continue_step=False):
            self.calls.append((model['id'],instruction.split(']')[0]+']',continue_step)); e.store.save_run(run)
            for key in ('denied','checkpoint','stalled'): run.pop(key,None)
            e.store.add('c',{'role':'user','content':instruction})
            if instruction.startswith('[Final check]'): e.store.add('c',{'role':'assistant','content':'Looks right.'}); return False
            paused=next(turns)(e.store,run,instruction)
            e.store.add('c',{'role':'assistant','content':'Did it. Saved in todo.py.'})
            return bool(paused)
        e.run_step=run_step; return e
    def run_plan(self,e,run=None,**kw):
        run=run or {'chat':'c','id':'r','plan_run':True}
        with patch.dict(CONFIG,model='chat-writer',coder_model='auto',planner_model='auto',workspace=str(self.dir)),patch('backend.orchestration.gpu_memory',lambda:16*2**30):
            paused=asyncio.run(e.run_plan(run,self.models,**kw))
        return paused,run,e.store.setting('plan:c')
    def write(self,name,text='print(1)'):
        def turn(store,run,instruction):
            (self.dir/name).write_text(text); store.act(run['step_id'],'write_file',{'path':name,'content':text})
        return turn

    def test_steps_use_role_models_record_notes_and_pass_their_checks(self):
        steps=[{'id':'s1','title':'Write the Python code for the todo list','status':'pending','check':{'type':'file_exists','path':'todo.py'}},
               {'id':'s2','title':'Write a short README for users','status':'pending','check':{'type':'file_contains','path':'README.md','text':'todo'}}]
        e=self.engine(steps,[self.write('todo.py'),self.write('README.md','How to use the todo app')])
        paused,run,plan=self.run_plan(e)
        self.assertFalse(paused)
        self.assertEqual([c[0] for c in self.calls],['qwen25-coder-14b','chat-writer','qwen3-14b'])
        self.assertTrue(self.calls[-1][1].startswith('[Final check]'))
        self.assertEqual([(s['status'],s['verdict']) for s in plan['steps']],[('done','passed')]*2)
        self.assertIn('todo.py',plan['steps'][0]['note'])
        self.assertIn('all 2 steps were checked and passed',e.store.msgs[-1]['content'])
        self.assertFalse(run['plan_blocked'])

    def test_activity_is_not_completion(self):
        # The model writes an unrelated file. With a check the step never passes; trying the same thing again is "no progress".
        steps=[{'id':'s1','title':'Write the Python code','status':'pending','check':{'type':'file_exists','path':'todo.py'}},{'id':'s2','title':'Write docs','status':'pending'}]
        e=self.engine(steps,[self.write('other.py'),self.write('other.py')])
        paused,run,plan=self.run_plan(e)
        s1,s2=plan['steps']
        self.assertEqual((s1['status'],s1['verdict'],s1['attempts']),('blocked','failed',2))
        self.assertIn('No progress',s1['reason'])
        self.assertEqual(s2['status'],'pending','later steps do not run past a blocked one')
        self.assertFalse(any(c[1].startswith('[Final check]') for c in self.calls))
        self.assertTrue(run['plan_blocked']); self.assertIn('Plan not finished',e.store.msgs[-1]['content']); self.assertIn('Continue plan',e.store.msgs[-1]['content'])

    def test_work_without_a_check_is_done_but_unverified(self):
        e=self.engine([{'id':'s1','title':'Write the Python code','status':'pending'}],[self.write('todo.py')])
        _,run,plan=self.run_plan(e)
        self.assertEqual((plan['steps'][0]['status'],plan['steps'][0]['verdict']),('done','unverified'))
        report=e.store.msgs[-1]['content']
        self.assertIn('not fully proven',report); self.assertNotIn('all 1 steps',report)

    def test_a_step_that_only_talks_is_sent_back_then_recorded_as_unproven(self):
        talk=lambda store,run,instruction:None
        e=self.engine([{'id':'s1','title':'Write the Python code','status':'pending'}],[talk,talk])
        _,_,plan=self.run_plan(e)
        self.assertEqual(len([c for c in self.calls if not c[1].startswith('[Final')]),2)
        self.assertTrue(self.calls[1][2],'the second try continues the same step')
        self.assertEqual(plan['steps'][0]['verdict'],'unverified'); self.assertIn('No action was taken',plan['steps'][0]['reason'])

    def test_a_big_step_continues_while_it_makes_progress(self):
        def out_of_rounds(name):
            def turn(store,run,instruction): self.write(name)(store,run,instruction); run['checkpoint']={'reason':'limit'}
            return turn
        steps=[{'id':'s1','title':'Write the Python code','status':'pending','check':{'type':'file_exists','path':'todo.py'}}]
        e=self.engine(steps,[out_of_rounds('a.py'),out_of_rounds('b.py'),self.write('todo.py')])
        _,_,plan=self.run_plan(e)
        self.assertEqual((plan['steps'][0]['status'],plan['steps'][0]['verdict'],plan['steps'][0]['attempts']),('done','passed',3))

    def test_running_out_of_rounds_with_no_progress_blocks(self):
        def stuck(store,run,instruction): store.act(run['step_id'],'run_command',{'command':'pytest'},'error',{'text':'1 failed'}); run['checkpoint']={'reason':'limit'}
        e=self.engine([{'id':'s1','title':'Fix the code','status':'pending'}],[stuck,stuck,stuck])
        _,_,plan=self.run_plan(e)
        self.assertEqual(plan['steps'][0]['status'],'blocked'); self.assertLessEqual(plan['steps'][0]['attempts'],2)
        self.assertIn('no further progress',plan['steps'][0]['reason'])

    def test_three_attempts_at_most(self):
        n=iter(range(9))
        def different_each_time(store,run,instruction): self.write(f'try{next(n)}.py')(store,run,instruction)
        steps=[{'id':'s1','title':'Write the Python code','status':'pending','check':{'type':'file_exists','path':'todo.py'}}]
        e=self.engine(steps,[different_each_time]*5)
        _,_,plan=self.run_plan(e)
        self.assertEqual((plan['steps'][0]['status'],plan['steps'][0]['verdict'],plan['steps'][0]['attempts']),('blocked','failed',PR.ATTEMPTS))

    def test_command_check_is_judged_from_what_actually_ran(self):
        check={'type':'command','command':'python -m pytest -q','expect':'passed'}
        def fails_then_passes():
            state={'n':0}
            def turn(store,run,instruction):
                state['n']+=1
                if state['n']==1: store.act(run['step_id'],'run_command',{'command':'python -m pytest -q'},'error',{'text':'1 failed'})
                else: self.write('fix.py')(store,run,instruction); store.act(run['step_id'],'run_command',{'command':'python -m pytest -q'},'done',{'text':'3 passed'})
            return turn
        turn=fails_then_passes()
        e=self.engine([{'id':'s1','title':'Make the tests pass','status':'pending','check':check}],[turn,turn])
        _,_,plan=self.run_plan(e)
        self.assertEqual((plan['steps'][0]['verdict'],plan['steps'][0]['attempts']),('passed',2))
        self.assertIn('python -m pytest -q',e.store.msgs[0]['content'],'the step is told its check up front')
        # A required command check that never ran blocks the plan.
        e=self.engine([{'id':'s1','title':'Make the tests pass','status':'pending','check':check}],[self.write('a.py'),self.write('b.py'),self.write('c.py')])
        _,_,plan=self.run_plan(e)
        self.assertEqual((plan['steps'][0]['status'], plan['steps'][0]['verdict']), ('blocked', 'unverified'))
        self.assertIn('was not run', plan['steps'][0]['reason'])

    def test_declined_action_blocks_and_nothing_else_is_tried(self):
        def declined(store,run,instruction): store.act(run['step_id'],'delete_file',{'path':'x'},'denied'); run['denied']=True
        e=self.engine([{'id':'s1','title':'Clean up','status':'pending'},{'id':'s2','title':'Write docs','status':'pending'}],[declined])
        _,run,plan=self.run_plan(e)
        self.assertEqual(plan['steps'][0]['status'],'blocked'); self.assertIn('declined',plan['steps'][0]['reason'])
        self.assertEqual(len(self.calls),1); self.assertNotIn('denied',run)

    def test_unknown_outcome_is_never_retried_automatically(self):
        def cut_off(store,run,instruction): store.act(run['step_id'],'run_command',{'command':'pip install x'},'interrupted')
        e=self.engine([{'id':'s1','title':'Install the package','status':'pending'}],[cut_off,cut_off])
        _,_,plan=self.run_plan(e)
        self.assertEqual(len(self.calls),1); self.assertEqual(plan['steps'][0]['status'],'blocked'); self.assertIn('outcome is unknown',plan['steps'][0]['reason'])

    def test_continue_picks_up_at_the_blocked_step_with_fresh_attempts(self):
        steps=[{'id':'s1','title':'Write the Python code','status':'done','verdict':'passed'},
               {'id':'s2','title':'Write the tests','status':'blocked','verdict':'failed','reason':'old','attempts':3,'check':{'type':'file_exists','path':'test_todo.py'}},
               {'id':'s3','title':'Write docs','status':'pending'}]
        e=self.engine(steps,[self.write('test_todo.py'),self.write('README.md')])
        _,_,plan=self.run_plan(e)
        self.assertEqual([s['status'] for s in plan['steps']],['done','done','done'])
        self.assertEqual((plan['steps'][1]['verdict'],plan['steps'][1]['attempts']),('passed',1))
        self.assertTrue(self.calls[0][1].startswith('[Plan step 2 of 3'),'step 1 is not run again')

    def test_state_is_saved_before_each_step_and_a_finished_turn_is_judged_on_resume(self):
        steps=[{'id':'s1','title':'Write the Python code','status':'active','check':{'type':'file_exists','path':'todo.py'}},{'id':'s2','title':'Write docs','status':'pending'}]
        e=self.engine(steps,[self.write('README.md')])
        (self.dir/'todo.py').write_text('x'); since=time.time()-5
        e.store.actions.append({'id':'a','chat':'c','step':'s1','name':'write_file','args':{'path':'todo.py'},'status':'done','result':None,'created':time.time()-1})
        run={'chat':'c','id':'r','plan_run':True,'step_id':'s1','step_state':{'id':'s1','attempt':1,'since':since,'fingerprint':None},'resumed_step':'s1'}
        _,run,plan=self.run_plan(e,run,judge_first=True)
        self.assertEqual(plan['steps'][0]['verdict'],'passed')
        self.assertTrue(self.calls[0][1].startswith('[Plan step 2 of 2'),'the step that already finished is judged, not run again')
        self.assertNotIn('resumed_step',run)
        self.assertEqual(e.store.saved[0]['step_state']['id'],'s2','what step is running is on disk before the model is called')

    def test_no_plan(self):
        e=Engine.__new__(Engine);e.store=Store(None)
        with self.assertRaises(ValueError): asyncio.run(e.run_plan({'chat':'c','id':'r'},self.models))

    def test_forward_dependency_runs_first(self):
        steps = [
            {'id': 'docs', 'title': 'Write docs', 'status': 'pending', 'depends_on': ['build']},
            {'id': 'build', 'title': 'Build', 'status': 'pending', 'check': {'type': 'file_exists', 'path': 'app.py'}},
        ]
        def docs(store, run, instruction):
            self.assertTrue((self.dir / 'app.py').exists())
            self.write('README.md')(store, run, instruction)
        e = self.engine(steps, [self.write('app.py'), docs])
        _, _, plan = self.run_plan(e)
        self.assertEqual([s['status'] for s in plan['steps']], ['done', 'done'])

    def test_unverified_dependency_blocks_following_work(self):
        steps = [
            {'id': 'build', 'title': 'Build', 'status': 'pending'},
            {'id': 'docs', 'title': 'Write docs', 'status': 'pending', 'depends_on': ['build']},
        ]
        e = self.engine(steps, [self.write('app.py')])
        _, _, plan = self.run_plan(e)
        self.assertEqual(plan['steps'][1]['status'], 'blocked')
        self.assertIn('Build', plan['steps'][1]['reason'])

    def test_final_offline_command_reruns_with_the_same_check_and_blocks_on_failure(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        if os.name != 'nt':
            self.skipTest('Automatic command rechecks require Windows isolation.')
        check={'type':'command','command':'Get-Content report.txt','inputs':['report.txt'],'expect':'ready'}
        steps=[{'id':'s1','title':'Check report','status':'pending','check':check}]

        def check_once(store,run,instruction):
            store.act('s1','run_command',{'command':check['command'],'inputs':check['inputs']},
                      result={'stdout':'ready','input_evidence':{'report.txt':'original'}})

        for stdout, expected in [('ready','passed'),('broken','failed')]:
            with self.subTest(stdout=stdout):
                e=self.engine(steps,[check_once])
                command=AsyncMock(return_value={'exit_code':0,'stdout':stdout,
                                                'input_evidence':{'report.txt':'current'}})
                e.tools=SimpleNamespace(call=command)
                _,run,plan=self.run_plan(e)
                command.assert_awaited_once_with('run_command',{'command':check['command'],'inputs':check['inputs']},run)
                self.assertEqual(plan['steps'][0]['verdict'],expected)
                if expected=='passed':
                    self.assertEqual(plan['steps'][0]['check_result']['input_evidence'],{'report.txt':'current'})
                else:
                    self.assertTrue(run['plan_blocked'])

    def test_continue_stops_until_a_prior_interrupted_action_is_reconciled(self):
        steps=[{'id':'s1','title':'Edit report','status':'blocked',
                'check':{'type':'file_exists','path':'report.txt'}}]
        e=self.engine(steps,[self.write('report.txt','ready')])
        e.store.act('s1','edit_file',{'path':'report.txt'},status='interrupted')
        _,run,plan=self.run_plan(e)
        self.assertTrue(run['plan_blocked'])
        self.assertEqual(self.calls,[])
        self.assertIn('Activity',plan['steps'][0]['reason'])
        e.store.actions[0]['status']='retryable'
        _,_,plan=self.run_plan(e)
        self.assertEqual(plan['steps'][0]['verdict'],'passed')

    def test_final_file_verification_detects_a_later_step_overwrite(self):
        steps = [
            {'id': 's1', 'title': 'Write a report', 'status': 'pending',
             'check': {'type': 'file_contains', 'path': 'report.md', 'text': 'required'}},
            {'id': 's2', 'title': 'Write a summary', 'status': 'pending'},
        ]
        e = self.engine(steps, [self.write('report.md', 'required'), self.write('report.md', 'summary')])
        _, _, plan = self.run_plan(e)
        self.assertEqual(plan['steps'][0]['status'], 'blocked')
        self.assertIn('Final verification', plan['steps'][0]['reason'])

class Rules(unittest.TestCase):
    def test_go_ahead_starts_the_runner_only_with_steps_left(self):
        plan={'steps':[{'id':'a','title':'x','status':'done'},{'id':'b','title':'y','status':'pending'}]}
        for text in ('go ahead','Go ahead.','ok do it','yes, go ahead please','Proceed','continue','carry out the plan','Carry out the saved plan, one step at a time.','lets go','implement it','keep going','Okay, start'):
            with self.subTest(text=text): self.assertTrue(PR.wants_plan_run(text,plan))
        for text in ('go ahead and also add a login page','what does step 2 do?','do it differently: use Rust','continue explaining','stop','no'):
            with self.subTest(text=text): self.assertFalse(PR.wants_plan_run(text,plan))
        self.assertFalse(PR.wants_plan_run('go ahead',None))
        self.assertFalse(PR.wants_plan_run('go ahead',{'steps':[{'id':'a','title':'x','status':'done'},{'id':'b','title':'y','status':'skipped'}]}))

    def test_the_model_cannot_certify_or_reshape_a_running_plan(self):
        saved={'steps':[{'id':'s1','title':'Write code','status':'done','verdict':'passed','note':'n'},{'id':'s2','title':'Test it','status':'active'},{'id':'s3','title':'Docs','status':'pending'}]}
        proposed=[{'id':'s1','title':'Write code','status':'done','depends_on':[]},{'id':'renamed','title':'Test it','status':'done','depends_on':[]},
                  {'id':'s3','title':'Docs','status':'done','depends_on':[]},{'id':'s4','title':'Package it','status':'done','depends_on':['s3','nope']}]
        merged=PR.merge_plan(saved,proposed,plan_run=True)
        self.assertEqual([(s['id'],s['status']) for s in merged],[('s1','done'),('s2','active'),('s3','pending'),('renamed','pending'),('s4','pending')])
        self.assertEqual(merged[0]['note'],'n'); self.assertEqual(merged[4]['added_by'],'model'); self.assertEqual(merged[4]['depends_on'],['s3'])
        # Outside a plan run the model may reshape the plan, but "done" from the model is not proof.
        loose=PR.merge_plan(saved,proposed,plan_run=False)
        self.assertEqual(loose[0]['verdict'],'passed','a step Luminaria already judged keeps its verdict')
        self.assertEqual((loose[2]['status'],loose[2]['verdict']),('done','unverified'))

    def test_checks_that_cannot_fail_are_refused(self):
        for bad in ({'type':'command','command':'exit 0'},{'type':'command','command':'echo done'},{'type':'command','command':' TRUE '},{'type':'command','command':''},
                    {'type':'file_exists'},{'type':'file_contains','path':'a.txt','text':' '},{'type':'vibes'},'yes'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): PR.clean_check(bad)
        self.assertEqual(PR.clean_check({'type':'command','command':'python -m pytest','extra':1}),{'type':'command','command':'python -m pytest'})
        self.assertIsNone(PR.clean_check(None))
        from backend.work import plan_steps
        self.assertEqual(plan_steps({'steps':[{'id':'a','title':'t','status':'pending','check':{'type':'file_exists','path':'x.py'}}]})[0]['check'],{'type':'file_exists','path':'x.py'})
        with self.assertRaises(ValueError): plan_steps({'steps':[{'id':'a','title':'t','status':'pending','check':{'type':'command','command':'echo ok'}}]})

    def test_summary_never_overstates(self):
        done=lambda v:{'id':'x','title':'T','status':'done','verdict':v}
        self.assertIn('all 2 steps were checked and passed',PR.summary({'steps':[done('passed'),done('passed')]}))
        mixed=PR.summary({'steps':[done('passed'),{**done('unverified'),'reason':'no check'}]})
        self.assertIn('not fully proven',mixed); self.assertIn('1 of 2 steps passed',mixed); self.assertNotIn('Continue plan',mixed)
        stopped=PR.summary({'steps':[done('passed'),{'id':'b','title':'Tests','status':'blocked','reason':'Check failed: 1 failed'},{'id':'c','title':'Docs','status':'pending'}]})
        self.assertIn('Plan not finished',stopped); self.assertIn('Step 2, **Tests**, stopped: Check failed: 1 failed',stopped); self.assertIn('1 not started',stopped)

class Evidence(unittest.TestCase):
    def test_strength_of_a_passed_check(self):
        from backend import plan_runner as PR
        resolve=lambda p:'/w/'+p
        wrote=[{'name':'write_file','status':'done','args':{'path':'tests/test_app.py'}}]
        check={'type':'command','command':'python -m pytest tests/test_app.py'}
        self.assertEqual(PR.evidence(check,wrote,resolve),'self_written')
        self.assertEqual(PR.evidence(check,[{'name':'write_file','status':'done','args':{'path':'app.py'}}],resolve),'independent')
        self.assertEqual(PR.evidence({'type':'file_exists','path':'out.txt'},wrote,resolve),'file')
        self.assertIsNone(PR.evidence(None,wrote,resolve))
    def test_summary_mentions_self_written_tests(self):
        from backend import plan_runner as PR
        plan={'steps':[{'id':'a','title':'Build','status':'done','verdict':'passed','evidence':'self_written'}]}
        self.assertIn('tests written during this plan',PR.summary(plan))

if __name__=='__main__': unittest.main()
