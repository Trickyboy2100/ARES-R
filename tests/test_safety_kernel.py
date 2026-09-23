import unittest
from types import SimpleNamespace

from ares_r.motion.safety_kernel import (DualArmSafetyKernel, SafetyViolation,
                                         central_plane_in_arm_base, require_permit)


def geometry(count=2, left_y=.30, right_y=-.30):
    sphere = lambda y: {"center_body_m": [0.3, y, 1.2], "radius_m": .03}
    return [{"links": [sphere(left_y)], "tool": [sphere(left_y)],
             "right_arm": [sphere(right_y)]} for _ in range(count)]


class SafetyKernelTest(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(max_velocity_rad_s=.1,
                                       max_acceleration_rad_s2=2.0,
                                       state="COMMISSIONED")
        self.kernel = DualArmSafetyKernel(True, {"slow": self.profile})
        self.kw = dict(arm="left", points=[[0]*6, [.001]*6], sample_period_s=.1,
                       geometry_samples=geometry(), speed_profile="slow", live_start=[0]*6,
                       tool_revision="t", planned_tool_revision="t", scene_snapshot_id="scene-1",
                       collision_checked=True, base_stationary=True,
                       inactive_arm_state_known=True)

    def test_full_path_mints_matching_permit(self):
        permit = self.kernel.authorize(**self.kw)
        require_permit(permit, "left", self.kw["points"], .1)

    def test_kill_switch_blocks_everything(self):
        with self.assertRaisesRegex(SafetyViolation, "disabled"):
            DualArmSafetyKernel(False, {"slow": self.profile}).authorize(**self.kw)

    def test_endpoint_only_or_missing_inactive_arm_is_rejected(self):
        for samples in (geometry(1), [{"links": geometry()[0]["links"],
                                      "tool": geometry()[0]["tool"]}] * 2):
            with self.assertRaises(SafetyViolation):
                self.kernel.authorize(**dict(self.kw, geometry_samples=samples))

    def test_link_or_tool_touching_slab_is_rejected(self):
        with self.assertRaisesRegex(SafetyViolation, "central 14 cm"):
            self.kernel.authorize(**dict(self.kw, geometry_samples=geometry(left_y=.09)))

    def test_tool_scene_start_and_speed_gates(self):
        variants = [dict(planned_tool_revision="other"), dict(collision_checked=False),
                    dict(live_start=[1]*6), dict(points=[[0]*6, [.2]*6])]
        for values in variants:
            with self.assertRaises(SafetyViolation):
                self.kernel.authorize(**dict(self.kw, **values))

    def test_uncommissioned_profile_is_rejected(self):
        profile = SimpleNamespace(max_velocity_rad_s=.1, max_acceleration_rad_s2=2,
                                  state="UNCOMMISSIONED")
        with self.assertRaisesRegex(SafetyViolation, "not commissioned"):
            DualArmSafetyKernel(True, {"slow": profile}).authorize(**self.kw)

    def test_body_center_planes_transform_to_each_arm_base(self):
        import math
        left = central_plane_in_arm_base("left", [0, .2, 1.2], 3 * math.pi / 4)
        right = central_plane_in_arm_base("right", [0, -.2, 1.2], math.pi / 4)
        self.assertAlmostEqual(left["normal_base"][0], math.sqrt(.5))
        self.assertAlmostEqual(left["normal_base"][1], -math.sqrt(.5))
        self.assertAlmostEqual(right["normal_base"][0], -math.sqrt(.5))
        self.assertAlmostEqual(right["normal_base"][1], -math.sqrt(.5))
        self.assertAlmostEqual(left["offset_m"], -.13)
        self.assertAlmostEqual(right["offset_m"], -.13)

    def test_scene_aware_gate_is_hard_collision_only(self):
        candidate = {
            "motion_contract": "SCENE_AWARE_FREE_SPACE_V1",
            "hard_validity": {
                "hard_valid": True,
                "hard_min_gap_m": .008,
                "validator_role": "HARD_COLLISION_AND_BINDING_ONLY",
            },
        }
        self.assertTrue(DualArmSafetyKernel.scene_aware_collision_gate(candidate))
        candidate["hard_validity"]["hard_min_gap_m"] = 0.0
        self.assertFalse(DualArmSafetyKernel.scene_aware_collision_gate(candidate))


if __name__ == "__main__":
    unittest.main()
