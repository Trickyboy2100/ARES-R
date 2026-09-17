"""Section 6 singularity metrics must be reproducible and correctly scaled."""

import math
import unittest

from ares_r.motion.singularity import (AMBER_LIMITS, L_REF_M, RED_LIMITS, classify,
                                       evaluate, metrics_from_jacobian, scale_jacobian,
                                       soft_limit_margin, summarize)


def identity_blocks(reference_length=L_REF_M):
    """Blocks whose scaled Jacobian is exactly the 6x6 identity."""
    linear = [[0.0] * 6 for _ in range(3)]
    angular = [[0.0] * 6 for _ in range(3)]
    for index in range(3):
        linear[index][index] = reference_length
        angular[index][index + 3] = 1.0
    return linear, angular


def blocks_from_columns(columns):
    """``columns`` is six ``(linear3, angular3)`` pairs in joint order."""
    linear = [[columns[joint][0][row] for joint in range(6)] for row in range(3)]
    angular = [[columns[joint][1][row] for joint in range(6)] for row in range(3)]
    return linear, angular


WRIST_SINGULAR_COLUMNS = (
    ([0.20, 0.0, 0.0], [0.0, 0.0, 1.0]),
    ([0.30, 0.0, 0.0], [0.0, 1.0, 0.0]),
    ([0.15, 0.0, 0.0], [0.0, 1.0, 0.0]),
    ([0.0, -0.05, 0.0], [1.0, 0.0, 0.0]),
    ([0.0, 0.0, 0.10], [0.0, 1.0, 0.0]),
    ([0.0, -0.05, 0.0], [1.0, 0.0, 0.0]),  # aligned with joint 4 when J5 = 0
)


