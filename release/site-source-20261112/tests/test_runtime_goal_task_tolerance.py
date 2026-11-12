import math,unittest
from unittest.mock import Mock
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK,RuntimeIKResult,solve_runtime_goal

class RuntimeTaskToleranceTests(unittest.TestCase):
    def solver(self,mm=1.845,deg=.797):
        s=object.__new__(RuntimeGoalIK)
        s.solve_diagnostic=Mock(return_value=RuntimeIKResult((0,)*6,mm/1000,math.radians(deg)))
        s.lower=np.full(6,-6.);s.upper=-s.lower
        return s
    def test_old_default_remains_strict_new_task_contract_accepts_recorded_failure(self):
        s=self.solver()
        with self.assertRaises(ValueError):s.solve([0]*3,np.eye(3),[0]*6)
        answer,_=solve_runtime_goal(s,[0]*3,np.eye(3),[0]*6,
            {'position_tolerance_m':.003,'orientation_tolerance_deg':3.})
        self.assertAlmostEqual(answer.position_error_m,.001845)
    def test_bounded_multiseed_recovers_without_waypoints(self):
        s=self.solver();s.solve=Mock(side_effect=[ValueError('local minimum'),RuntimeIKResult((0,)*6,0,0)])
        _,errors=solve_runtime_goal(s,[0]*3,np.eye(3),[0]*6,{})
        self.assertEqual(s.solve.call_count,2);self.assertEqual(len(errors),1)
    def test_outside_task_tolerance_still_rejected_and_bounded(self):
        s=self.solver(mm=3.1)
        with self.assertRaisesRegex(ValueError,'NO_ACCEPTED_SEED'):
            solve_runtime_goal(s,[0]*3,np.eye(3),[0]*6,{'ik_seed_joints_rad':[[1]*6]*10})
        self.assertEqual(s.solve_diagnostic.call_count,4)
    def test_angular_limit_retained(self):
        s=self.solver(mm=0,deg=3.1)
        with self.assertRaises(ValueError):solve_runtime_goal(s,[0]*3,np.eye(3),[0]*6,{})
