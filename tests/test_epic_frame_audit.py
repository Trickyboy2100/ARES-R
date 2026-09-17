import json
import tempfile
import unittest

from ares_r.epic_frame_audit import build_record, compare, summarize, verdict, write_evidence


class SummarizeTest(unittest.TestCase):
    def test_mean_and_spread(self):
        summary = summarize([[0.0, 0.0, 0.0], [1.0, 2.0, -3.0], [2.0, 4.0, 3.0]])
        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["mean_mm"], [1.0, 2.0, 0.0])
        self.assertEqual(summary["spread_mm"], [2.0, 4.0, 6.0])
        self.assertEqual(summary["worst_spread_mm"], 6.0)

    def test_single_sample_has_no_spread(self):
        summary = summarize([[1.5, -2.5, 3.5]])
        self.assertEqual(summary["worst_spread_mm"], 0.0)

    def test_empty_samples_are_refused(self):
        with self.assertRaisesRegex(ValueError, "no samples"):
            summarize([])

    def test_three_coordinates_are_required(self):
        with self.assertRaisesRegex(ValueError, "three coordinates"):
            summarize([[0.0, 0.0], [1.0, 1.0, 1.0]])


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.before = summarize([[0.0, 0.0, 0.0], [0.2, -0.1, 0.1]])
        self.after = summarize([[100.0, 0.0, 0.0], [100.1, -0.2, 0.0]])

    def test_clean_hundred_millimetre_move(self):
        report = compare(self.before, self.after, 100.0, "车体前方")
        self.assertTrue(report["scale_within_tolerance"])
        self.assertEqual(report["dominant_axis"], "x")
        self.assertAlmostEqual(report["unit_direction"][0], 1.0, places=4)
        self.assertAlmostEqual(report["scale"], 1.0, delta=0.01)
        self.assertIn("尺度一致", verdict(report))

    def test_a_doubled_reading_is_caught(self):
        report = compare(self.before, self.after, 50.0, "车体前方")
        self.assertFalse(report["scale_within_tolerance"])
        self.assertIn("尺度不符", verdict(report))

    def test_unknown_distance_still_gives_the_direction(self):
        """No measured length means no scale claim, but the axis mapping is exact."""
        report = compare(self.before, self.after, None, "车体前方")
        self.assertIsNone(report["scale"])
        self.assertIsNone(report["scale_within_tolerance"])
        self.assertIsNone(report["residual_mm"])
        self.assertEqual(report["dominant_axis"], "x")
        self.assertAlmostEqual(report["unit_direction"][0], 1.0, places=4)
        self.assertIn("尺度仍未验证", verdict(report))
        json.dumps(report)

    def test_direction_is_identified(self):
        after = summarize([[0.0, -100.0, 0.0]])
        report = compare(self.before, after, 100.0, "沿地面向右")
        self.assertEqual(report["dominant_axis"], "y")
        self.assertLess(report["unit_direction"][1], -0.99)

    def test_zero_distance_is_refused(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            compare(self.before, self.after, 0.0, "none")

    def test_no_movement_is_refused(self):
        with self.assertRaisesRegex(ValueError, "did not move"):
            compare(self.before, self.before, 100.0, "none")

    def test_movement_inside_the_noise_is_reported(self):
        before = summarize([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
        after = summarize([[6.0, 0.0, 0.0], [7.0, 0.0, 0.0]])
        report = compare(before, after, 1.0, "tiny")
        self.assertTrue(report["noise_dominated"])
        self.assertIn("同量级", verdict(report))


class EvidenceTest(unittest.TestCase):
    def test_record_carries_the_verdict_and_the_raw_frames(self):
        before = summarize([[0.0, 0.0, 0.0]])
        after = summarize([[100.0, 0.0, 0.0]])
        report = compare(before, after, 100.0, "车体前方")
        record = build_record("move-x", "displacement", before, after, report, note="手推")
        self.assertEqual(record["session"], "move-x")
        self.assertEqual(record["operator_note"], "手推")
        self.assertEqual(record["comparison"]["dominant_axis"], "x")
        self.assertIn("Camera capture only", record["warning"])
        json.dumps(record)

    def test_evidence_is_written_once(self):
        payload = dict(schema_version=1, session="s1")
        with tempfile.TemporaryDirectory() as root:
            first = write_evidence(root, "s1", payload)
            self.assertTrue(first.is_file())
            self.assertIn("epic-frame", str(first))
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                write_evidence(root, "s1", payload)

    def test_session_name_must_be_plain(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "plain name"):
                write_evidence(root, "../escape", {})


if __name__ == "__main__":
    unittest.main()
