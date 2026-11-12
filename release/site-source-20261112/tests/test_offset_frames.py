import copy
import tempfile
import time
import unittest
import numpy as np
from ares_r.offset_frames import R_BODY_DETECTION,convert_offset,offset_context
from ares_r.operations import OperationsRegistry,initial_state
from ares_r.perception.robot_collision import transform_xyz_rpy


class OffsetFramesTests(unittest.TestCase):
    def test_operator_axes_are_right_handed(self):
        np.testing.assert_allclose(np.linalg.det(R_BODY_DETECTION),1)
        for v,expected in [([.1,0,0,0,0,0],[0,-.1,0]),([0,.1,0,0,0,0],[0,0,-.1]),
                           ([0,0,.1,0,0,0],[.1,0,0])]:
            np.testing.assert_allclose(convert_offset(v,'DETECTION','BODY')[:3],expected)
        np.testing.assert_allclose(convert_offset([.1,.2,.3,0,0,0],'DETECTION','BODY'),[.3,-.1,-.2,0,0,0])

    def test_rotations_conjugate_not_rpy_component_swap(self):
        rng=np.random.default_rng(16)
        for value in [*[rng.uniform(-1,1,size=6) for _ in range(60)],
                      [0,0,0,0,np.pi/2,0],[0,0,0,.7,-np.pi/2,1.1]]:
            b=convert_offset(value,'DETECTION','BODY')
            back=convert_offset(b,'BODY','DETECTION')
            np.testing.assert_allclose(transform_xyz_rpy(back[:3],back[3:]),
                transform_xyz_rpy(value[:3],value[3:]),atol=1e-10)
            expected=R_BODY_DETECTION@transform_xyz_rpy(value[:3],value[3:])[:3,:3]@R_BODY_DETECTION.T
            np.testing.assert_allclose(transform_xyz_rpy(b[:3],b[3:])[:3,:3],expected,atol=1e-10)

    def test_invalid_frames_and_nonfinite_rejected(self):
        for source,target,value in [('TCP','BODY',[0]*6),('BODY','CAMERA',[0]*6),
                                    ('BODY','DETECTION',[float('nan')]*6)]:
            with self.assertRaises(ValueError):convert_offset(value,source,target)

    def test_fresh_actual_rotation_and_stale_fallback(self):
        state=initial_state();r=transform_xyz_rpy([0]*3,[0,0,.3])[:3,:3]@R_BODY_DETECTION
        t=np.eye(4);t[:3,:3]=r
        state['dryer'].update(anchor={'T_body_corner':t.tolist(),'captured_at_unix':time.time(),
            'base_pose_revision':4,'observation_epoch':2},anchor_revision='A')
        live={'state':'READY','base_pose_revision':4,'scene_epoch':2}
        context=offset_context(state,live)
        self.assertTrue(context['live_anchor_valid']);np.testing.assert_allclose(context['R_body_detection'],r)
        self.assertFalse(context['detection_frame_is_tcp_frame'])
        for scene in [dict(live,state='STALE'),dict(live,base_pose_revision=5),dict(live,scene_epoch=3)]:
            c=offset_context(state,scene);self.assertFalse(c['live_anchor_valid'])
            np.testing.assert_allclose(c['R_body_detection'],R_BODY_DETECTION)

    def test_read_only_toggle_and_body_save_canonical(self):
        with tempfile.TemporaryDirectory() as directory:
            registry=OperationsRegistry(directory);before=registry.read();context=offset_context(before)
            value=[.01,.02,.03,.2,-.3,.4]
            converted=registry.convert_offsets({'from_frame':'DETECTION','to_frame':'BODY',
                'offset_context_revision':context['revision'],'offsets':{'lower_middle':value}})
            self.assertEqual(registry.read(),before)
            registry.update('slot',{'expected_revision':0,'slot_id':'lower_middle',
                'offset_m_rad':converted['offsets']['lower_middle'],'offset_frame':'BODY',
                'offset_context_revision':context['revision']})
            saved=registry.read()['dryer']['slots']['lower_middle']
            self.assertEqual(saved['offset_frame'],'DETECTION')
            np.testing.assert_allclose(transform_xyz_rpy(saved['offset_m_rad'][:3],saved['offset_m_rad'][3:]),
                transform_xyz_rpy(value[:3],value[3:]),atol=1e-12)

    def test_stale_context_rejected_and_legacy_offsets_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            registry=OperationsRegistry(directory)
            registry.update('slot',{'expected_revision':0,'slot_id':'lower_left','offset_m_rad':[.1,0,0,0,0,0]})
            self.assertEqual(registry.read()['dryer']['slots']['lower_left']['offset_m_rad'],[.1,0,0,0,0,0])
            with self.assertRaises(ValueError):registry.update('slot',{'expected_revision':1,'slot_id':'lower_left',
                'offset_m_rad':[1]*6,'offset_frame':'BODY','offset_context_revision':'old'})
            self.assertEqual(registry.read()['revision'],1)

    def test_target_is_same_pose_after_body_input_and_uses_full_anchor_se3(self):
        with tempfile.TemporaryDirectory() as directory:
            registry=OperationsRegistry(directory);t=np.eye(4);t[:3,:3]=R_BODY_DETECTION;t[:3,3]=[.5,.1,.8]
            registry.update('anchor',{'expected_revision':0,'profile':'dryer_place_corner',
                'T_body_corner':t.tolist(),'captured_at_unix':time.time(),'base_pose_revision':4,'observation_epoch':2})
            scene={'state':'READY','base_pose_revision':4,'scene_epoch':2};ctx=offset_context(registry.read(),scene)
            registry.update('slot',{'expected_revision':1,'slot_id':'lower_middle','offset_frame':'BODY',
                'offset_context_revision':ctx['revision'],'offset_m_rad':[.3,-.1,-.2,0,0,0]},scene_context=scene)
            target=registry.target('lower_middle',4,2)
            np.testing.assert_allclose(target['position_m'],[.8,0,.6],atol=1e-12)
            np.testing.assert_allclose(target['explicit_rotation'],R_BODY_DETECTION)
