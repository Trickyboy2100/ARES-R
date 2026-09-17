import time
import unittest

import numpy as np

from ares_r.world import (
    CalibrationSet, ObservationEpoch, PointCloudRef, PoseSE3, RobotState,
    SceneObject, SceneObjectRole, WorldModel, compile_snapshot,
    transform_body_aabb,
)


class SceneCompilerTest(unittest.TestCase):
    def test_rotated_body_aabb_is_conservative_in_arm_frame(self):
        angle = np.pi / 4
        transform = np.eye(4)
        transform[:3, :3] = [[np.cos(angle), -np.sin(angle), 0],
                             [np.sin(angle), np.cos(angle), 0], [0, 0, 1]]
        center, dims = transform_body_aabb([0, 0, 0], [2, 1, 1], transform)
        np.testing.assert_allclose(center, [0, 0, 0], atol=1e-9)
        self.assertGreater(dims[0], 2.1)
        self.assertGreater(dims[1], 2.1)

    def test_snapshot_identity_and_calibration_reach_compiled_scene(self):
        runtime = "demo-runtime"
        now_wall, now_mono = time.time_ns(), time.monotonic_ns()
        world = WorldModel(runtime_id=runtime, snapshot_ttl_s=30, environment_ttl_s=30)
        state = RobotState(now_wall, now_mono, runtime, right_joints_rad=(0,)*6,
                           source_revisions=(("scope", "DEMO_OFFLINE_ONLY"),))
        world.update_robot_state(state)
        obs = world.begin_observation("OBS_DEMO", now_wall, now_mono)
        cloud = PointCloudRef("cloud", "a"*64, "body_demo_candidate")
        world.register_pointcloud(obs, cloud)
        item = SceneObject("box", SceneObjectRole.OBSTACLE, "cuboid",
                           PoseSE3("body", (1, 0, 1), (1, 0, 0, 0)),
                           (.2, .3, .4), .02, obs)
        world.register_obstacles(obs, (item,), cloud.pointcloud_id, cloud.sha256)
        world.register_calibration(obs, CalibrationSet((("T_body_camera", "DEMO_ONLY:123"),)))
        world.commit_observation(obs)
        snapshot = world.freeze_snapshot("robot-rev", "tool-rev")
        compiled = compile_snapshot(snapshot, "right", np.eye(4))
        self.assertEqual(compiled["scene_snapshot_id"], snapshot.snapshot_id)
        self.assertEqual(compiled["calibration_revision"]["T_body_camera"], "DEMO_ONLY:123")
        self.assertFalse(compiled["execution_allowed"])
        self.assertIn("box", compiled["cuboids"])


if __name__ == "__main__":
    unittest.main()
