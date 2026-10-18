import math
import unittest
from unittest.mock import patch
import numpy as np
from ares_r.manipulation.contact_lift_precheck import precheck_contact_lift
from ares_r.motion.runtime_goal_ik import RuntimeIKResult
from ares_r.motion.tcp_orientation import HORIZONTAL_FORWARD_R_BODY


class DiagnosticSolver:
    lower=np.full(6,-10);upper=np.full(6,10)
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def solve_diagnostic(self,xyz,rotation,seed):
        self.calls.append(list(xyz))
        return RuntimeIKResult(tuple(seed),.00751 if self.fail else 0,math.radians(2.66) if self.fail else 0)
    def fk(self,q):
        value=np.eye(4);value[:3,:3]=HORIZONTAL_FORWARD_R_BODY;return value


class PrecheckTests(unittest.TestCase):
    def run_check(self,solver,**kwargs):
        return precheck_contact_lift(solver,[.8,-.2,1.],HORIZONTAL_FORWARD_R_BODY,[1,0,0],[[0]*6],**kwargs)
    def test_complete_contact_lift_both_symmetries_before_planner(self):
        solver=DiagnosticSolver();result=self.run_check(solver)
        self.assertTrue(result['passed']);self.assertEqual(len(result['accepted']),2)
        self.assertEqual(len(solver.calls),154)
        self.assertEqual([b['symmetry_id'] for b in result['branches']],['NORMAL','FLIPPED_180'])
        np.testing.assert_allclose(solver.calls[0],[.745,-.2,1.])
        np.testing.assert_allclose(solver.calls[76],[.8,-.2,1.1])
    def test_full_failure_curves_not_just_first_bad_knot(self):
        result=self.run_check(DiagnosticSolver(fail=True))
        self.assertFalse(result['passed'])
        for branch in result['branches']:
            self.assertTrue(branch['complete']);self.assertEqual(len(branch['samples']),77)
            self.assertAlmostEqual(branch['max_position_error_m'],.00751)
            self.assertAlmostEqual(branch['max_orientation_error_deg'],2.66)
    def test_budget_exhaustion_never_marks_partial_curve_feasible(self):
        with patch('ares_r.manipulation.contact_lift_precheck.time.monotonic',side_effect=[0,1,2]):
            result=self.run_check(DiagnosticSolver(),budget_s=.1)
        self.assertFalse(result['passed']);self.assertTrue(result['timed_out'])
        self.assertFalse(result['branches'][0]['complete'])
    def test_no_quality_retry_on_contact_failure(self):
        from ares_r.manipulation.roundtrip_demo import plan_with_retries
        calls=[]
        def attempt(mode,index):
            calls.append(mode);raise RuntimeError('CONTACT_IK_NO_FEASIBLE_BRANCH')
        with self.assertRaisesRegex(RuntimeError,'CONTACT_IK'):
            plan_with_retries({'planning_attempt_modes':['FAST','QUALITY','QUALITY'],'max_planning_attempts':3},
                              attempt,lambda *a:None,lambda:None)
        self.assertEqual(calls,['FAST'])
