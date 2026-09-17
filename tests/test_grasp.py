import math
import unittest

from ares_r.models import DetectionResult, Pose
from ares_r.motion.grasp import (GraspPlan, approach_direction, build_grasp_plan,
                                 rotation_matrix, tilt_from_horizontal_deg)

FRAME = "right_arm_base"

#: Captured on site 2026-09-16 from space 2 (right arm), three runs agreeing to
#: within a millimetre. This is the pose the module has to keep working for.
RIGHT_ARM_SITE = dict(x=0.48568, y=-0.31749, z=-0.16743,
                      rx_deg=94.56296, ry_deg=1.45046, rz_deg=46.93216)
#: Same tray, reported by space 1 (left arm). 0.653 m from that base.
LEFT_ARM_SITE = dict(x=-0.59707, y=-0.19984, z=-0.17237,
                     rx_deg=-84.85887, ry_deg=178.15266, rz_deg=137.14281)


def config(**overrides):
    grasp = dict(arm="right", insertion_mode="horizontal", approach_axis="+z",
                 rpy_order="ZYX", approach_m=0.06, lift_m=0.08, min_reach_m=0.15,
                 max_reach_m=0.62, max_approach_tilt_deg=15.0)
    grasp.update(overrides)
    return {"epic": {"pose_frame": FRAME, "pose_frame_verified": True},
            "motion": {"lift_m": 0.08}, "grasp": grasp}


def detection(success=True, frame=FRAME, **pose):
    point = Pose(frame, pose["x"], pose["y"], pose["z"],
                 math.radians(pose["rx_deg"]), math.radians(pose["ry_deg"]),
                 math.radians(pose["rz_deg"]))
    return DetectionResult(success, "request-1", "pick", pose=point, candidates=[point],
                           raw_response="320,0,1,1,1,2,1,0,0,0,0,0",
                           meta={"pose_frame": frame, "space_id": 2, "object_id": 1,
                                 "grasp_index": 0, "total_grasp_count": 1})


def vertical_detection(x=0.30, y=0.0, z=-0.10, **overrides):
    """A pose whose tool Z axis points straight up: rx = ry = rz = 0."""
    values = dict(x=x, y=y, z=z, rx_deg=0.0, ry_deg=0.0, rz_deg=0.0)
    values.update(overrides)
    return detection(**values)


