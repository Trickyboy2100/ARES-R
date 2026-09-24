import unittest

from ares_r.manipulation.contact_motion import (TargetContactPolicy,
    plan_constrained_contact, validate_contact_approach)


def box(center, dims=(.01, .01, .01)):
    return {"center_body_m": list(center), "dims_m": list(dims)}


class TargetContactPolicyTests(unittest.TestCase):
    def policy(self):
        return TargetContactPolicy("contact-v1", "tray", (1, 0, 0), .04, .012, .002)

    def samples(self):
        rows=[]
        for x in (0, .01, .02, .03, .04):
            rows.append({"tcp_position_body_m": [x, 0, 0], "components": {
                "arm_links": [box((x-.1, 0, 0))],
                "tool": [box((x-.01, 0, 0))], "gripper": [box((x, 0, 0))]}})
        return rows

    def test_terminal_gripper_target_contact_is_allowed(self):
        report=validate_contact_approach(self.samples(), box((.045,0,0),(.01,.03,.03)), {}, self.policy())
        self.assertTrue(report["valid"])
        self.assertTrue(report["contacts"])

    def test_early_tool_target_contact_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "before terminal"):
            validate_contact_approach(self.samples(), box((.025,0,0),(.01,.03,.03)), {}, self.policy())

    def test_arm_and_non_target_are_always_hard_collision(self):
        rows=self.samples(); rows[-1]["components"]["arm_links"]=[box((.04,0,0))]
        with self.assertRaisesRegex(RuntimeError, "arm link"):
            validate_contact_approach(rows, box((.04,0,0),(.02,.03,.03)), {}, self.policy())
        with self.assertRaisesRegex(RuntimeError, "non-target wall"):
            validate_contact_approach(self.samples(), box((.2,0,0)),
                                      {"wall":box((.02,0,0),(.01,.03,.03))}, self.policy())

    def test_contact_planner_uses_cartesian_interpolation_and_continuous_seed(self):
        seen=[]
        def ik(pose, seed):
            seen.append(seed); return [pose[0]]*6
        def geometry(_joints, pose):
            x=pose[0]
            return {"tcp_position_body_m": pose[:3], "components": {
                "arm_links":[box((x-.1,0,0))], "tool":[box((x-.01,0,0))],
                "gripper":[box((x,0,0))]}}
        result=plan_constrained_contact([0,0,0,0,0,0],[.04,0,0,0,0,0],
            policy=self.policy(),solve_ik=ik,geometry_at=geometry,
            target=box((.045,0,0),(.01,.03,.03)),obstacles={},dense_step_m=.01)
        self.assertEqual(result["motion_contract"],"TARGET_CONTACT_APPROACH_V1")
        self.assertIsNone(seen[0]); self.assertIsNotNone(seen[1])


if __name__ == "__main__": unittest.main()
