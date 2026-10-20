import unittest
from types import SimpleNamespace
import numpy as np
from ares_r.perception.support_decomposition import refine_robot_adjacent_primitives

class PayloadRefinementTests(unittest.TestCase):
    def test_empty_bridge_refined_without_point_deletion(self):
        points=np.array([[-.1,0,0],[.1,0,0]])
        p={'primitive_id':'observed','observed_bounds_m':[[-.1,0,0],[.1,0,0]],
           'inflation_m':.007,'dims_m':[.2,.004,.004],'center_m':[0,0,0],'point_count':2}
        report={'primitives':[p],'old_single_aabb_occupied_volume_m3':1.}
        far=SimpleNamespace(center_body_m=(2,2,2),radius_m=.01)
        payload=SimpleNamespace(center_body_m=(0,0,0),radius_m=.02)
        result=refine_robot_adjacent_primitives(points,report,SimpleNamespace(spheres=[far]),
            inflation_m=.007,additional_collision_spheres=[payload])
        self.assertEqual(len(result['primitives']),2)
        self.assertEqual(sum(p['point_count'] for p in result['primitives']),2)
        self.assertTrue(all(p['inflation_m']==.007 for p in result['primitives']))
        self.assertEqual(result['robot_adjacent_refinement']['records'][0]['decision'],'SPLIT_NO_POINT_DELETION')

    def test_real_observed_collision_not_removed(self):
        points=np.array([[0.,0,0],[.1,0,0]])
        p={'primitive_id':'real','observed_bounds_m':[[0,0,0],[.1,0,0]],'inflation_m':.007,
           'dims_m':[.1,.004,.004],'center_m':[.05,0,0],'point_count':2}
        sphere=SimpleNamespace(center_body_m=(0,0,0),radius_m=.02)
        result=refine_robot_adjacent_primitives(points,{'primitives':[p],'old_single_aabb_occupied_volume_m3':1.},
            SimpleNamespace(spheres=[]),additional_collision_spheres=[sphere])
        self.assertEqual(result['primitives'],[p])
        self.assertEqual(result['robot_adjacent_refinement']['records'][0]['decision'],'RETAIN_GENUINE_POINT_COLLISION')
