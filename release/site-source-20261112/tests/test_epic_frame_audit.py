import json
import math
import tempfile
import unittest

from ares_r.epic_frame_audit import (DEFAULT_REPEAT_POSITION_MM, DEFAULT_REPEAT_ROTATION_DEG,
                                     EULER_ORDERS, build_record, compare, convention_verdict,
                                     match_orientation_convention, orientation_verdict,
                                     repeatability_verdict, rotation_difference_deg,
                                     rotation_matrix_ordered, scan_orientation_conventions,
                                     summarize, tool_axis_tilt_deg, verdict, write_evidence)

#: Captured 2026-09-18 from Epic space 2, five frames agreeing to under a
#: millimetre. The orientation question has to be answered on this data.
SITE_RPY_DEG = (89.737, -0.305, 46.524)
SITE_POSITION_MM = (474.32, -273.66, -179.98)


def _rpy_rad():
    return tuple(math.radians(value) for value in SITE_RPY_DEG)


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _matrix_to_zyx_rpy(matrix):
    """Inverse of ``rotation_matrix_ordered(..., "ZYX")``; enough for the tests."""
    ry = math.asin(max(-1.0, min(1.0, -matrix[2][0])))
    if abs(math.cos(ry)) > 1e-9:
        rx = math.atan2(matrix[2][1], matrix[2][2])
        rz = math.atan2(matrix[1][0], matrix[0][0])
    else:
        rx = 0.0
        rz = math.atan2(-matrix[0][1], matrix[1][1])
    return (rx, ry, rz)


class RotationOrderTest(unittest.TestCase):
    def test_zero_triple_is_the_identity_in_every_order(self):
        for order in EULER_ORDERS:
            self.assertEqual(rotation_matrix_ordered(0.0, 0.0, 0.0, order),
                             [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], order)

    def test_order_must_be_a_permutation(self):
        with self.assertRaisesRegex(ValueError, "permutation"):
            rotation_matrix_ordered(0.0, 0.0, 0.0, "ZZY")

    def test_orders_disagree_once_two_angles_are_large(self):
        zyx = rotation_matrix_ordered(*_rpy_rad(), "ZYX")
        xyz = rotation_matrix_ordered(*_rpy_rad(), "XYZ")
        self.assertFalse(all(abs(a - b) < 1e-3 for row_a, row_b in zip(zyx, xyz)
                             for a, b in zip(row_a, row_b)))

    def test_yaw_does_not_move_the_tool_z_component(self):
        """The fact that makes ``approach_axis`` convention-independent."""
        tilts = {order: tool_axis_tilt_deg(rotation_matrix_ordered(*_rpy_rad(), order), "+z")
                 for order in EULER_ORDERS}
        self.assertLess(max(abs(value) for value in tilts.values()), 1.0)
        self.assertLess(max(tilts.values()) - min(tilts.values()), 1.0)

    def test_axis_must_be_a_signed_tool_axis(self):
        with self.assertRaisesRegex(ValueError, "axis must be one of"):
            tool_axis_tilt_deg(rotation_matrix_ordered(0.0, 0.0, 0.0, "ZYX"), "z")

    def test_identity_puts_the_tool_z_axis_vertical(self):
        identity = rotation_matrix_ordered(0.0, 0.0, 0.0, "ZYX")
        self.assertAlmostEqual(tool_axis_tilt_deg(identity, "+z"), 90.0)
        self.assertAlmostEqual(tool_axis_tilt_deg(identity, "+x"), 0.0)


