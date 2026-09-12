import unittest

from ares_r.skills import CapabilityRequirement, SkillMaturity
from ares_r.skills.providers import (CapabilityRegistry, ProviderDescriptor,
    ProviderHealth, ProviderMode)


class StubProvider:
    def __init__(self, provider_id, capabilities, ceiling=SkillMaturity.SPECIFIED,
                 protocol_version=1):
        self._descriptor = ProviderDescriptor(provider_id, "impl-1", protocol_version, ProviderMode.MOCK,
            capabilities, ceiling, False, ProviderHealth.READY)
        self.calls = 0

    @property
    def descriptor(self):
        return self._descriptor


class ProviderRegistryTests(unittest.TestCase):
    def test_deterministic_resolution(self):
        registry = CapabilityRegistry()
        z = StubProvider("z", ("motion.plan",)); a = StubProvider("a", ("motion.plan",))
        registry.register(z); registry.register(a)
        result = registry.resolve((CapabilityRequirement("motion.plan"),), ProviderMode.MOCK)
        self.assertTrue(result.successful)
        self.assertEqual(result.providers[0].descriptor.provider_id, "a")

    def test_duplicate_and_capability_mismatch(self):
        registry = CapabilityRegistry(); provider = StubProvider("p", ("one",))
        registry.register(provider)
        with self.assertRaises(ValueError): registry.register(provider)
        result = registry.resolve((CapabilityRequirement("missing"),), ProviderMode.MOCK)
        self.assertEqual(result.missing_capabilities, ("missing",))

    def test_maturity_ceiling(self):
        registry = CapabilityRegistry(); registry.register(StubProvider("p", ("one",)))
        result = registry.resolve((CapabilityRequirement("one"),), ProviderMode.MOCK,
                                  SkillMaturity.MOCK_VERIFIED)
        self.assertFalse(result.successful)

    def test_integer_protocol_compatibility(self):
        for provider_version, required_version, expected in (
                (1, 1, True), (2, 1, True), (1, 2, False), (10, 2, True)):
            registry = CapabilityRegistry()
            registry.register(StubProvider("p", ("cap",), protocol_version=provider_version))
            result = registry.resolve((CapabilityRequirement("cap", required_version),),
                                      ProviderMode.MOCK)
            self.assertEqual(result.successful, expected)
