import unittest

from ares_r.skills import (FailureCode, LockIntent, LockMode, ResolvedLock,
    SkillLifecycleState, SkillPlan, SkillPlanStep, SkillResult, SkillRuntimeEvent,
    SkillStatus, canonical_json, digest)


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
        a = SkillPlanStep("a", "cap.a", "A")
        b = SkillPlanStep("b", "cap.b", "B")
        one = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False,
                        steps=(a, b))
        two = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA, False,
                        steps=(SkillPlanStep("a", "cap.a", "A"),
                               SkillPlanStep("b", "cap.b", "B")))
        self.assertEqual(digest(one), digest(two))
        reversed_plan = SkillPlan("P", "I", "device.start", "1", 1, 2, "W", SHA,
                                  False, steps=(b, a))
        self.assertNotEqual(digest(one), digest(reversed_plan))
        r1 = SkillResult("I", "P", SkillStatus.SUCCEEDED, "ok", 1, 2,
                         metadata=(("b", 2), ("a", 1)))
        r2 = SkillResult("I", "P", SkillStatus.SUCCEEDED, "ok", 1, 2,
                         metadata=(("a", 1), ("b", 2)))
        self.assertEqual(digest(r1), digest(r2))

    def test_duplicate_steps_and_resolved_locks_rejected(self):
        step = SkillPlanStep("a", "cap", "op")
        with self.assertRaisesRegex(ValueError, "duplicate plan"):
            SkillPlan("P", "I", "x.y", "1", 1, 2, "W", SHA, False,
                      steps=(step, step))
        lock = ResolvedLock("arm:right", LockMode.EXCLUSIVE_MOTION, "arm.selected")
        with self.assertRaisesRegex(ValueError, "duplicate resolved"):
            SkillPlan("P", "I", "x.y", "1", 1, 2, "W", SHA, False,
                      resolved_locks=(lock, lock))
        with self.assertRaises(ValueError):
            ResolvedLock("untyped", LockMode.EXCLUSIVE_MOTION, "intent")
        with self.assertRaises(ValueError):
            LockIntent("intent", "untyped", LockMode.EXCLUSIVE_MOTION)

    def test_result_is_terminal_and_lifecycle_is_event_data(self):
        with self.assertRaises(ValueError):
            SkillResult("I", None, "RUNNING", "not terminal", 1, 2)
        initial = SkillRuntimeEvent("I", 0, None, SkillLifecycleState.ACCEPTED, 1)
        self.assertIsNone(initial.previous_state)
        event = SkillRuntimeEvent("I", 3, SkillLifecycleState.READY,
                                  SkillLifecycleState.RUNNING, 2,
                                  (("phase", "execute"),))
        self.assertEqual(event.state, SkillLifecycleState.RUNNING)
        with self.assertRaisesRegex(ValueError, "invalid skill lifecycle"):
            SkillRuntimeEvent("I", 1, SkillLifecycleState.ACCEPTED,
                              SkillLifecycleState.SUCCEEDED, 2)
        with self.assertRaisesRegex(ValueError, "initial runtime event"):
            SkillRuntimeEvent("I", 1, None, SkillLifecycleState.ACCEPTED, 2)