class ConventionScanTest(unittest.TestCase):
    def test_site_pose_leaves_several_horizontal_candidates(self):
        """Honest result: horizontality alone cannot pin the convention down."""
        found = scan_orientation_conventions(_rpy_rad())
        self.assertGreater(len(found), 1)
        self.assertIn("ZYX", {item["order"] for item in found})
        self.assertIn("+z", {item["axis"] for item in found})
        self.assertIn("需要一次物理姿态比对", orientation_verdict(found))

    def test_a_vertical_pose_has_no_horizontal_z_axis(self):
        """With the tool pointing straight down, only x and y can be horizontal."""
        found = scan_orientation_conventions((0.0, 0.0, 0.0))
        axes = {item["axis"] for item in found}
        self.assertNotIn("+z", axes)
        self.assertNotIn("-z", axes)
        self.assertEqual(axes, {"+x", "-x", "+y", "-y"})

    def test_empty_scan_is_reported_as_such(self):
        self.assertIn("不是六种常规欧拉序之一", orientation_verdict([]))

    def test_three_values_are_required(self):
        with self.assertRaisesRegex(ValueError, "three values"):
            scan_orientation_conventions((0.1, 0.2))

    def test_verdict_names_a_single_solution(self):
        found = [dict(order="ZYX", axis="+z", tilt_deg=0.24)]
        self.assertIn("唯一解", orientation_verdict(found))


class RotationDifferenceTest(unittest.TestCase):
    def test_a_rotation_differs_from_itself_by_nothing(self):
        rotation = rotation_matrix_ordered(*_rpy_rad(), "ZYX")
        self.assertAlmostEqual(rotation_difference_deg(rotation, rotation), 0.0, places=6)

    def test_a_known_yaw_difference_is_recovered(self):
        identity = rotation_matrix_ordered(0.0, 0.0, 0.0, "ZYX")
        yawed = rotation_matrix_ordered(0.0, 0.0, math.radians(30.0), "ZYX")
        self.assertAlmostEqual(rotation_difference_deg(identity, yawed), 30.0, places=6)

    def test_the_reference_order_wins_when_both_sides_agree(self):
        rpy = _rpy_rad()
        ranked = match_orientation_convention(rpy, rpy, "ZYX")
        self.assertEqual(ranked[0]["order"], "ZYX")
        self.assertAlmostEqual(ranked[0]["residual_deg"], 0.0, places=6)
        self.assertGreater(ranked[-1]["residual_deg"], 10.0)

    def test_a_half_turned_gripper_is_accepted(self):
        """A two-finger gripper grips the same part rotated half a turn."""
        rpy = _rpy_rad()
        reference = rotation_matrix_ordered(*rpy, "ZYX")
        half_turn = rotation_matrix_ordered(0.0, 0.0, math.pi, "ZYX")
        camera_rpy = _matrix_to_zyx_rpy(_matmul(reference, half_turn))
        ranked = match_orientation_convention(camera_rpy, rpy, "ZYX")
        self.assertEqual(ranked[0]["order"], "ZYX")
        self.assertLess(ranked[0]["residual_deg"], 1.0)
        self.assertTrue(ranked[0]["half_turn"])

    def test_without_symmetry_the_same_data_looks_wrong(self):
        """The regression that produced a misleading 137 deg verdict on 2026-09-18.

        With the true convention ZYX, a half-turned gripper scores far past the
        tolerance, so the audit would have rejected a perfectly good camera.
        """
        rpy = _rpy_rad()
        reference = rotation_matrix_ordered(*rpy, "ZYX")
        half_turn = rotation_matrix_ordered(0.0, 0.0, math.pi, "ZYX")
        camera_rpy = _matrix_to_zyx_rpy(_matmul(reference, half_turn))
        ranked = match_orientation_convention(camera_rpy, rpy, "ZYX", gripper_symmetry=False)
        zyx = [item for item in ranked if item["order"] == "ZYX"][0]
        self.assertGreater(zyx["residual_deg"], 100.0)

    def test_an_unknown_reference_order_is_refused(self):
        with self.assertRaisesRegex(ValueError, "permutation"):
            match_orientation_convention(_rpy_rad(), _rpy_rad(), "QWE")


