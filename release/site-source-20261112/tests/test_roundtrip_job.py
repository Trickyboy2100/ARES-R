import copy
import json
from pathlib import Path
import tempfile
import unittest
from ares_r.manipulation.roundtrip_job import RoundtripJob,atomic,canonical_status
from ares_r.manipulation.roundtrip_demo import CycleRunner
from ares_r.motion.physical_command_ledger import PhysicalCommandLedger
from ares_r.motion.arrival_contract import await_arrival,minimal_arm_state
ROOT=Path(__file__).resolve().parents[1]
class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        self.route=json.loads((ROOT/self.p['base_route']).read_text())
    def tearDown(self):self.tmp.cleanup()
    def test_owner_excludes_second_job_without_stealing_pointer(self):
        owner=self.root/'owner';one=RoundtripJob(self.root/'one',self.p,self.route,owner_root=owner)
        one.acquire()
        try:
            two=RoundtripJob(self.root/'two',self.p,self.route,owner_root=owner)
            with self.assertRaisesRegex(RuntimeError,'OWNER_BUSY'):two.acquire()
            self.assertEqual(json.loads((owner/'current.json').read_text())['run_id'],one.value['run_id'])
        finally:one.release()
    def test_resume_reconciles_lost_response_without_reissuing_command(self):
        commands=[];ledger={};lost=[True]
        class Transport:
            def record_completed(self,*args):pass
            def check_cancelled(self):pass
            def stop(self):pass
            def checkpoint_snapshot(self):return {'count':len(commands)}
            def restore_checkpoint(self,snapshot):pass
            def validate_resume(self,value):pass
            def reconcile(self,stage,token):return {'outcome':'COMPLETED','result':ledger[token]}
            def __getattr__(self,name):
                def call(**kwargs):
                    token=self.command_id;commands.append(token);ledger[token]={'provider':'UNIT_TEST'}
                    if lost[0] and token.endswith('LIFT230_CONTINUOUS'):
                        lost[0]=False;raise RuntimeError('response lost')
                    return ledger[token]
                return call
        transport=Transport();out=self.root/'job';owner=self.root/'owner'
        job=RoundtripJob(out,self.p,self.route,owner_root=owner)
        with self.assertRaisesRegex(RuntimeError,'response lost'):CycleRunner(self.p,self.route,transport,lambda *a:None,job=job).run()
        resumed=RoundtripJob(out,self.p,self.route,owner_root=owner,resume=True)
        result=CycleRunner(self.p,self.route,transport,lambda *a:None,job=resumed).run()
        self.assertEqual(result['stages'],20);self.assertEqual(len(commands),20);self.assertEqual(len(set(commands)),20)
        self.assertEqual(resumed.value['resume_count'],1)
    def test_uncertain_release_is_not_repeated(self):
        job=RoundtripJob(self.root/'job',self.p,self.route,owner_root=self.root/'owner');job.acquire()
        job.begin({'id':'RELEASE','call':'gripper','arguments':{'raw':400}});job.release()
        resumed=RoundtripJob(job.directory,self.p,self.route,owner_root=job.owner_root,resume=True)
        class Transport:
            def reconcile(self,*a):return {'outcome':'UNCERTAIN'}
        with self.assertRaisesRegex(RuntimeError,'OUTCOME_UNCERTAIN'):resumed.restore(Transport(),[])
    def test_dispatch_duplicate_and_changed_payload(self):
        ledger=PhysicalCommandLedger(self.root);body={'command_id':'run:close','raw':0}
        self.assertTrue(ledger.reserve('run:close','gripper',body)[0])
        ledger.update('run:close','UNCERTAIN',{'error':'lost response'})
        self.assertFalse(ledger.reserve('run:close','gripper',body)[0])
        with self.assertRaisesRegex(RuntimeError,'PAYLOAD_CHANGED'):ledger.reserve('run:close','gripper',dict(body,raw=400))
    def test_webui_art_same_canonical_job(self):
        from ares_r.canonical_backend import CanonicalBackend
        from ares_r.demos.roundtrip_launcher import RoundtripLauncher
        owner=self.root/'worklog/runtime/right_arm_grasp_place_roundtrip_v1'
        job=RoundtripJob(self.root/'worklog/run',self.p,self.route,owner_root=owner);job.acquire()
        job.value.update(state='FAULT',stage='ATTACH',failure='GRASP_UNCERTAIN');job.save();job.release()
        backend=object.__new__(CanonicalBackend);backend.root=self.root
        launcher=RoundtripLauncher(self.root);launcher.contract=lambda:({}, {'blockers':[]})
        web=launcher.status();art=backend.call('task_status')
        for key in ('run_id','state','stage','failure_message'):self.assertEqual(web[key],art[key])
    def test_settling_and_left_recovery_bounded(self):
        clock=[0.];samples=[{'joints_rad':[.002]*6,'in_position':True}]+[{'joints_rad':[0.]*6,'in_position':True}]*2
        proof=await_arrival(lambda:samples.pop(0),[0.]*6,clock=lambda:clock[0],sleep=lambda t:clock.__setitem__(0,clock[0]+t))
        self.assertEqual(len(proof['samples']),3)
        calls=[]
        def unavailable(side):calls.append(side);raise SystemError('SDK verbose status failure')
        with self.assertRaises(SystemError):minimal_arm_state(unavailable,'left',sleep=lambda t:None)
        self.assertEqual(len(calls),3)
    def test_backend_exit_zero_without_arrival_is_fault(self):
        from unittest.mock import Mock,patch
        from ares_r.canonical_backend import CanonicalBackend
        backend=object.__new__(CanonicalBackend)
        import threading
        backend._physical_guard=threading.Lock();backend._physical_process=Mock()
        backend._physical_process.poll.return_value=0;backend._physical_stream=None
        backend._physical_pty=None;backend._physical_abort_path=None
        backend._physical_state={'state':'RUNNING','output':str(self.root/'missing-proof')}
        with patch('ares_r.motion.execution_feedback.execution_feedback',return_value={'execution_result':None}):
            state=backend.physical_status()
        self.assertEqual(state['state'],'FAULT');self.assertEqual(state['failure_reason'],'ARRIVAL_PROOF_MISSING')
