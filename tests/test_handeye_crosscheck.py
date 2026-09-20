import unittest
from pathlib import Path

from ares_r.perception.handeye_crosscheck import build_report


REPOSITORY = Path(__file__).resolve().parents[1]


class DualArmHandeyeCrosscheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report(REPOSITORY)

    def test_forward_semantic_is_decisive(self):
        h1 = self.report["hypotheses"]["H1"]
        h2 = self.report["hypotheses"]["H2"]
        self.assertLess(h1["translation_disagreement_mm"], 5.0)
        self.assertLess(h1["rotation_disagreement_deg"], 2.0)
        self.assertGreater(h2["translation_disagreement_mm"], 100.0)
        self.assertGreater(h2["rotation_disagreement_deg"], 20.0)

    def test_board_and_existing_config_validate_right_chain(self):
        board = self.report["board_check"]["right"]
        self.assertLess(abs(board["origin_table_height_error_mm"]), 30.0)
        self.assertLess(board["normal_to_body_up_deg"], 2.0)
        self.assertTrue(self.report["configured_transform_check"]["is_right_H1_chain"])

    def test_verdict_allows_p1_without_averaging(self):
        self.assertEqual(self.report["state"], "COMMISSIONED")
        self.assertTrue(self.report["p1_allowed"])
        self.assertEqual(self.report["fusion_policy"], "no left/right averaging")


if __name__ == "__main__":
    unittest.main()
