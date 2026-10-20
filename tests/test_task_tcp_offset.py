import json,copy,unittest
from pathlib import Path
import numpy as np
from ares_r.manipulation.task_tcp_offset import apply_task_pose,validate_offset,offset_revision,validate_body_descent
from ares_r.manipulation.roundtrip_demo import recipe
from ares_r.manipulation.roundtrip_replay import RoundtripReplayTransport
ROOT=Path(__file__).resolve().parents[1]

class TaskTcpOffsetTests(unittest.TestCase):
    def test_zero_identity(self):
        xyz=np.array([.7,-.2,1.2]);rotation=np.eye(3)
        p,r=apply_task_pose(xyz,rotation,[0]*6)
        np.testing.assert_array_equal(p,xyz);np.testing.assert_array_equal(r,rotation)
    def test_body_translation_and_rotation_do_not_rotate_position(self):
        p,r=apply_task_pose([1,2,3],np.eye(3),[.01,-.02,.03,0,0,np.pi/2])
        np.testing.assert_allclose(p,[1.01,1.98,3.03])
        np.testing.assert_allclose(r@[1,0,0],[0,1,0],atol=1e-12)
    def test_invalid_and_revision(self):
        for x in ([0]*5,[0]*5+[float('nan')],[0]*5+[True]):
            with self.assertRaises(ValueError):validate_offset(x)
        self.assertNotEqual(offset_revision([0]*6),offset_revision([.001,0,0,0,0,0]))
    def test_release_follows_descent_and_legacy_has_no_new_stage(self):
        p=json.loads((ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
        route=json.loads((ROOT/p['base_route']).read_text())
        self.assertEqual(len(recipe(p,route)),20)
        old=copy.deepcopy(p);old.pop('place_descent_enabled')
        old['center_before_pick']=False;old['center_after_release']=False;old['return_mode']='RETRACE_ONLY_NO_STOW'
        old.pop('lift_execution_mode',None)
        self.assertEqual(len(recipe(old,route)),19)
        sim=RoundtripReplayTransport(p);sim.preland=True;sim.closed=True;sim.attached=True
        with self.assertRaisesRegex(RuntimeError,'descent'):sim.gripper(400)
        sim.place_descend(.05);sim.gripper(400)
    def test_descent_axis_gate(self):
        def fk(q):
            t=np.eye(4);t[:3,3]=q[:3];return t
        proof=validate_body_descent([[0,0,1,0,0,0],[0,0,.95,0,0,0]],fk,.05)
        self.assertTrue(proof['passed'])
        for end in ([.01,0,.95,0,0,0],[0,0,.90,0,0,0],[0,0,1.05,0,0,0]):
            with self.assertRaises(RuntimeError):validate_body_descent([[0,0,1,0,0,0],end],fk,.05)