class ConventionVerdictTest(unittest.TestCase):
    def test_a_clear_winner_is_named(self):
        ranked = [dict(order="ZYX", residual_deg=1.2), dict(order="ZXY", residual_deg=41.0)]
        self.assertIn("姿态约定 = ZYX", convention_verdict(ranked))

    def test_a_narrow_margin_is_refused(self):
        ranked = [dict(order="ZYX", residual_deg=1.2), dict(order="ZXY", residual_deg=2.0)]
        self.assertIn("不足以定死约定", convention_verdict(ranked))

    def test_a_large_residual_is_refused(self):
        ranked = [dict(order="ZYX", residual_deg=17.0), dict(order="ZXY", residual_deg=41.0)]
        self.assertIn("不在六种常规欧拉序之内", convention_verdict(ranked))

    def test_an_empty_ranking_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no ranked conventions"):
            convention_verdict([])


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


class RepeatabilityVerdictTest(unittest.TestCase):
    """Repeated detections: are they the same answer? Not: is the answer right."""

    def setUp(self):
        self.tight = summarize([[0.0, 0.0, 0.0], [0.1, -0.2, 0.3], [0.2, 0.1, -0.1]])

    def test_agreement_passes_and_names_the_spreads(self):
        result = repeatability_verdict(self.tight, 0.2)
        self.assertTrue(result["ok"])
        self.assertTrue(result["position_ok"])
        self.assertTrue(result["rotation_ok"])
        self.assertEqual(result["samples"], 3)
        self.assertAlmostEqual(result["worst_position_mm"], 0.4, places=6)
        self.assertIn("同一个抓取点", result["sentence"])

    def test_a_position_jump_is_caught(self):
        jumped = summarize([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
        result = repeatability_verdict(jumped, 0.0)
        self.assertFalse(result["ok"])
        self.assertTrue(result["position_ok"] is False)
        self.assertTrue(result["rotation_ok"])
        self.assertIn("位置极差", result["sentence"])
        self.assertIn("不是同一个抓取点", result["sentence"])

    def test_a_rotation_jump_is_caught(self):
        result = repeatability_verdict(self.tight, 3.0)
        self.assertFalse(result["ok"])
        self.assertTrue(result["position_ok"])
        self.assertFalse(result["rotation_ok"])
        self.assertIn("姿态极差", result["sentence"])

    def test_both_gates_failing_are_both_reported(self):
        jumped = summarize([[0.0, 0.0, 0.0], [9.0, 0.0, 0.0]])
        sentence = repeatability_verdict(jumped, 9.0)["sentence"]
        self.assertIn("位置极差", sentence)
        self.assertIn("姿态极差", sentence)

    def test_the_gate_is_inclusive_at_the_threshold(self):
        summary = summarize([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertTrue(repeatability_verdict(summary, 0.5, 1.0, 0.5)["ok"])

    def test_defaults_clear_the_measured_three_sample_noise_floor(self):
        """2026-09-20 ``right_pick``: three bursts spread 0.39 / 0.76 / 0.92 mm."""
        for worst_mm in (0.388, 0.762, 0.920):
            summary = summarize([[0.0, 0.0, 0.0], [worst_mm, 0.0, 0.0]])
            self.assertTrue(repeatability_verdict(summary, 0.36)["ok"], worst_mm)

    def test_tolerances_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            repeatability_verdict(self.tight, 0.0, 0.0, 0.5)
        with self.assertRaisesRegex(ValueError, "positive"):
            repeatability_verdict(self.tight, 0.0, DEFAULT_REPEAT_POSITION_MM, -1.0)

    def test_a_raw_sample_list_is_refused(self):
        with self.assertRaisesRegex(ValueError, "summarize"):
            repeatability_verdict([[0.0, 0.0, 0.0]], 0.0)


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

    def test_evidence_kind_names_its_own_directory(self):
        payload = dict(schema_version=1, session="s2")
        with tempfile.TemporaryDirectory() as root:
            path = write_evidence(root, "s2", payload, "epic-repeatability")
            self.assertIn("epic-repeatability", str(path))
            self.assertNotIn("epic-frame", str(path))

    def test_evidence_kind_must_be_plain(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "plain name"):
                write_evidence(root, "s3", {}, "../escape")

    def test_session_name_must_be_plain(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "plain name"):
                write_evidence(root, "../escape", {})


if __name__ == "__main__":
    unittest.main()
