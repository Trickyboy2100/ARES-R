import unittest

from ares_r.skills import SkillMaturity
from ares_r.skills.catalog import TIER_A_SKILLS, build_tier_a_registry


class SkillRegistryTests(unittest.TestCase):
    def test_tier_a_loaded_and_all_specified(self):
        registry = build_tier_a_registry()
        self.assertEqual(len(registry.definitions()), 14)
        self.assertTrue(all(item.maturity == SkillMaturity.SPECIFIED for item in TIER_A_SKILLS))
        self.assertEqual(registry.get("manipulation.pick").implementation_version, "1.0.0")

    def test_duplicate_registration_and_version_mismatch(self):
        registry = build_tier_a_registry()
        with self.assertRaises(ValueError):
            registry.register(TIER_A_SKILLS[0])
        with self.assertRaises(KeyError):
            registry.get("manipulation.pick", "2.0.0")

    def test_maturity_filter(self):
        registry = build_tier_a_registry()
        self.assertEqual(len(registry.definitions(SkillMaturity.SPECIFIED)), 14)
