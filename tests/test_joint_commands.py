import unittest

from ares_r.joint_commands import parse_joint_values, stepped_target, target_gate
from ares_r.motion import MotionLimits


class JointCommandsTest(unittest.TestCase):
    def setUp(self):
        self.limits = MotionLimits(tuple("j%d" % i for i in range(1, 7)),
            (-3.0,) * 6, (3.0,) * 6, (1.0,) * 6, (2.0,) * 6, 0.1, 0.03, True)

    def test_parse_degrees(self):
        values = parse_joint_values(["0", "90", "0", "0", "0", "-180"], "deg")
        self.assertAlmostEqual(values[1], 1.5707963267948966)
        self.assertAlmostEqual(values[5], -3.141592653589793)

    def test_step_changes_only_selected_joint(self):
        values = stepped_target([0.0] * 6, "J3", "10", "deg")
        self.assertEqual(values[:2], [0.0, 0.0])
        self.assertAlmostEqual(values[2], 0.17453292519943295)

    def test_uncommissioned_limits_block_target(self):
        limits = MotionLimits(self.limits.joint_names, self.limits.lower_rad,
            self.limits.upper_rad, self.limits.max_velocity_rad_s,
            self.limits.max_acceleration_rad_s2, self.limits.soft_limit_margin_rad,
            self.limits.max_start_error_rad, False)
        self.assertIn("site joint limits are not commissioned", target_gate([0.0] * 6, limits))

    def test_rejects_wrong_joint_count(self):
        with self.assertRaisesRegex(ValueError, "six"):
            parse_joint_values(["0"] * 5, "rad")


if __name__ == "__main__":
    unittest.main()
