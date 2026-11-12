import unittest

from ares_r.motion.central_exclusion import CentralExclusionPolicy
from ares_r.motion.safety_kernel import DualArmSafetyKernel, SafetyViolation


def sample(y):
    sphere = {"center_body_m": [0.3, y, 1.0], "radius_m": .01}
    return {"links": [sphere], "tool": [sphere], "left_arm": [sphere]}


class CentralExclusionPolicyTest(unittest.TestCase):
    def test_historical_band_is_seven_centimetres_per_side(self):
        policy = CentralExclusionPolicy(True, .07, "test")
        self.assertFalse(policy.gate("right", -.07))
        self.assertTrue(policy.gate("right", -.071))
        self.assertFalse(policy.gate("left", .07))
        self.assertTrue(policy.gate("left", .071))

    def test_disabled_policy_does_not_reject_center_crossing(self):
        policy = CentralExclusionPolicy(False, .07, "p39b")
        self.assertTrue(policy.gate("right", 0.02))
        self.assertEqual(policy.margin("right", 0.02), float("inf"))

    def test_safety_geometry_switch_controls_only_virtual_slab(self):
        with self.assertRaises(SafetyViolation):
            DualArmSafetyKernel._check_geometry("right", [sample(-.02)], 1, False, True)
        DualArmSafetyKernel._check_geometry("right", [sample(-.02)], 1, False, False)


if __name__ == "__main__":
    unittest.main()
