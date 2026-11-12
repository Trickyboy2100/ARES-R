import copy
import time
import unittest
from ares_r.motion.arrival_confirmation import inspect_sample, confirm_arrival


class ArrivalTest(unittest.TestCase):
    def setUp(self):
        self.goal = dict(position_m=[0,0,0], explicit_rotation=[[1,0,0],[0,1,0],[0,0,1]])
        self.tol = dict(position_m=.003, orientation_deg=3)
        self.live = dict(captured_at_unix=time.time(),errors={},arms={'right': dict(
            T_body_tcp=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],joints_rad=[0]*6,
            controller_status=dict(errcode=0,emergency_stop=False,protective_stop=False,on_soft_limit=False,
                                   drag_mode=False,powered_on=True,enabled=True,in_position=True,tool_id=3,user_frame_id=0))})
        self.execution = dict(state='SUCCEEDED',execution_result=dict(success=True,target_reached=True,servo_disabled_confirmed=True,aborted=False))

    def sample(self):
        return inspect_sample(self.live,self.goal,self.live,self.tol,time.time())

    def test_valid(self):
        self.assertTrue(self.sample()['passed'])

    def test_stale(self):
        self.live['captured_at_unix']-=20
        self.assertIn('STALE_STATE',self.sample()['reasons'])

    def test_bad_pose_and_nan(self):
        self.live['arms']['right']['T_body_tcp'][0][3]=.01
        self.assertFalse(self.sample()['passed'])
        self.live['arms']['right']['T_body_tcp'][0][3]=float('nan')
        self.assertIn('TCP_INVALID',self.sample()['reasons'])

    def test_controller_error(self):
        self.live['arms']['right']['controller_status']['errcode']=1
        self.assertFalse(self.sample()['passed'])

    def test_tool_change(self):
        before=copy.deepcopy(self.live)
        self.live['arms']['right']['controller_status']['tool_id']=2
        self.assertIn('TOOL_USER_CHANGED',inspect_sample(self.live,self.goal,before,self.tol,time.time())['reasons'])

    def test_three_distinct_reads(self):
        def read():
            self.live['captured_at_unix']=time.time();return copy.deepcopy(self.live)
        r=confirm_arrival(read,self.goal,self.live,self.tol,self.execution,interval_s=.001)
        self.assertEqual(r['outcome'],'ARRIVED_CONFIRMED')
        self.assertEqual(r['consecutive_samples'],3)

    def test_repeated_snapshot_not_success(self):
        r=confirm_arrival(lambda:self.live,self.goal,self.live,self.tol,self.execution,timeout_s=.01,interval_s=.001)
        self.assertFalse(r['passed'])

    def test_fault_at_goal_not_success(self):
        self.execution['state']='FAULT'
        r=confirm_arrival(lambda:self.live,self.goal,self.live,self.tol,self.execution)
        self.assertEqual(r['outcome'],'EXECUTION_FAILED')

    def test_servo_off_required(self):
        self.execution['execution_result']['servo_disabled_confirmed']=False
        r=confirm_arrival(lambda:self.live,self.goal,self.live,self.tol,self.execution)
        self.assertFalse(r['passed'])

    def test_unstable_joints(self):
        value=[0]
        def read():
            value[0]+=1;self.live['captured_at_unix']=time.time()
            self.live['arms']['right']['joints_rad'][0]=value[0]*.01
            return copy.deepcopy(self.live)
        r=confirm_arrival(read,self.goal,self.live,self.tol,self.execution,timeout_s=.01,interval_s=.001)
        self.assertFalse(r['passed'])
