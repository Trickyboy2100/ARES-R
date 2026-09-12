import unittest

from ares_r.skills import (FailureCode, ParameterSpec, PlannerExposure,
    SafetyClass, SkillDefinition, SkillLayer, TimeoutPolicy)
from ares_r.skills.catalog import build_tier_a_registry
from ares_r.skills.schema_export import export_function_schema, export_registry_schemas


class SchemaExportTests(unittest.TestCase):
    def test_approved_semantic_skill_exported_closed(self):
        registry = build_tier_a_registry()
        schema = export_function_schema(registry.get("manipulation.pick"))
        self.assertFalse(schema["parameters"]["additionalProperties"])
        self.assertEqual(schema["parameters"]["properties"]["object"]["type"], "string")
        exported = export_registry_schemas(registry.definitions())
        self.assertEqual(len(exported), 14)

    def test_quantities_are_explicit_typed_objects(self):
        schema = export_function_schema(build_tier_a_registry().get("manipulation.turn"))
        target = schema["parameters"]["properties"]["target"]
        self.assertEqual(target["type"], "object")
        self.assertFalse(target["additionalProperties"])
        self.assertEqual(set(target["required"]), {"value", "unit"})

    def test_l0_and_raw_control_rejected(self):
        unsafe = SkillDefinition("hw.servo_joint", 1, "1", "unsafe", SkillLayer.L0_HARDWARE,
            "hardware", (), (), (), (), (), (), (), (), TimeoutPolicy(1, 1, 1),
            (FailureCode.EXECUTION_FAILED,), PlannerExposure.LLM, SafetyClass.S2_MOTION)
        with self.assertRaises(ValueError): export_function_schema(unsafe)
        names = " ".join(item["name"] for item in
                         export_registry_schemas(build_tier_a_registry().definitions()))
        for raw in ("servo", "joint", "tcp", "base_velocity", "safety_reset", "provider"):
            self.assertNotIn(raw, names.lower())
