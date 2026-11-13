import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from blocks.action_transport import ActionTransport
from blocks.contracts import resolve

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client=ActionTransport('http://127.0.0.1:1',sleep=lambda _:None)
        row=resolve('pick.scale.sieve.v1')
        self.goal=dict(block_id=row['block_id'],expected_profile_revision=row['profile_revision'],
                       request_id='r',onsite_observer_confirmed=True,prepared_environment_confirmed=True)
        self.catalog=dict(demos=[dict(alias='ros-run-P01',physical_start_enabled=True,
                                     profile_revision=row['profile_revision'])])
        self.job=dict(run_id='123',state='RUNNING')
    def run_job(self,cancel=lambda:False):
        return self.client.run(self.goal,feedback=lambda _:None,cancelled=cancel)
    def test_verified_final_result(self):
        end=dict(self.job,state='SUCCEEDED',result=dict(success=True,terminal_state='HELD_CONFIRMED'))
        self.client.call=Mock(side_effect=[self.catalog,self.job,end])
        self.assertTrue(self.run_job()['success'])
    def test_http_success_without_postcondition_fails(self):
        self.client.call=Mock(side_effect=[self.catalog,dict(self.job,state='SUCCEEDED')])
        self.assertFalse(self.run_job()['success'])
    def test_lost_start_ack_no_replay(self):
        self.client.call=Mock(side_effect=[self.catalog,TimeoutError('lost')])
        self.assertEqual(self.run_job()['terminal_state'],'UNCERTAIN')
        self.assertEqual(self.client.call.call_count,2)
    def test_different_run_never_accepted(self):
        self.client.call=Mock(side_effect=[self.catalog,self.job,dict(self.job,run_id='other')])
        self.assertEqual(self.run_job()['code'],'RUN_BINDING_CHANGED')
    def test_cancel_is_bound_to_exact_run_and_waits(self):
        checks=iter([False,True])
        end=dict(self.job,state='RECOVERY_REQUIRED')
        self.client.call=Mock(side_effect=[self.catalog,self.job,{},end])
        self.assertEqual(self.run_job(lambda:next(checks))['terminal_state'],'UNCERTAIN')
        self.assertIn((('business_stop','123'),),[tuple(c)[:1] for c in self.client.call.call_args_list])
    def test_release_disabled_no_start(self):
        self.catalog['demos'][0]['physical_start_enabled']=False
        self.client.call=Mock(return_value=self.catalog)
        self.assertEqual(self.run_job()['code'],'BLOCK_NOT_RELEASED')
        self.assertEqual(self.client.call.call_count,1)
