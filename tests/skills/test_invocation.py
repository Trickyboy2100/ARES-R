import dataclasses
import math
import unittest

from ares_r.skills import SkillInvocation, canonical_json, digest


class InvocationTests(unittest.TestCase):
    def test_parameters_are_immutable_and_sorted(self):
        item = SkillInvocation("I1", "manipulation.pick", "1", (("z", 2), ("a", 1)),
                               "test", 1, "W1", "once")
        self.assertEqual(item.parameters, (("a", 1), ("z", 2)))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.skill_id = "x"

    def test_nonfinite_is_rejected(self):
        with self.assertRaises(ValueError):
            SkillInvocation("I", "x.y", "1", (("x", math.nan),), "t", 1, "W", "K")

    def test_stable_json(self):
        one = SkillInvocation("I", "x.y", "1", (("b", 2), ("a", 1)), "t", 1, "W", "K")
        two = SkillInvocation("I", "x.y", "1", (("a", 1), ("b", 2)), "t", 1, "W", "K")
        self.assertEqual(canonical_json(one), canonical_json(two))
        self.assertEqual(digest(one), digest(two))
