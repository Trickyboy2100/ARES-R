from pathlib import Path
import json
import os
import time
import unittest

import numpy as np

from ares_r.perception.chassis_policy import chassis_enabled, is_chassis_geometry
from ares_r.perception.robot_collision import build_geometry_snapshot
from ares_r.motion.joint_mirror import JointMirrorModel
from ares_r.world import (WorldModel, RobotState, PointCloudRef, CalibrationSet,
                          SceneObject, SceneObjectRole, PoseSE3, compile_snapshot)


ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT/'config/robot_collision_model.json').read_text())
ASSETS = Path(os.environ.get('ARES_R_TEST_ASSET_ROOT', MODEL['asset_root']))


class ChassisPolicyTests(unittest.TestCase):
    def test_explicit_ids_do_not_remove_environment_or_arm_bases(self):
        self.assertFalse(chassis_enabled())
        self.assertTrue(is_chassis_geometry({'id': 'body_chassis_lower'}))
        self.assertFalse(is_chassis_geometry({'id': 'observed_chassis_shaped_object'}))
        self.assertFalse(is_chassis_geometry({'geometry_id': 'left/base_link', 'owner': 'left_arm'}))

    def test_old_snapshot_chassis_is_excluded_but_real_obstacle_remains(self):
        wall, mono = time.time_ns(), time.monotonic_ns()
        world = WorldModel(runtime_id='test', snapshot_ttl_s=30, environment_ttl_s=30)
        world.update_robot_state(RobotState(wall, mono, 'test', right_joints_rad=(0,)*6))
        observation = world.begin_observation('OBS', wall, mono)
        cloud = PointCloudRef('cloud', 'a'*64, 'body')
        world.register_pointcloud(observation, cloud)
        objects = [SceneObject(name, SceneObjectRole.OBSTACLE, 'cuboid',
            PoseSE3('body', (.6, -.3, 1.), (1, 0, 0, 0)), (.2, .2, .2), 0, observation)
            for name in ('body_chassis_lower', 'observed_chassis_shaped_object')]
        world.register_obstacles(observation, objects, cloud.pointcloud_id, cloud.sha256)
        world.register_calibration(observation, CalibrationSet((('T_body_camera', 'test'),)))
        world.commit_observation(observation)
        compiled = compile_snapshot(world.freeze_snapshot('robot', 'tool'), 'right', np.eye(4))
        self.assertNotIn('body_chassis_lower', compiled['cuboids'])
        self.assertIn('observed_chassis_shaped_object', compiled['cuboids'])

    @unittest.skipUnless(ASSETS.exists(), 'pinned site assets required')
    def test_exporter_drops_legacy_chassis_and_keeps_both_arms(self):
        model = JointMirrorModel(ROOT, asset_root=ASSETS)
        model.model['asset_root'] = str(ASSETS)
        model.model['fixed_body_boxes'].extend(model.model.get('disabled_fixed_body_boxes', []))
        geometry = build_geometry_snapshot(model.model, model.world, model.audits)
        self.assertFalse(any(box.owner == 'chassis' for box in geometry.boxes))
        self.assertTrue(any(box.owner == 'left_arm' for box in geometry.boxes))
        self.assertTrue(any(box.owner == 'right_arm' for box in geometry.boxes))
