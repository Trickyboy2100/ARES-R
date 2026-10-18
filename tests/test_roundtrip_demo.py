import copy
import json
from pathlib import Path
import unittest

from ares_r.manipulation.roundtrip_demo import (CycleRunner, recipe, validate_parameters,
    digest, PlanningAttemptFailure, plan_with_retries)

ROOT=Path(__file__).resolve().parents[1]


class RoundtripDemoTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        self.route=json.loads((ROOT/'config/grasp_place_base_route.json').read_text())

    def test_recipe_and_inverse_route(self):
        stages=recipe(self.p,self.route)
        deltas=[s['arguments']['delta'] for s in stages if s['call']=='base']
        self.assertEqual(deltas,[[-.3,0,0],[0,-.85,0],[.3,0,0],[-.3,0,0],[0,.85,0],[.3,0,0]])
        self.assertEqual([sum(row[i] for row in deltas) for i in range(3)],[0,0,0])
        names=[s['id'] for s in stages]
        self.assertLess(names.index('VERIFY_GRASP'),names.index('LIFT_INITIAL100'))
        self.assertLess(names.index('ATTACH'),names.index('LIFT_TO_HOLD230'))
        self.assertNotIn('STOW_RIGHT_AFTER_SETTLE',names)
        self.assertFalse(any(s['call']=='stow' for s in stages))
        self.assertLess(names.index('RETREAT_BASE030'),names.index('RETURN_LEFT085'))

    def test_230mm_is_not_contact_bypass_extension(self):
        self.assertEqual(self.p['initial_contact_lift_m'],.10)
        self.assertAlmostEqual(self.p['additional_free_lift_m'],.13)
        self.assertAlmostEqual(self.p['total_lift_m'],.23)

    def test_default_no_physical_authority(self):
        self.assertFalse(self.p['review_approved'])
        self.assertFalse(self.p['concurrent_base_arm_enabled'])

    def test_parallel_base_arm_not_silently_allowed(self):
        self.p['concurrent_base_arm_enabled']=True
        with self.assertRaises(ValueError):validate_parameters(self.p)

    def test_fallback_policy_explicit_and_bounded(self):
        self.p['max_planning_attempts']=4
        with self.assertRaises(ValueError):validate_parameters(self.p)

    def test_no_stow_can_be_reenabled(self):
        self.p['stow_enabled']=True
        with self.assertRaises(ValueError):validate_parameters(self.p)

    def test_three_plans_maximum_and_fallback_sequence(self):
        for succeed_at in (1,2,3,None):
            modes=[];events=[]
            def attempt(mode,index):
                modes.append(mode)
                if index==succeed_at:return 'candidate'
                raise PlanningAttemptFailure('no path')
            if succeed_at is None:
                with self.assertRaises(PlanningAttemptFailure):
                    plan_with_retries(self.p,attempt,lambda *e:events.append(e),lambda:None)
                self.assertEqual(len(modes),3)
            else:
                self.assertEqual(plan_with_retries(self.p,attempt,lambda *e:events.append(e),lambda:None),'candidate')
                self.assertEqual(len(modes),succeed_at)
            self.assertEqual(modes,['FAST','QUALITY','QUALITY'][:len(modes)])

    def test_physical_fault_and_cancel_are_not_retried(self):
        modes=[]
        def broken(mode,index):
            modes.append(mode);raise RuntimeError('physical fault')
        with self.assertRaises(RuntimeError):
            plan_with_retries(self.p,broken,lambda *e:None,lambda:None)
        self.assertEqual(modes,['FAST'])
        def cancelled():raise RuntimeError('STOP')
        with self.assertRaises(RuntimeError):
            plan_with_retries(self.p,broken,lambda *e:None,cancelled)
        self.assertEqual(modes,['FAST'])

    def test_no_bypass_widening(self):
        self.p['initial_contact_lift_m']=.23;self.p['additional_free_lift_m']=0
        with self.assertRaises(ValueError):validate_parameters(self.p)

    def test_no_unreviewed_route_change(self):
        self.route['routes']['GRASP_TO_PLACE']['segments'][1]['body_delta_m'][1]=-.4
        with self.assertRaises(ValueError):recipe(self.p,self.route)

    def test_replay_and_failures_never_continue(self):
        for fail_at in (None,'prepare_pick','verify_grasp','lift_remaining','base','move_preland'):
            calls=[];events=[]
            class Mock:
                def check_cancelled(self):pass
                def stop(self):calls.append('stop')
                def __getattr__(self,name):
                    def invoke(**kw):
                        calls.append(name)
                        if name==fail_at:raise RuntimeError(name)
                        return {'mock':True}
                    return invoke
            runner=CycleRunner(self.p,self.route,Mock(),lambda *e:events.append(e))
            if fail_at is None:
                result=runner.run();self.assertEqual(result['result'],'RETURNED_GRASP')
                self.assertEqual(len(calls),19)
            else:
                with self.assertRaises(RuntimeError):runner.run()
                self.assertEqual(calls[-2:],[fail_at,'stop'])
                self.assertEqual(events[-1][1],'FAULT')

    def test_manifest_hash_binds_parameters(self):
        other=copy.deepcopy(self.p);other['total_lift_m']=.1
        self.assertNotEqual(digest(other),digest(self.p))
