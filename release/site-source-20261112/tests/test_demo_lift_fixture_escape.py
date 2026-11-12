import copy,unittest
from unittest.mock import patch
import numpy as np
from ares_r.manipulation.continuous_demo_lift import fixture_escape

class FixtureEscapeTests(unittest.TestCase):
    def setUp(self):
        self.box={'center_m':[0,0,0],'half_extents_m':[.02]*3}
        self.request={'T_body_model':np.eye(4).tolist(),'robot_yaml_urdf':'fixture',
          'compiled_scene':{'cuboids':{'observed_fixture':{'dims':[.02]*3,'pose':[0,0,.89,1,0,0,0]},
          'inactive_left':{'dims':[.01]*3,'pose':[1,1,1,1,0,0,0]}}},
          'collision_model':{'gripper_max_envelope_link6':self.box},
          'manipulation_contact_scope':{'target_object_ids':['target']}}
        self.policy={'enabled':True,'scope':'RIGHT_ROUNDTRIP_LIFT230_ONLY','revision':'TEST',
          'operator_confirmed':True,'fixture_bounds_body_m':[[-.04,-.04,.87],[.04,.04,.9]]}
    def run_check(self,heights):
        def frames(path,q):
            t=np.eye(4);t[2,3]=q[0];return {'link6':t}
        with patch('ares_r.perception.robot_collision.arm_link_transforms',frames):
            return fixture_escape([[z]*6 for z in heights],self.request,{'link6_aabb':self.box},.9,self.policy)
    def test_departure_only_and_no_world_deletion(self):
        before=copy.deepcopy(self.request);ids,proof=self.run_check([.9,.95,1.03])
        self.assertEqual(ids,['observed_fixture']);self.assertTrue(proof['arm_world_still_hard'])
        self.assertTrue(proof['expires_after_lift']);self.assertEqual(self.request,before)
    def test_deeper_contact_and_unfinished_departure_rejected(self):
        for path in ([.9,.89,1.03],[.9,.901,.902]):
            with self.assertRaises(RuntimeError):self.run_check(path)
    def test_no_upper_or_large_fixture_exemption(self):
        self.request['compiled_scene']['cuboids']['observed_fixture']['pose'][2]=1.1
        with self.assertRaisesRegex(RuntimeError,'not found'):self.run_check([.9,1.03])
    def test_explicit_demo_scope_and_lower_region_required(self):
        self.policy['scope']='GENERIC_MOTION'
        with self.assertRaisesRegex(RuntimeError,'scope'):self.run_check([.9,1.03])
        self.policy['scope']='RIGHT_ROUNDTRIP_LIFT230_ONLY';self.policy['fixture_bounds_body_m'][1][2]=1.5
        with self.assertRaisesRegex(RuntimeError,'below grasp'):self.run_check([.9,1.03])
    def test_association_tolerance_does_not_shrink_collision_geometry(self):
        self.policy['fixture_bounds_body_m'][0][0]=-.007
        with self.assertRaisesRegex(RuntimeError,'not found'):self.run_check([.9,1.03])
        self.policy['association_tolerance_m']=.01
        before=copy.deepcopy(self.request);ids,proof=self.run_check([.9,1.03])
        self.assertEqual(ids,['observed_fixture']);self.assertEqual(self.request,before)
        self.assertEqual(proof['association_tolerance_m'],.01)
        self.policy['fixture_bounds_body_m'][0][0]=.002
        with self.assertRaisesRegex(RuntimeError,'not found'):self.run_check([.9,1.03])
    def test_fifteen_mm_association_changes_identity_gate_not_collision_geometry(self):
        self.policy['fixture_bounds_body_m'][0][0]=.003
        self.policy['association_tolerance_m']=.01
        with self.assertRaisesRegex(RuntimeError,'not found'):self.run_check([.9,1.03])
        before=copy.deepcopy(self.request);self.policy['association_tolerance_m']=.015
        ids,proof=self.run_check([.9,1.03]);self.assertEqual(ids,['observed_fixture'])
        self.assertEqual(self.request,before);self.assertTrue(proof['other_world_still_hard'])
        self.policy['association_tolerance_m']=.016
        with self.assertRaisesRegex(RuntimeError,'outside'):self.run_check([.9,1.03])
    def test_target_anchor_translates_region_without_inflating_or_deleting_world(self):
        self.policy['reference_grasp_body_m']=[0,0,.9]
        self.request['task_target_pose_body_m_rad']=[.02,0,.9,0,0,0]
        before=copy.deepcopy(self.request);ids,proof=self.run_check([.9,1.03])
        self.assertEqual(ids,['observed_fixture']);self.assertEqual(self.request,before)
        self.assertTrue(proof['target_anchor']['same_dimensions'])
        self.assertAlmostEqual(proof['fixture_bounds_body_m'][0][0],-.02)
        self.request['task_target_pose_body_m_rad'][0]=.061
        with self.assertRaisesRegex(RuntimeError,'beyond60mm'):self.run_check([.9,1.03])
