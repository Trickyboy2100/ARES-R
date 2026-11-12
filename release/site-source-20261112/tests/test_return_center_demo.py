import importlib.util,io,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('return_center_demo',ROOT/'scripts/run_return_center_demo.py')
demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)


class _Response:
    def __init__(self,payload):self._buffer=io.BytesIO(json.dumps(payload).encode())
    def __enter__(self):return self._buffer
    def __exit__(self,*args):return False


class ReturnCenterDemoTests(unittest.TestCase):
    """Regression guards for the two fields the canonical backend validates."""
    def _capture(self,calls):
        sent=[]
        def fake(request,timeout=None):
            sent.append((request.full_url,json.loads(request.data) if request.data else None))
            return _Response({})
        with patch.object(demo,'urlopen',fake):
            for path,body in calls:demo.api(path,body)
        return sent

    def test_motion_api_authorization_is_the_backend_phrase(self):
        # canonical_backend._motion_execute_once rejects anything else with 409.
        self.assertEqual(demo.MOTION_API_AUTHORIZATION,'RIGHT SCENE_AWARE SUPERVISED')
        source=(ROOT/'src/ares_r/canonical_backend.py').read_text()
        self.assertIn("body.get('authorization') != 'RIGHT SCENE_AWARE SUPERVISED'",source)

    def test_console_token_attached_only_to_guarded_endpoints(self):
        # DemoConsole.permits() blocks motion_execute from a child that omits the token.
        demo.CONSOLE_TOKEN='console-token'
        try:
            sent=self._capture([('/api/operations/execute',{'plan_id':'P'}),
                                ('/api/motion/plan',{'goal':1}),
                                ('/api/operations/telemetry',{})])
        finally:
            demo.CONSOLE_TOKEN=None
        self.assertEqual(sent[0][1],{'plan_id':'P','demo_console_token':'console-token'})
        self.assertEqual(sent[1][1],{'goal':1})
        self.assertEqual(sent[2][1],{})

    def test_no_console_token_outside_the_console(self):
        demo.CONSOLE_TOKEN=None
        sent=self._capture([('/api/operations/execute',{'plan_id':'P'})])
        self.assertEqual(sent[0][1],{'plan_id':'P'})


