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
        self.assertEqual(deltas,[[-.4,0,0],[0,-.81,0],[.32,0,0],[-.32,0,0],[0,.81,0],[.4,0,0]])
        for i in range(3):self.assertAlmostEqual(sum(row[i] for row in deltas),0)
        names=[s['id'] for s in stages]
        self.assertLess(names.index('GRIPPER40'),names.index('MOVE_PREGRASP'))
        self.assertLess(names.index('VERIFY_GRASP'),names.index('LIFT230_CONTINUOUS'))
        self.assertLess(names.index('LIFT230_CONTINUOUS'),names.index('ATTACH'))
        self.assertNotIn('LIFT_INITIAL100',names)
        self.assertNotIn('LIFT_TO_HOLD230',names)
        self.assertLess(names.index('MOVE_PRELAND'),names.index('PLACE_DESCENT50'))
        self.assertLess(names.index('PLACE_DESCENT50'),names.index('RELEASE'))
        self.assertNotIn('STOW_RIGHT_AFTER_SETTLE',names)
        self.assertFalse(any(s['call']=='stow' for s in stages))
        self.assertLess(names.index('RETREAT_BASE032'),names.index('RETURN_LEFT081'))
        self.assertLess(names.index('CENTER_BEFORE_PICK'),names.index('PICK_PREPARE'))
        self.assertNotIn('CENTER_AFTER_RELEASE',names)
        self.assertLess(names.index('DETACH'),names.index('RETREAT_BASE032'))

    def test_route_longitudinal_change_is_version_bound(self):
        bad=copy.deepcopy(self.route)
        bad['routes']['GRASP_TO_PLACE']['segments'][0]['body_delta_m'][0]=-.3
        with self.assertRaisesRegex(ValueError,'route changed'):recipe(self.p,bad)

    def test_legacy_route_remains_replayable(self):
        old=copy.deepcopy(self.route)
        old['revision']='GRASP_PLACE_BODY_ROUTE_2026_10_16_V2_GRASP_LEFT100MM'
        old['routes']['GRASP_TO_PLACE']['segments'][0]['body_delta_m'][0]=-.3
        old['routes']['GRASP_TO_PLACE']['segments'][2]['body_delta_m'][0]=.3
        old['routes']['GRASP_TO_PLACE']['segments'][1]['body_delta_m'][1]=-.85
        names=[s['id'] for s in recipe(self.p,old)]
        self.assertIn('RETREAT_BASE030',names)
        self.assertIn('RETURN_FORWARD030',names)

    def test_previous_85cm_route_still_replayable(self):
        old=copy.deepcopy(self.route)
        old['revision']='GRASP_PLACE_BODY_ROUTE_2026_10_19_V4_PLACE_BACK080_REBOUND'
        old['routes']['GRASP_TO_PLACE']['segments'][1]['body_delta_m'][1]=-.85
        deltas=[s['arguments']['delta'] for s in recipe(self.p,old) if s['call']=='base']
        self.assertEqual(deltas[1],[0,-.85,0]);self.assertEqual(deltas[4],[0,.85,0])

    def test_230mm_is_not_contact_bypass_extension(self):
        self.assertEqual(self.p['initial_contact_lift_m'],.10)
        self.assertAlmostEqual(self.p['additional_free_lift_m'],.13)
        self.assertAlmostEqual(self.p['total_lift_m'],.23)

    def test_default_no_physical_authority(self):
        self.assertFalse(self.p['review_approved'])
        self.assertFalse(self.p['concurrent_base_arm_enabled'])

    def test_versioned_fifteen_second_deadline(self):
        self.assertEqual(self.p['planning_deadline_s'],15)
        validate_parameters(self.p)
        for deadline in (4,0,16,float('inf'),float('nan')):
            bad=copy.deepcopy(self.p);bad['planning_deadline_s']=deadline
            with self.assertRaisesRegex(ValueError,'fifteen-second'):
                validate_parameters(bad)

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

    def test_terminal_model_and_resource_errors_do_not_consume_quality(self):
        for error in ('RESOURCE_EXHAUSTED','INVALID_START_COLLISION','INVALID_GOAL_COLLISION',
                      'CONTACT_IK','CANCEL_NOT_ACKNOWLEDGED','COLLISION_LAUNCH_BUDGET_EXCEEDED'):
            calls=[]
            def failed(mode,index):
                calls.append(mode);raise PlanningAttemptFailure(error)
            with self.assertRaises(PlanningAttemptFailure):
                plan_with_retries(self.p,failed,lambda *a:None,lambda:None)
            self.assertEqual(calls,['FAST'])

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
        for fail_at in (None,'prepare_pick','verify_grasp','pick_segment','base','move_preland'):
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
                self.assertEqual(len(calls),len(recipe(self.p,self.route)))
            else:
                with self.assertRaises(RuntimeError):runner.run()
                self.assertEqual(calls[-2:],[fail_at,'stop'])
                self.assertEqual(events[-1][1],'FAULT')

    def test_manifest_hash_binds_parameters(self):
        other=copy.deepcopy(self.p);other['total_lift_m']=.1
        self.assertNotEqual(digest(other),digest(self.p))
