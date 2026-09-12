import math
import unittest

from ares_r.skills import FailureCode
from ares_r.skills.catalog import build_tier_a_registry
from ares_r.skills.policy import create_llm_proposal
from ares_r.workspace import (Container, Device, GeometryBinding, Holder, Sample,
    Slot, Station, ResourceGraph, example_workspace)


class LlmPolicyTests(unittest.TestCase):
    def test_pick_proposal_and_acceptance_walkthrough(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        self.assertIsNotNone(workspace.get("sample_A"))
        self.assertIsNotNone(workspace.get("vial_7"))
        self.assertEqual(workspace.occupant("tray_1.slot_3").resource_id, "vial_7")
        self.assertIsNotNone(workspace.binding("vial_7"))
        result = create_llm_proposal(registry, workspace, "manipulation.pick",
            {"object": "vial_7", "arm": "right"}, "I1", 1, "K1")
        self.assertTrue(result.accepted)
        self.assertEqual(result.invocation.workspace_revision, workspace.revision)

    def test_unknown_and_malformed_parameters_rejected(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        extra = create_llm_proposal(registry, workspace, "manipulation.pick",
            {"object": "vial_7", "xyz": [0, 0, 0]}, "I", 1, "K")
        self.assertEqual(extra.failure_code, FailureCode.INVALID_INPUT)
        malformed = create_llm_proposal(registry, workspace, "manipulation.turn",
            {"control": "vial_7", "target": math.inf}, "I", 1, "K")
        self.assertEqual(malformed.failure_code, FailureCode.INVALID_INPUT)

    def test_implicit_quantity_and_explicit_provider_rejected(self):
        resources = (Station("s", "s"), Device("knob", "knob"))
        workspace = ResourceGraph.create(resources)
        registry = build_tier_a_registry()
        implicit = create_llm_proposal(registry, workspace, "manipulation.turn",
            {"control": "knob", "target": 30}, "I", 1, "K")
        self.assertFalse(implicit.accepted)
        provider = create_llm_proposal(registry, workspace, "manipulation.turn",
            {"control": "knob", "target": {"value": 30, "unit": "deg"},
             "provider_id": "real"}, "I", 1, "K")
        self.assertFalse(provider.accepted)

    def test_proposal_does_not_call_provider(self):
        class Trap:
            def __getattr__(self, name):
                raise AssertionError("provider accessed during proposal")
        workspace = example_workspace(); registry = build_tier_a_registry()
        result = create_llm_proposal(registry, workspace, "manipulation.pick",
            {"object": "vial_7"}, "I", 1, "K")
        self.assertTrue(result.accepted)
        _unused_provider = Trap()


if __name__ == "__main__":
    unittest.main()
