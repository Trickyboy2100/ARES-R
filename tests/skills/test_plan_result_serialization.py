import unittest

from ares_r.skills import (FailureCode, SkillPlan, SkillResult, SkillStatus,
                           canonical_json, digest)


SHA = "a" * 64


class PlanResultTests(unittest.TestCase):
    def test_motion_requires_snapshot(self):
        with self.assertRaises(ValueError):
            SkillPlan("P", "I", "x.y", "1", 1, 2, "W", SHA, True)
        plan = SkillPlan("P", "I", "x.y", "1", 1, 2, "W", SHA, True,
                         scene_snapshot_id="S", planning_context_digest=SHA)
        self.assertEqual(plan.scene_snapshot_id, "S")

    def test_semantic_plan_has_no_fake_snapshot(self):
        plan = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False)
        self.assertIsNone(plan.scene_snapshot_id)
        with self.assertRaises(ValueError):
            SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False,
                      scene_snapshot_id="fake")

    def test_expected_failure_is_structured(self):
        result = SkillResult("I", None, SkillStatus.REJECTED, "not ready", None, 2,
                             FailureCode.PRECONDITION_FALSE)
        self.assertEqual(result.failure_code, FailureCode.PRECONDITION_FALSE)
        with self.assertRaises(ValueError):
            SkillResult("I", None, SkillStatus.FAILED, "bad", 1, 2)

    def test_digest_independent_of_mapping_order(self):
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))
        self.assertIn('"status":"REJECTED"', canonical_json(
            SkillResult("I", None, SkillStatus.REJECTED, "x", None, 2,
                        FailureCode.INVALID_INPUT)))

    def test_plan_and_result_digest_are_stable(self):
        one = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False,
                        steps=(("b", 2), ("a", 1)))
        two = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False,
                        steps=(("a", 1), ("b", 2)))
        self.assertEqual(digest(one), digest(two))
        r1 = SkillResult("I", "P", SkillStatus.SUCCEEDED, "ok", 1, 2,
                         metadata=(("b", 2), ("a", 1)))
        r2 = SkillResult("I", "P", SkillStatus.SUCCEEDED, "ok", 1, 2,
                         metadata=(("a", 1), ("b", 2)))
        self.assertEqual(digest(r1), digest(r2))
