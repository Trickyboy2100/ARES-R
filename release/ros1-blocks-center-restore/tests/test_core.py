import unittest,tempfile,json,hashlib,copy
from pathlib import Path
from center_restore.core import resolve_target,unchanged_source,sequence
P=dict(arm='right',pose_id='right/example',joints_rad=[.1]*6,T_body_tcp=[[1,0,0,.4],[0,1,0,-.3],[0,0,1,1.5],[0,0,0,1]],tool_id=3,evidence='evidence')


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name);(self.root/'config').mkdir();(self.root/'evidence').mkdir()
        f=self.root/'evidence/actual-measured-record.json';f.write_text(json.dumps(P));self.path=f
        (self.root/'config/arm_pose_registry.json').write_text(json.dumps({'poses':{'right/example':P}}))
        self.goal=dict(request_id='test',target_mode='SAVED_POSE_REF',saved_pose_id='right/example',expected_saved_pose_sha=hashlib.sha256(f.read_bytes()).hexdigest())
    def tearDown(self):self.d.cleanup()
    def test_resolve_real_record(self):self.assertEqual(resolve_target(self.root,self.goal,{})[0],P)
    def test_capture_not_saved(self):
        g=dict(request_id='capture',target_mode='CAPTURE_START');t=dict(captured_at_unix=1,arms={'right':P})
        a,pin=resolve_target(self.root,g,t);self.assertIsNone(pin);self.assertNotEqual(a['pose_id'],P['pose_id'])
    def test_wrong_revision(self):
        self.goal['expected_saved_pose_sha']='wrong'
        with self.assertRaisesRegex(ValueError,'REVISION_CHANGED'):resolve_target(self.root,self.goal,{})
    def test_mutated_after_pin(self):
        _,pin=resolve_target(self.root,self.goal,{})
        self.path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'REVISION_CHANGED'):unchanged_source(self.root,self.goal,pin)
    def test_unknown_mode(self):
        self.goal['target_mode']='AUTO'
        with self.assertRaises(ValueError):resolve_target(self.root,self.goal,{})
    def test_joint_wrong_shape(self):
        t=copy.deepcopy(P);t['joints_rad']=[0];self.path.write_text(json.dumps(t));(self.root/'config/arm_pose_registry.json').write_text(json.dumps({'poses':{'right/example':t}}))
        with self.assertRaisesRegex(ValueError,'INVALID_SAVED_JOINTS'):resolve_target(self.root,self.goal,{})
    def trial(self,fail=None,execute=True):
        class A:
            def event(s,*a):pass
            def bindings_valid(s,t):pass
            def plan(s,leg,t):
                if fail==leg:raise RuntimeError('injected failure')
                return {'fresh_plan_id':leg}
            def execute(s,leg,p,t):return {'passed':True}
        return sequence(A(),P,execute)
    def test_both_legs(self):self.assertTrue(self.trial()['return_to_saved_pose_verified'])
    def test_center_fail(self):self.assertEqual(self.trial('center_leg')['terminal_state'],'FAULT')
    def test_restore_fail_partial(self):self.assertEqual(self.trial('restore_leg')['terminal_state'],'CENTER_ARRIVED_RESTORE_FAILED')
    def test_no_motion_prepare_not_execution(self):self.assertFalse(self.trial(execute=False)['return_to_saved_pose_verified'])
    def test_bindings_changed(self):
        class A:
            def event(s,*a):pass
            def bindings_valid(s,t):raise RuntimeError('TOOL_REVISION_CHANGED')
        self.assertFalse(sequence(A(),P,True)['success'])
