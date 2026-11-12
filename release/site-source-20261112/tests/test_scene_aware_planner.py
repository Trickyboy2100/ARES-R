import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

from ares_r.motion.scene_aware_motion import (MotionConstraints, MotionGoal, MotionRequest,
                                              OrientationMode)
from ares_r.motion import scene_aware_planner


class SceneAwarePlannerContractTests(unittest.TestCase):
    def test_body_forward_constraint_is_generic_request_data(self):
        request = MotionRequest("right", [0] * 6,
                                constraints=MotionConstraints(
                                    orientation=OrientationMode.BODY_FORWARD_HORIZONTAL))
        report = {"T_body_model": np.eye(4).tolist()}
        audit = {"diagnostics": {"joint_position_rad": [0] * 6,
                                  "tool_data": {"pose_mm_rad": [0, 0, 184, 0, 0, 0]}}}
        lock = scene_aware_planner._orientation_lock(request, report, audit, {})
        self.assertEqual(lock["policy"], "BODY_FORWARD_HORIZONTAL_V1")
        self.assertEqual(lock["target_R_body_tcp"],
                         scene_aware_planner.HORIZONTAL_FORWARD_R_BODY.tolist())

    def test_free_orientation_has_no_worker_lock(self):
        request = MotionRequest("left", [0] * 6)
        self.assertIsNone(scene_aware_planner._orientation_lock(request, {}, {}, {}))

    def test_runtime_level_goal_uses_level_yaw_mode(self):
        request = MotionRequest("right", goal=MotionGoal([.7, -.5, 1.0]))
        self.assertEqual(request.goal.orientation, OrientationMode.LEVEL_YAW_FREE)
        self.assertEqual(scene_aware_planner.LEVEL_YAW_CRITERIA_RPY, (1.0, 0.0, 1.0))

    def test_hard_level_manifold_fills_goal_and_requires_a_lock(self):
        goal = MotionGoal([.7, -.5, 1.0], orientation=OrientationMode.LEVEL_YAW_TARGET,
                          yaw_target_rad=0.0)
        request = MotionRequest("right", goal=goal,
                                hard_level_manifold={'ik_samples': 25})
        manifold = scene_aware_planner._hard_level_manifold(
            request, {'policy': 'LEVEL_YAW_TARGET_V1'})
        self.assertEqual(manifold['goal_position_m'], [.7, -.5, 1.0])
        self.assertEqual(manifold['goal_yaw_rad'], 0.0)
        self.assertEqual(manifold['ik_samples'], 25)
        with self.assertRaisesRegex(ValueError, 'orientation lock'):
            scene_aware_planner._hard_level_manifold(request, None)
        # 没有可用目标位置时 fail-closed
        bare = MotionRequest("right", [0.1] * 6,
                             hard_level_manifold={'ik_samples': 25})
        with self.assertRaisesRegex(ValueError, 'goal_position_m'):
            scene_aware_planner._hard_level_manifold(bare, {'policy': 'LEVEL_YAW_FREE_V1'})


if __name__ == "__main__":
    unittest.main()
