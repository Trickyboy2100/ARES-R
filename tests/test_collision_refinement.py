import unittest
import numpy as np
from ares_r.manipulation.attached_world import seal
from ares_r.manipulation.collision_refinement import payload_spheres_link6, observed_obb


class CollisionRefinementTests(unittest.TestCase):
    def attachment(self):
        from ares_r.manipulation.attached_collision import build_attached_collision
        from ares_r.world import AttachedObject, PoseSE3, SceneObject, SceneObjectRole
        shape=SceneObject('box',SceneObjectRole.TARGET,'cuboid',PoseSE3('body',(0,0,0),(1,0,0,0)),(.2,.12,.06),0.,'OBS')
        obj=AttachedObject('box','right',PoseSE3('tcp',(0,0,0),(.9238795325112867,0,0,.3826834323650898)),shape,'GRASP')
        return build_attached_collision(obj,np.eye(4).tolist(),.004)

    def test_cells_cover_entire_padded_object_without_link6_aabb_conversion(self):
        a=self.attachment();s=payload_spheres_link6(a);T=np.array(a['T_link6_object'])
        random=np.random.default_rng(4)
        half=np.array(a['object_dimensions_m'])/2+a['inflation_m']
        points=random.uniform(-1,1,(1500,3))*half
        points=np.vstack([points,[[x,y,z] for x in (-half[0],half[0]) for y in (-half[1],half[1]) for z in (-half[2],half[2])]])
        points=points@T[:3,:3].T+T[:3,3]
        centers=np.array([r['center'] for r in s]);radii=np.array([r['radius'] for r in s])
        self.assertTrue(np.all(np.min(np.linalg.norm(points[:,None]-centers[None],axis=2)-radii,axis=1)<1e-9))

    def test_invalid_transform_and_cell_rejected(self):
        a=self.attachment();a['T_link6_object'][0][0]*=2;a=seal(a)
        with self.assertRaisesRegex(ValueError,'rigid'):payload_spheres_link6(a)
        with self.assertRaises(ValueError):payload_spheres_link6(self.attachment(),0.)

    def test_obb_encloses_all_points_and_original_padding(self):
        points=np.random.default_rng(2).uniform([-1,-.1,-.02],[1,.1,.02],(100,3))
        angle=.6;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
        points=points@R.T;b=observed_obb(points,.007)
        local=np.abs((points-b['center_body_m'])@np.array(b['rotation_body']))+.007
        self.assertTrue(np.all(local<=np.array(b['half_extents_m'])+1e-9))
        self.assertTrue(b['all_source_points_enclosed'])
        self.assertEqual(b,observed_obb(points,.007))

    def test_malformed_cloud_not_silently_deleted(self):
        for points in ([],[[1,2,3]],[[0,0,0],[1,1,1],[np.nan,0,0]]):
            with self.assertRaises(ValueError):observed_obb(points,.007)

    def test_hull_frames_preserve_padding_and_dont_use_robot_or_goal(self):
        points=np.array([[0,0,0],[.03,0,0],[.03,.01,0],[0,.01,0],[.002,.002,.001]])
        box=observed_obb(points,.007)
        R=np.array(box['rotation_body'])
        self.assertTrue(np.allclose(R.T@R,np.eye(3),atol=1e-8))
        self.assertAlmostEqual(np.linalg.det(R),1.)
        self.assertTrue(np.all(np.abs((points-box['center_body_m'])@R)+.007<=np.array(box['half_extents_m'])+1e-9))
        self.assertLessEqual(np.prod(box['half_extents_m']),np.prod(np.maximum(np.ptp(points,axis=0)/2,.002)+.007)+1e-12)
