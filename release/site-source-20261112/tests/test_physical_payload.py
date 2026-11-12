import unittest
import numpy as np
from ares_r.manipulation.physical_payload import validate_profile,build_physical_attachment
from ares_r.manipulation.attached_collision import verify_attached_collision


class PhysicalPayloadTests(unittest.TestCase):
    def profile(self):
        return {'schema_version':1,'revision':'MEASURED_TEST','geometry_source':'OPERATOR_PHYSICAL_OBJECT',
          'dimensions_m':[.18,.10,.02],'T_tcp_object':np.eye(4).tolist(),'inflation_m':.004}
    def build(self,p,points=None,protected=()):
        if points is None:points=[[0,0,0],[.08,.04,.009],[.20,.20,.10]]
        return build_physical_attachment(p,object_id='TARGET',observation_id='OBS',T_body_tcp=np.eye(4),
          T_link6_tcp=np.eye(4),points_body=points,pointcloud_sha256='FROZEN',protected_boxes=protected)
    def test_dimensions_never_come_from_oversized_point_cluster(self):
        a=self.build(self.profile());self.assertEqual(a['object_dimensions_m'],[.18,.10,.02])
        self.assertEqual(a['physical_model_provenance']['source_points_bound'],2)
        self.assertFalse(a['physical_model_provenance']['perception_cluster_defines_dimensions'])
        self.assertTrue(verify_attached_collision(a))
    def test_unknown_thickness_or_grasp_anchor_not_guessed(self):
        p=self.profile();p['dimensions_m'][2]=None
        with self.assertRaisesRegex(ValueError,'THICKNESS'):validate_profile(p)
        p=self.profile();p['T_tcp_object']=None
        with self.assertRaisesRegex(ValueError,'GRASP_ANCHOR'):validate_profile(p)
    def test_grasp_anchor_positions_whole_object_without_cutting_it(self):
        p=self.profile();p['T_tcp_object'][0][3]=.06
        a=self.build(p,[[.06,0,0],[.14,0,0],[-.02,0,0]])
        self.assertEqual(a['object_dimensions_m'],[.18,.10,.02])
        self.assertAlmostEqual(a['link6_aabb']['center_m'][0],.06)
    def test_support_protected_and_empty_binding_rejected(self):
        support={'observed_bounds_m':[[-1,-1,-1],[1,1,1]]}
        with self.assertRaisesRegex(RuntimeError,'NO_SOURCE_POINT_BINDING'):
            self.build(self.profile(),protected=[support])
    def test_model_revision_changes_with_physical_dimensions(self):
        a=self.build(self.profile());p=self.profile();p['dimensions_m'][0]=.17
        self.assertNotEqual(a['revision'],self.build(p)['revision'])

    def test_demo_exposed_override_retains_rear20_and_original_height(self):
        from ares_r.manipulation.physical_payload import demo_exposed_payload_override
        a=self.build(self.profile())
        result=demo_exposed_payload_override(a,T_body_grasp_tcp=np.eye(4),T_body_grasp_link6=np.eye(4),
            points_body=[[0,0,0],[.14,0,0],[-.015,0,0],[.3,0,0]],pointcloud_sha256='SOURCE',reanchor_from_grasp=True)
        self.assertEqual(result['object_dimensions_m'],[.160,.100,.020])
        self.assertAlmostEqual(result['T_link6_object'][0][3],.080)
        self.assertAlmostEqual(result['link6_aabb']['center_m'][0]-.5*result['link6_aabb']['dims_m'][0],-.024)
        self.assertAlmostEqual(result['link6_aabb']['center_m'][0]+.5*result['link6_aabb']['dims_m'][0],.164)
        self.assertEqual(result['clamped_segment']['dimensions_m'],[.020,.100,.020])
        self.assertEqual(len(result['point_ownership']['points_link6_m']),3)
        self.assertEqual(a['object_dimensions_m'],[.18,.10,.02])
        self.assertTrue(verify_attached_collision(result))

    def test_size_only_override_does_not_silently_shift_original_pose(self):
        from ares_r.manipulation.physical_payload import demo_exposed_payload_override
        a=self.build(self.profile())
        b=demo_exposed_payload_override(a,T_body_grasp_tcp=np.eye(4),T_body_grasp_link6=np.eye(4),
            points_body=[[0,0,0],[.05,0,0],[-.09,0,0]],pointcloud_sha256='SOURCE')
        self.assertTrue(np.allclose(a['T_link6_object'],b['T_link6_object']))
        self.assertTrue(b['physical_model_provenance']['source_center_and_rotation_preserved'])
        self.assertEqual(b['object_dimensions_m'],[.16,.1,.02])
