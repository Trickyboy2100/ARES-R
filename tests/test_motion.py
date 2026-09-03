import json
import tempfile
import unittest
from pathlib import Path

from ares_r.motion import MotionLimits, load_trajectory, validate_trajectory


class MotionValidationTest(unittest.TestCase):
    def setUp(self):
        self.limits = MotionLimits(
            ("j1", "j2"), (-1.0, -1.0), (1.0, 1.0),
            (1.0, 1.0), (10.0, 10.0), 0.1, 0.05, True,
        )

    def write_trajectory(self, **changes):
        data = {
            "schema_version": 1,
            "planner": "test",
            "arm": "left",
            "joint_names": ["j1", "j2"],
            "sample_period_s": 0.08,
            "points": [[0.0, 0.0], [0.05, 0.0], [0.10, 0.0]],
            "collision_checked": True,
            "robot_model_revision": "r1",
            "world_revision": "w1",
            "tool_revision": "t1",
            "attached_object_revision": "none",
        }
        data.update(changes)
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "trajectory.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return directory, load_trajectory(path)

    def test_valid_trajectory(self):
        directory, trajectory = self.write_trajectory()
        self.addCleanup(directory.cleanup)
        self.assertEqual(validate_trajectory(trajectory, self.limits, [0.0, 0.0]), [])

    def test_blocks_unchecked_collision_and_limit(self):
        directory, trajectory = self.write_trajectory(
            collision_checked=False, points=[[0.0, 0.0], [0.95, 0.0]])
        self.addCleanup(directory.cleanup)
        codes = {issue.code for issue in validate_trajectory(trajectory, self.limits)}
        self.assertIn("COLLISION", codes)
        self.assertIn("SOFT_LIMIT", codes)
        self.assertIn("VELOCITY", codes)

    def test_blocks_unconfirmed_site_limits(self):
        directory, trajectory = self.write_trajectory()
        self.addCleanup(directory.cleanup)
        unconfirmed = MotionLimits(
            self.limits.joint_names, self.limits.lower_rad, self.limits.upper_rad,
            self.limits.max_velocity_rad_s, self.limits.max_acceleration_rad_s2,
            self.limits.soft_limit_margin_rad, self.limits.max_start_error_rad, False)
        codes = {issue.code for issue in validate_trajectory(trajectory, unconfirmed)}
        self.assertIn("UNCONFIRMED_LIMITS", codes)

    def test_blocks_start_mismatch(self):
        directory, trajectory = self.write_trajectory()
        self.addCleanup(directory.cleanup)
        codes = {issue.code for issue in validate_trajectory(trajectory, self.limits, [0.2, 0.0])}
        self.assertIn("START_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
