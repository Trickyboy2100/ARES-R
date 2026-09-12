import math
import unittest

from ares_r.skills import FailureCode
from ares_r.skills.catalog import build_tier_a_registry
from ares_r.skills.policy import LlmProposalPolicy, create_llm_proposal
from ares_r.workspace import (Container, Device, GeometryBinding, Holder, Sample,
    Slot, Station, ResourceGraph, example_workspace)


class LlmPolicyTests(unittest.TestCase):
    def test_pick_proposal_and_acceptance_walkthrough(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        self.assertIsNotNone(workspace.get("sample_A"))
        self.assertIsNotNone(workspace.get("vial_7"))
        self.assertEqual(workspace.occupant("tray_1.slot_3").resource_id, "vial_7")
        self.assertIsNotNone(workspace.binding("vial_7"))
        result = create_llm_proposal(registry, workspace, LlmProposalPolicy.development(), "manipulation.pick",
            {"object": "vial_7", "arm": "right"}, "I1", 1, "K1")
        self.assertTrue(result.accepted)
        self.assertEqual(result.invocation.workspace_revision, workspace.revision)

    def test_unknown_and_malformed_parameters_rejected(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        extra = create_llm_proposal(registry, workspace, LlmProposalPolicy.development(), "manipulation.pick",
            {"object": "vial_7", "xyz": [0, 0, 0]}, "I", 1, "K")
        self.assertEqual(extra.failure_code, FailureCode.INVALID_INPUT)
        device_workspace = ResourceGraph.create((Device("device", "device"),))
        malformed = create_llm_proposal(registry, device_workspace, LlmProposalPolicy.development(), "device.start",
            {"device": "device", "program": "p", "duration": {"value": math.inf, "unit": "s"}}, "I", 1, "K")
        self.assertEqual(malformed.failure_code, FailureCode.INVALID_INPUT)

    def test_implicit_quantity_and_explicit_provider_rejected(self):
        resources = (Station("s", "s"), Device("knob", "knob"))
        workspace = ResourceGraph.create(resources)
        registry = build_tier_a_registry()
        implicit = create_llm_proposal(registry, workspace, LlmProposalPolicy.development(), "device.start",
            {"device": "knob", "program": "p", "duration": 30}, "I", 1, "K")
        self.assertFalse(implicit.accepted)
        provider = create_llm_proposal(registry, workspace, LlmProposalPolicy.development(), "device.start",
            {"device": "knob", "program": "p", "duration": {"value": 30, "unit": "s"},
             "provider_id": "real"}, "I", 1, "K")
        self.assertFalse(provider.accepted)

    def test_proposal_does_not_call_provider(self):
        class Trap:
            def __getattr__(self, name):
                raise AssertionError("provider accessed during proposal")
        workspace = example_workspace(); registry = build_tier_a_registry()
        result = create_llm_proposal(registry, workspace, LlmProposalPolicy.development(), "manipulation.pick",
            {"object": "vial_7"}, "I", 1, "K")
        self.assertTrue(result.accepted)
        _unused_provider = Trap()

    def test_development_mock_and_production_maturity_policies(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        arguments = (registry, workspace)
        params = {"object": "vial_7"}
        development = create_llm_proposal(*arguments, LlmProposalPolicy.development(),
            "manipulation.pick", params, "I1", 1, "K1")
        mock = create_llm_proposal(*arguments, LlmProposalPolicy.mock(),
            "manipulation.pick", params, "I2", 1, "K2")
        production = create_llm_proposal(*arguments, LlmProposalPolicy.production(),
            "manipulation.pick", params, "I3", 1, "K3")
        self.assertTrue(development.accepted)
        self.assertEqual(mock.failure_code, FailureCode.SAFETY_REJECTED)
        self.assertEqual(production.failure_code, FailureCode.SAFETY_REJECTED)

    def test_policy_allowlist(self):
        workspace = example_workspace(); registry = build_tier_a_registry()
        policy = LlmProposalPolicy.development()
        policy = LlmProposalPolicy(policy.minimum_maturity, policy.allowed_safety_classes,
                                   policy.deployment_mode, ("device.start",))
        result = create_llm_proposal(registry, workspace, policy, "manipulation.pick",
            {"object": "vial_7"}, "I", 1, "K")
        self.assertFalse(result.accepted)


if __name__ == "__main__":
    unittest.main()
