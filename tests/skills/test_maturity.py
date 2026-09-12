import unittest

from ares_r.skills import (MaturityEvidence, MaturityEvidenceKey,
    MaturityEvidenceRegistry, SkillMaturity)
from ares_r.skills import context


class MaturityTests(unittest.TestCase):
    def test_evidence_order(self):
        self.assertLess(SkillMaturity.SPECIFIED, SkillMaturity.MOCK_VERIFIED)
        self.assertLess(SkillMaturity.SIM_VERIFIED, SkillMaturity.REAL_DRYRUN)
        self.assertLess(SkillMaturity.REAL_DRYRUN, SkillMaturity.REAL_COMMISSIONED)

    def test_s1a_execution_boundaries_are_explicit(self):
        self.assertFalse(context.SKILL_RUNTIME_IMPLEMENTED)
        self.assertEqual(context.CONTRACT_V1, "FROZEN")
        self.assertFalse(context.LOCK_MANAGER_IMPLEMENTED)
        self.assertFalse(context.MOCK_SKILL_EXECUTION_IMPLEMENTED)
        self.assertFalse(context.PRODUCTION_EXECUTION_LEASE_IMPLEMENTED)
        self.assertFalse(context.ISAAC_PROVIDER_IMPLEMENTED)
        self.assertFalse(context.REAL_PROVIDER_IMPLEMENTED)

    def test_scoped_maturity_evidence_lookup(self):
        key = MaturityEvidenceKey("manipulation.pick", "1.0.0", "mock",
                                  "robot-r1", "tool-r1", "config-r1")
        evidence = MaturityEvidence(key, SkillMaturity.MOCK_VERIFIED, "a" * 64, 1)
        registry = MaturityEvidenceRegistry((evidence,))
        self.assertEqual(registry.lookup(key), evidence)
        other = MaturityEvidenceKey("manipulation.pick", "1.0.0", "mock",
                                    "robot-r2", "tool-r1", "config-r1")
        self.assertIsNone(registry.lookup(other))


if __name__ == "__main__":
    unittest.main()