class TransientRetryTests(unittest.TestCase):
    """Only the proven zero-motion controller-gate transient may be retried."""
    JOINTS=[-4.123,-0.018,-1.507,-2.389,1.208,3.575]
    def _out(self,root,**state):
        out=Path(root);value=dict(state='FAULT',failure_reason=(
            'controller safety gate errcode=4128769 power=1 enabled=1 estop=0 '
            'collision=0 limit=0 drag=0'),execution_result=dict(sample_count=0))
        value.update(state)
        (out/'run-status.json').write_text(json.dumps(value))
        (out/'telemetry-dispatch.json').write_text(json.dumps(
            dict(arms=dict(right=dict(joints_rad=list(self.JOINTS))))))
        return out
    def _live(self,errcode=0,joints=None):
        return dict(arms=dict(right=dict(controller_status=dict(errcode=errcode),
                                        joints_rad=list(joints if joints is not None else self.JOINTS))))
    def _check(self,out,live):
        with patch.object(demo,'api',lambda path,body=None,timeout=900:live):
            return demo.transient_zero_motion_failure(out)

    def test_accepts_the_known_zero_motion_gate(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(self._check(self._out(d),self._live()))

    def test_refuses_when_the_arm_already_moved(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(self._check(self._out(d,execution_result=dict(sample_count=257)),self._live()))

    def test_refuses_any_other_failure(self):
        with tempfile.TemporaryDirectory() as d:
            out=self._out(d); path=out/'run-status.json'
            path.write_text(json.dumps(dict(state='FAULT',failure_reason='native motion fault',
                                            execution_result=dict(sample_count=0))))
            self.assertFalse(self._check(out,self._live()))

    def test_refuses_while_the_controller_reports_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(self._check(self._out(d),self._live(errcode=4128769)))

    def test_refuses_when_joints_differ_from_the_planned_start(self):
        with tempfile.TemporaryDirectory() as d:
            moved=list(self.JOINTS);moved[2]+=0.05      # ~2.9 deg
            self.assertFalse(self._check(self._out(d),self._live(joints=moved)))


class ResidualStartCollisionTests(unittest.TestCase):
    """2026-11-11: an unchanged pose was blocked by a 2 mm residual cluster."""
    def report(self,*rows,**extra):
        worst=[dict(object=name,clearance_m=value,clearance_mm=value*1000)
               for name,value in rows]
        return dict(checked_objects=125,penetrating_count=len(worst),worst=worst,**extra)

    def test_sub_centimetre_residual_cluster_earns_one_rescan(self):
        report=self.report(('observed_remaining_observed_unknown_occupied_000',-0.002064))
        self.assertTrue(demo.residual_start_collision(report))

    def test_any_other_object_class_still_refuses(self):
        for name in ('observed_support_01_support_surface_023',
                     'observed_remaining_structure_structure_002',
                     'attached_object'):
            self.assertFalse(demo.residual_start_collision(self.report((name,-0.002))))

    def test_deep_penetration_or_many_offenders_still_refuses(self):
        deep=self.report(('observed_remaining_observed_unknown_occupied_000',-0.0135))
        self.assertFalse(demo.residual_start_collision(deep))
        many=dict(self.report(('observed_remaining_observed_unknown_occupied_000',-0.002)),
                  penetrating_count=3)
        self.assertFalse(demo.residual_start_collision(many))

    def test_clean_report_never_triggers_the_rescan(self):
        self.assertFalse(demo.residual_start_collision(self.report()))


class CenterBranchTests(unittest.TestCase):
    """2026-11-11 13:29: the planner chose the wrist branch that needs 162.7 deg on J6."""
    START = [-4.065010, -1.484233, 1.076923, -4.719591, -0.533383, 0.735010]  # rad, measured
    PARAMS = dict(ik_seeds_rad=[
        [-4.119722, -0.012392, -1.508488, -2.387774, 1.214109, 3.574740],   # flipped
        [-4.189835, 0.002792, -1.490986, 0.713493, -1.313185, 0.468981],    # canonical
    ])

    def test_travel_is_wrapped_to_the_nearest_equivalent(self):
        travel = demo.seed_travel_deg([0.0] * 6, [0.0, 0.0, 0.0, -4.719591, 0.0, 0.0])
        self.assertAlmostEqual(travel[3], -89.584, places=2)   # +270.4 deg is the same as -89.6
        self.assertAlmostEqual(demo.seed_travel_deg([0.713493], [-4.719591])[0], -48.7, places=1)

    def test_only_the_branch_inside_the_leg_envelope_is_offered(self):
        rows = demo.feasible_center_seeds(self.PARAMS, self.START)
        self.assertEqual([row['feasible'] for row in rows], [False, True])
        self.assertAlmostEqual(rows[0]['worst_deg'], 162.7, places=1)
        self.assertAlmostEqual(rows[1]['worst_deg'], 147.13, places=1)
        self.assertEqual(len(rows[1]['seed']), 6)

    def test_seed_is_offered_in_the_representation_nearest_the_current_pose(self):
        rows = demo.feasible_center_seeds(self.PARAMS, self.START)
        near = rows[1]['seed_near_start']
        for original, sent in zip(rows[1]['seed'], near):
            offset = math.degrees(sent - original) / 360.0
            self.assertAlmostEqual(offset, round(offset), places=6)
        self.assertAlmostEqual(math.degrees(near[3]), -319.12, places=1)   # not +40.88
        self.assertLessEqual(max(abs(math.degrees(a - b)) for a, b in zip(near, self.START)), 150.0)

    def test_limit_is_inclusive(self):
        start = [0.0] * 6
        params = dict(ik_seeds_rad=[[math.radians(150.0), 0.0, 0.0, 0.0, 0.0, 0.0]])
        self.assertTrue(demo.feasible_center_seeds(params, start)[0]['feasible'])
        params = dict(ik_seeds_rad=[[math.radians(150.5), 0.0, 0.0, 0.0, 0.0, 0.0]])
        self.assertFalse(demo.feasible_center_seeds(params, start)[0]['feasible'])


if __name__=='__main__':unittest.main()
