import dataclasses
import math
import unittest

from ares_r.skills import (CapabilityRequirement, FailureCode, LockMode,
    LockRequirement, ParameterSpec, PlannerExposure, ResourceRequirement,
    SafetyClass, SkillDefinition, SkillLayer, SkillMaturity, TimeoutPolicy)


def definition():
    return SkillDefinition("manipulation.pick", 1, "1.0.0", "Pick resource",
        SkillLayer.L2_MANIPULATION, "manipulation",
        (ParameterSpec("object", "resource", resource_types=("Container",)),),
        (CapabilityRequirement("motion.plan"),),
        (ResourceRequirement("object", ("Container",)),),
        ("object_free",), ("zone_clear",), ("attached",), (),
        (LockRequirement("object", LockMode.EXCLUSIVE_MOTION),),
        TimeoutPolicy(5, 30, 5), (FailureCode.PLAN_FAILED,),
        PlannerExposure.LLM, SafetyClass.S2_MOTION, motion_bearing=True)


class ContractTests(unittest.TestCase):
    def test_immutable_and_closed_enums(self):
        item = definition()
        self.assertEqual(item.maturity, SkillMaturity.SPECIFIED)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.skill_id = "changed"
        with self.assertRaises(ValueError):
            SkillLayer("MALFORMED")

    def test_parameter_contract_rejects_implicit_quantity(self):
        with self.assertRaises(ValueError):
            ParameterSpec("mass", "quantity")
        with self.assertRaises(ValueError):
            TimeoutPolicy(math.inf, 1, 1)

    def test_unknown_constructor_fields_are_rejected(self):
        values = dataclasses.asdict(definition())
        values["unknown"] = True
        with self.assertRaises(TypeError):
            SkillDefinition(**values)
