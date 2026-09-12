import unittest

from ares_r.skills import SkillMaturity


class MaturityTests(unittest.TestCase):
    def test_evidence_order(self):
        self.assertLess(SkillMaturity.SPECIFIED, SkillMaturity.MOCK_VERIFIED)
        self.assertLess(SkillMaturity.SIM_VERIFIED, SkillMaturity.REAL_DRYRUN)
        self.assertLess(SkillMaturity.REAL_DRYRUN, SkillMaturity.REAL_COMMISSIONED)


if __name__ == "__main__":
    unittest.main()
