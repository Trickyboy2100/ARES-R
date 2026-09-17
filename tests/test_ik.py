import unittest

import numpy

from ares_r.motion.ik import best_candidate, build_targets
from ares_r.motion.ik_worker import pose_vector_to_matrix, tool_goal_matrix


class PoseVectorTest(unittest.TestCase):
    def test_identity_pose(self):
        matrix = pose_vector_to_matrix([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertTrue(numpy.allclose(matrix, numpy.eye(4)))

    def test_translation_lands_in_the_last_column(self):
        matrix = pose_vector_to_matrix([1.0, -2.0, 3.0, 0.0, 0.0, 0.0])
        self.assertTrue(numpy.allclose(matrix[:3, 3], [1.0, -2.0, 3.0]))

    def test_six_values_are_required(self):
        with self.assertRaisesRegex(ValueError, "six values"):
            pose_vector_to_matrix([0.0, 0.0, 0.0])

    def test_non_finite_values_are_refused(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            pose_vector_to_matrix([0.0, 0.0, float("nan"), 0.0, 0.0, 0.0])


class ToolGoalTest(unittest.TestCase):
    def test_identity_correction_without_a_tool_offset_is_the_target(self):
        target = pose_vector_to_matrix([0.3, -0.2, -0.1, 0.0, 0.0, 0.0])
        goal = tool_goal_matrix(target, numpy.eye(4), [0.0, 0.0, 0.0])
        self.assertTrue(numpy.allclose(goal, target))

    def test_tool_offset_is_subtracted_in_the_target_frame(self):
        """The solver aims link6, so a 160 mm tool means the flange stops short."""
        target = pose_vector_to_matrix([0.3, -0.2, -0.1, 0.0, 0.0, 0.0])
        goal = tool_goal_matrix(target, numpy.eye(4), [0.0, 0.0, 0.16])
        self.assertTrue(numpy.allclose(goal[:3, 3], [0.3, -0.2, -0.26], atol=1e-12))
        self.assertTrue(numpy.allclose(goal[:3, :3], target[:3, :3]))

    def test_tool_offset_follows_the_target_orientation(self):
        """A 90 degree yaw turns the standoff direction with the gripper."""
        target = pose_vector_to_matrix([0.5, 0.0, 0.0, 0.0, 0.0, 1.5707963267948966])
        goal = tool_goal_matrix(target, numpy.eye(4), [0.1, 0.0, 0.0])
        self.assertTrue(numpy.allclose(goal[:3, 3], [0.5, -0.1, 0.0], atol=1e-12))

    def test_correction_is_inverted(self):
        """A correction maps model to controller, so the goal must undo it."""
        correction = numpy.eye(4)
        correction[2, 3] = 1.2
        target = pose_vector_to_matrix([0.0, 0.0, 1.2, 0.0, 0.0, 0.0])
        goal = tool_goal_matrix(target, correction, [0.0, 0.0, 0.0])
        self.assertTrue(numpy.allclose(goal[:3, 3], [0.0, 0.0, 0.0], atol=1e-12))

    def test_correction_and_tool_offset_compose(self):
        correction = numpy.eye(4)
        correction[2, 3] = 1.2
        target = pose_vector_to_matrix([0.0, 0.0, 1.2, 0.0, 0.0, 0.0])
        goal = tool_goal_matrix(target, correction, [0.0, 0.0, 0.16])
        self.assertTrue(numpy.allclose(goal[:3, 3], [0.0, 0.0, -0.16], atol=1e-12))


class TargetTest(unittest.TestCase):
    class Plan:
        def __init__(self):
            from ares_r.models import Pose
            self.grasp = Pose("frame", 0.4, -0.3, -0.1, 1.0, 0.0, 0.8)
            self.pregrasp = Pose("frame", 0.36, -0.26, -0.1, 1.0, 0.0, 0.8)

    def test_both_stops_are_requested_in_order(self):
        targets = build_targets(self.Plan())
        self.assertEqual([item["label"] for item in targets], ["pregrasp", "grasp"])
        self.assertEqual(targets[0]["pose_m_rad"], [0.36, -0.26, -0.1, 1.0, 0.0, 0.8])

    def test_empty_target_list_is_refused(self):
        from ares_r.motion.ik import solve_ik
        with self.assertRaisesRegex(ValueError, "IK target"):
            solve_ik({}, "right", [], {}, "current")

    def test_unknown_profile_is_refused_before_touching_the_gpu(self):
        from ares_r.motion.ik import solve_ik
        with self.assertRaisesRegex(ValueError, "unknown planning profile"):
            solve_ik({}, "right", [{"label": "grasp", "pose_m_rad": [0.0] * 6}], {}, "nonexistent")


class BestCandidateTest(unittest.TestCase):
    def test_first_accepted_candidate_wins(self):
        payload = {"candidates": [dict(target="a", accepted=False, rejections=["stale"]),
                                  dict(target="b", accepted=True),
                                  dict(target="c", accepted=True)]}
        self.assertEqual(best_candidate(payload)["target"], "b")

    def test_refusal_names_every_distinct_reason(self):
        payload = {"candidates": [dict(target="a", accepted=False, rejections=["low clearance"]),
                                  dict(target="b", accepted=False, rejections=["low clearance",
                                                                               "central slab"])]}
        with self.assertRaises(RuntimeError) as context:
            best_candidate(payload)
        message = str(context.exception)
        self.assertIn("low clearance", message)
        self.assertIn("central slab", message)

    def test_empty_result_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "no candidate was returned"):
            best_candidate({"candidates": []})

    def test_target_filter_restricts_the_choice(self):
        payload = {"candidates": [dict(target="grasp", accepted=True),
                                  dict(target="pregrasp", accepted=True),
                                  dict(target="pregrasp", accepted=True)]}
        self.assertEqual(best_candidate(payload)["target"], "grasp")
        self.assertEqual(best_candidate(payload, target="pregrasp")["target"], "pregrasp")

    def test_target_filter_names_the_missing_target(self):
        payload = {"candidates": [dict(target="grasp", accepted=True)]}
        with self.assertRaisesRegex(RuntimeError, "no accepted candidate for target 'pregrasp'"):
            best_candidate(payload, target="pregrasp")


class SeparationGateTest(unittest.TestCase):
    """The other arm's clearance is an operator statement, never an assumption."""

    def test_undeclared_separation_is_refused(self):
        from ares_r.motion.grasp_plan import _require_separation, prepare
        with self.assertRaisesRegex(RuntimeError, "physical separation"):
            _require_separation(False)
        with self.assertRaisesRegex(RuntimeError, "physical separation"):
            prepare({}, "right", "case", None, "current", other_arm_separated=False)

    def test_declared_separation_is_accepted(self):
        from ares_r.motion.grasp_plan import _require_separation
        self.assertIsNone(_require_separation(True))


if __name__ == "__main__":
    unittest.main()