class RotationTest(unittest.TestCase):
    def test_zero_rotation_is_the_identity(self):
        self.assertEqual(rotation_matrix(0.0, 0.0, 0.0),
                         [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    def test_unknown_order_is_refused(self):
        with self.assertRaisesRegex(ValueError, "ZYX"):
            rotation_matrix(0.0, 0.0, 0.0, "XYZ")

    def test_approach_axis_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError, "approach axis"):
            approach_direction(rotation_matrix(0.0, 0.0, 0.0), "z")

    def test_negative_axis_flips_the_direction(self):
        rotation = rotation_matrix(math.radians(-90.0), 0.0, 0.0)
        self.assertAlmostEqual(approach_direction(rotation, "+z")[1], 1.0)
        self.assertAlmostEqual(approach_direction(rotation, "-z")[1], -1.0)

    def test_positive_axis_flips_the_direction_of_a_right_angle_roll(self):
        rotation = rotation_matrix(math.radians(90.0), 0.0, 0.0)
        self.assertAlmostEqual(approach_direction(rotation, "+z")[1], -1.0)

    def test_site_pose_approaches_horizontally(self):
        """The one physical fact the whole module leans on: a horizontal insertion."""
        rotation = rotation_matrix(math.radians(RIGHT_ARM_SITE["rx_deg"]),
                                   math.radians(RIGHT_ARM_SITE["ry_deg"]),
                                   math.radians(RIGHT_ARM_SITE["rz_deg"]))
        direction = approach_direction(rotation)
        self.assertAlmostEqual(direction[0], 0.7270, delta=0.002)
        self.assertAlmostEqual(direction[1], -0.6821, delta=0.002)
        self.assertLess(abs(direction[2]), 0.09)
        self.assertAlmostEqual(tilt_from_horizontal_deg(direction), -4.56, delta=0.1)


class GraspPlanTest(unittest.TestCase):
    def setUp(self):
        self.plan = build_grasp_plan(config(), detection(**RIGHT_ARM_SITE))

    def test_plan_is_a_grasp_plan(self):
        self.assertIsInstance(self.plan, GraspPlan)
        self.assertEqual(self.plan.arm, "right")
        self.assertEqual(self.plan.frame_id, FRAME)
        self.assertTrue(self.plan.frame_verified)

    def test_pregrasp_sits_back_along_the_measured_approach(self):
        self.assertAlmostEqual(self.plan.pregrasp.x, 0.44206, delta=1e-4)
        self.assertAlmostEqual(self.plan.pregrasp.y, -0.27657, delta=1e-4)
        self.assertAlmostEqual(self.plan.pregrasp.z, -0.16266, delta=1e-4)

    def test_pregrasp_keeps_the_grasp_orientation(self):
        self.assertEqual((self.plan.pregrasp.rx, self.plan.pregrasp.ry, self.plan.pregrasp.rz),
                         (self.plan.grasp.rx, self.plan.grasp.ry, self.plan.grasp.rz))

    def test_insertion_is_a_pure_standoff_length(self):
        gap = math.dist((self.plan.grasp.x, self.plan.grasp.y, self.plan.grasp.z),
                        (self.plan.pregrasp.x, self.plan.pregrasp.y, self.plan.pregrasp.z))
        self.assertAlmostEqual(gap, self.plan.insertion_distance_m, places=9)

    def test_distance_matches_the_camera_value(self):
        self.assertAlmostEqual(self.plan.distance_from_base_m, 0.6039, delta=0.001)

    def test_pregrasp_moves_closer_to_the_base(self):
        standoff = math.dist((0.0, 0.0, 0.0),
                             (self.plan.pregrasp.x, self.plan.pregrasp.y, self.plan.pregrasp.z))
        self.assertLess(standoff, self.plan.distance_from_base_m)

    def test_source_keeps_the_camera_identifiers(self):
        self.assertEqual(self.plan.source["space_id"], 2)
        self.assertEqual(self.plan.source["grasp_index"], 0)
        self.assertEqual(self.plan.source["candidate_count"], 1)
        self.assertIn("raw_response", self.plan.summary()["source"])

    def test_summary_is_json_serialisable(self):
        import json
        json.dumps(self.plan.summary())


class GraspPlanGateTest(unittest.TestCase):
    def test_unverified_frame_blocks_the_plan(self):
        broken = config()
        broken["epic"]["pose_frame_verified"] = False
        with self.assertRaisesRegex(RuntimeError, "displacement test"):
            build_grasp_plan(broken, detection(**RIGHT_ARM_SITE))

    def test_inspection_can_proceed_but_is_marked_unverified(self):
        pending = config()
        pending["epic"]["pose_frame_verified"] = False
        plan = build_grasp_plan(pending, detection(**RIGHT_ARM_SITE),
                                allow_unverified_frame=True)
        self.assertFalse(plan.frame_verified)

    def test_detection_frame_must_match_the_config(self):
        with self.assertRaisesRegex(RuntimeError, "was produced in frame"):
            build_grasp_plan(config(), detection(frame="stale_frame", **RIGHT_ARM_SITE))

    def test_horizontal_mode_refuses_a_vertical_approach(self):
        with self.assertRaisesRegex(RuntimeError, "off the horizontal plane"):
            build_grasp_plan(config(), vertical_detection())

    def test_vertical_mode_accepts_the_same_pose(self):
        plan = build_grasp_plan(config(insertion_mode="vertical"), vertical_detection())
        self.assertAlmostEqual(plan.tilt_deg, 90.0, places=6)

    def test_vertical_mode_refuses_the_site_horizontal_pose(self):
        with self.assertRaisesRegex(RuntimeError, "from vertical"):
            build_grasp_plan(config(insertion_mode="vertical"), detection(**RIGHT_ARM_SITE))

    def test_left_arm_pose_is_refused_as_out_of_reach(self):
        with self.assertRaisesRegex(RuntimeError, "outside the commissioned"):
            build_grasp_plan(config(), detection(**LEFT_ARM_SITE))

    def test_arm_must_match_the_commissioned_arm(self):
        with self.assertRaisesRegex(RuntimeError, "commissioned for"):
            build_grasp_plan(config(), detection(**RIGHT_ARM_SITE), arm="left")

    def test_unknown_rpy_order_is_refused(self):
        with self.assertRaisesRegex(ValueError, "ZYX"):
            build_grasp_plan(config(rpy_order="XYZ"), detection(**RIGHT_ARM_SITE))

    def test_reach_window_is_validated(self):
        with self.assertRaisesRegex(RuntimeError, "min_reach_m"):
            build_grasp_plan(config(min_reach_m=0.9), detection(**RIGHT_ARM_SITE))

    def test_approach_distance_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "approach_m"):
            build_grasp_plan(config(approach_m=0.0), detection(**RIGHT_ARM_SITE))

    def test_missing_grasp_section_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "no grasp section"):
            build_grasp_plan({"epic": {"pose_frame": FRAME, "pose_frame_verified": True}},
                             detection(**RIGHT_ARM_SITE))

    def test_failed_detection_has_no_grasp_point(self):
        with self.assertRaisesRegex(ValueError, "no grasp point"):
            build_grasp_plan(config(), detection(success=False, **RIGHT_ARM_SITE))


if __name__ == "__main__":
    unittest.main()
