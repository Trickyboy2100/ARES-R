import unittest
import time
import numpy as np
from ares_r.manipulation.observed_scene_obb import ObservedSceneOBB
from ares_r.world.scene_compiler import _rotation_wxyz,transform_body_cuboid
from ares_r.world import CalibrationSet,PointCloudRef,PoseSE3,RobotState,SceneObject,SceneObjectRole,WorldModel,compile_snapshot


class ObservedOBBTests(unittest.TestCase):
    def test_source_enclosure_and_padding(self):
        r=np.array([[.8,-.6,0],[.6,.8,0],[0,0,1.]])
        points=np.random.default_rng(42).uniform([-.1,-.01,-.01],[.1,.01,.01],(5000,3))@r.T
        low,high=points.min(0),points.max(0)
        p=dict(semantic='PROTRUDING_OBJECT',observed_bounds_m=[low,high],dims_m=(high-low).tolist())
        result=ObservedSceneOBB(points).refine(p,.007)
        self.assertIsNotNone(result)
        local=np.abs((points-result['center_m'])@_rotation_wxyz(result['quaternion_wxyz']))
        self.assertTrue(np.all(local<=np.array(result['dims_m'])/2+1e-8))
        self.assertEqual(result['source_points'],5000)
        self.assertEqual(result['padding_m'],.007)
        self.assertIsNone(ObservedSceneOBB(points).refine(dict(p,semantic='SUPPORT_SURFACE'),.007))

    def test_compiler_honors_object_not_only_arm_rotation(self):
        now,mono=time.time_ns(),time.monotonic_ns();wm=WorldModel(runtime_id='obb',snapshot_ttl_s=30,environment_ttl_s=30)
        wm.update_robot_state(RobotState(now,mono,'obb',right_joints_rad=(0,)*6));obs=wm.begin_observation('obb-obs',now,mono)
        cloud=PointCloudRef('cloud','a'*64,'body');wm.register_pointcloud(obs,cloud)
        q=(np.cos(np.pi/8),0,0,np.sin(np.pi/8))
        obj=SceneObject('oriented',SceneObjectRole.OBSTACLE,'cuboid',PoseSE3('body',(1,0,1),q),(.2,.02,.02),.007,obs)
        wm.register_obstacles(obs,[obj],cloud.pointcloud_id,cloud.sha256);wm.register_calibration(obs,CalibrationSet((('cal','rev'),)));wm.commit_observation(obs)
        snapshot=wm.freeze_snapshot('robot','tool');compiled=compile_snapshot(snapshot,'right',np.eye(4),'P3_PRODUCTION_PLANNING_ONLY')['cuboids']['oriented']
        np.testing.assert_allclose(_rotation_wxyz(compiled['pose'][3:]),_rotation_wxyz(q),atol=1e-9)
        np.testing.assert_allclose(compiled['dims'],[.214,.034,.034])
        conservative=compile_snapshot(snapshot,'right',np.eye(4))['cuboids']['oriented']
        self.assertGreater(conservative['dims'][1],.17)
        self.assertEqual(conservative['pose'][3:],[1,0,0,0])
