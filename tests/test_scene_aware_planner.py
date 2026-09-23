import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

from ares_r.motion.scene_aware_motion import MotionConstraints, MotionRequest, OrientationMode
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


if __name__ == "__main__":
    unittest.main()