class ScaledJacobianTest(unittest.TestCase):
    def test_identity_blocks_scale_to_unit_singular_values(self):
        linear, angular = identity_blocks()
        metrics = metrics_from_jacobian(linear, angular, [0.0] * 6)
        self.assertAlmostEqual(metrics["sigma_min_scaled"], 1.0)
        self.assertAlmostEqual(metrics["sigma_max_scaled"], 1.0)
        self.assertAlmostEqual(metrics["condition_number_scaled"], 1.0)
        self.assertAlmostEqual(metrics["manipulability_scaled"], 1.0)

    def test_reference_length_fixes_translation_rotation_mixing(self):
        linear, angular = identity_blocks()
        stretched = [[value * 10.0 for value in row] for row in linear]
        metrics = metrics_from_jacobian(stretched, angular, [0.0] * 6)
        # 10x the translational block is exactly 10x the condition number only
        # because both blocks were divided by the same fixed reference length.
        self.assertAlmostEqual(metrics["condition_number_scaled"], 10.0)
        self.assertAlmostEqual(metrics["reference_length_m"], L_REF_M)

    def test_reference_length_must_be_positive_and_finite(self):
        linear, angular = identity_blocks()
        for reference in (0.0, -0.5, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                scale_jacobian(linear, angular, reference)

    def test_block_shapes_and_values_are_checked(self):
        linear, angular = identity_blocks()
        with self.assertRaises(ValueError):
            scale_jacobian(linear[:2], angular)
        with self.assertRaises(ValueError):
            scale_jacobian(linear, [row[:5] for row in angular])
        broken = [row[:] for row in linear]
        broken[0][0] = float("nan")
        with self.assertRaises(ValueError):
            scale_jacobian(broken, angular)

    def test_joint_vector_is_validated(self):
        linear, angular = identity_blocks()
        for joints in ([0.0] * 5, [0.0] * 7, [float("nan")] + [0.0] * 5):
            with self.assertRaises(ValueError):
                metrics_from_jacobian(linear, angular, joints)


class WristSingularityTest(unittest.TestCase):
    def test_aligned_wrist_axes_are_rank_deficient_and_red(self):
        linear, angular = blocks_from_columns(WRIST_SINGULAR_COLUMNS)
        record = evaluate([0.0, 0.3, -0.2, 0.4, 0.0, 0.9], linear, angular)
        # Numerically the rank drops by one, so the smallest singular value is
        # only near zero; the condition number is huge rather than exactly inf.
        self.assertLess(record["sigma_min_scaled"], 1e-9)
        self.assertGreater(record["condition_number_scaled"], RED_LIMITS["condition_number_scaled"])
        self.assertAlmostEqual(record["manipulability_scaled"], 0.0, places=9)
        self.assertAlmostEqual(record["abs_sin_j5"], 0.0)
        self.assertEqual(record["level"], "RED")

    def test_abs_sin_j5_tracks_joint_five_only(self):
        linear, angular = identity_blocks()
        record = evaluate([0.1, 0.2, 0.3, 0.4, math.radians(90.0), 0.6], linear, angular)
        self.assertAlmostEqual(record["abs_sin_j5"], 1.0)
        self.assertEqual(record["level"], "OK")


class ClassificationTest(unittest.TestCase):
    def metrics(self, **overrides):
        base = {"sigma_min_scaled": 1.0, "condition_number_scaled": 1.0, "abs_sin_j5": 1.0}
        base.update(overrides)
        return base

    def test_healthy_configuration_is_ok(self):
        self.assertEqual(classify(self.metrics()), "OK")

    def test_amber_limits_apply_below_the_red_limits(self):
        self.assertEqual(classify(self.metrics(sigma_min_scaled=0.04)), "AMBER")
        self.assertEqual(classify(self.metrics(condition_number_scaled=150.0)), "AMBER")
        self.assertEqual(classify(self.metrics(abs_sin_j5=0.08)), "AMBER")

    def test_red_limits_win_over_amber(self):
        self.assertEqual(classify(self.metrics(sigma_min_scaled=0.01)), "RED")
        self.assertEqual(classify(self.metrics(condition_number_scaled=250.0)), "RED")
        self.assertEqual(classify(self.metrics(abs_sin_j5=0.01)), "RED")
        self.assertEqual(classify(self.metrics(manipulability_scaled=0.0,
                                              condition_number_scaled=float("inf"))), "RED")

    def test_thresholds_match_the_commissioned_section_6_values(self):
        self.assertEqual(RED_LIMITS, {"sigma_min_scaled": 0.02,
                                      "condition_number_scaled": 200.0, "abs_sin_j5": 0.05})
        self.assertEqual(AMBER_LIMITS, {"sigma_min_scaled": 0.05,
                                        "condition_number_scaled": 100.0, "abs_sin_j5": 0.10})
        # Exactly at a limit is inside the band, not outside it.
        self.assertEqual(classify(self.metrics(sigma_min_scaled=RED_LIMITS["sigma_min_scaled"])), "AMBER")
        self.assertEqual(classify(self.metrics(sigma_min_scaled=AMBER_LIMITS["sigma_min_scaled"])), "OK")


class MarginAndSummaryTest(unittest.TestCase):
    def test_soft_limit_margin_reports_the_smallest_distance(self):
        lower = [-1.0] * 6
        upper = [1.0] * 6
        joints = [0.0, 0.0, 0.0, 0.0, 0.85, 0.0]
        self.assertAlmostEqual(soft_limit_margin(joints, lower, upper), 0.15)
        with self.assertRaises(ValueError):
            soft_limit_margin([0.0] * 6, lower[:5], upper)

    def test_summary_reports_worst_sample_and_level_counts(self):
        linear, angular = identity_blocks()
        records = [
            evaluate([0.0, 0.0, 0.0, 0.0, 0.7, 0.0], linear, angular,
                     sample_index=0, tcp_m=[0.1, -0.3, 1.0]),
            evaluate([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], *blocks_from_columns(WRIST_SINGULAR_COLUMNS),
                     sample_index=7, tcp_m=[0.2, -0.25, 0.95]),
            evaluate([0.0, 0.0, 0.0, 0.0, math.radians(90.0), 0.0], linear, angular, sample_index=9),
        ]
        summary = summarize(records)
        self.assertEqual(summary["sample_count"], 3)
        self.assertEqual(summary["levels"], {"RED": 1, "AMBER": 0, "OK": 2})
        self.assertLess(summary["min_sigma_min_scaled"], 1e-9)
        self.assertGreater(summary["max_condition_number_scaled"], RED_LIMITS["condition_number_scaled"])
        self.assertEqual(summary["worst"]["sample_index"], 7)
        self.assertEqual(summary["worst"]["tcp_m"], [0.2, -0.25, 0.95])
        self.assertEqual(len(summary["worst"]["joints_rad"]), 6)
        self.assertAlmostEqual(summary["min_abs_sin_j5"], 0.0)
        self.assertAlmostEqual(summary["reference_length_m"], L_REF_M)

    def test_summary_rejects_an_empty_sample_set(self):
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
