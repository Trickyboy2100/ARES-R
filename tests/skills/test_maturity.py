import unittest

from ares_r.skills import SkillMaturity
from ares_r.skills import context


class MaturityTests(unittest.TestCase):
    def test_evidence_order(self):
        self.assertLess(SkillMaturity.SPECIFIED, SkillMaturity.MOCK_VERIFIED)
        self.assertLess(SkillMaturity.SIM_VERIFIED, SkillMaturity.REAL_DRYRUN)
        self.assertLess(SkillMaturity.REAL_DRYRUN, SkillMaturity.REAL_COMMISSIONED)

    def test_s1a_execution_boundaries_are_explicit(self):
        self.assertFalse(context.SKILL_RUNTIME_IMPLEMENTED)
        self.assertFalse(context.EXECUTION_LEASE_IMPLEMENTED)
        self.assertFalse(context.MOCK_SKILL_EXECUTION_IMPLEMENTED)
        self.assertFalse(context.ISAAC_PROVIDER_IMPLEMENTED)
        self.assertFalse(context.REAL_PROVIDER_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
