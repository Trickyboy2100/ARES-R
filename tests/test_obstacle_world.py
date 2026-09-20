import numpy as np
import unittest

from ares_r.perception.obstacle_world import (aabb_from_points, crop_roi, joint_state_matches,
                                              remove_support, scene_object_specs,
                                              self_filter, self_filter_completeness,
                                              support_slab)


def _grid(count=1000, extent=0.5):
    rng = np.random.default_rng(7)
    return rng.uniform(-extent, extent, (count, 3))


class CropRoiTest(unittest.TestCase):
    def test_points_outside_the_box_are_dropped(self):
        points = np.array([[0.0, 0.0, 0.5], [5.0, 0.0, 0.5], [0.0, -5.0, 0.5]])
        kept, record = crop_roi(points, [-1, -1, 0], [1, 1, 1])
        self.assertEqual(len(kept), 1)
        self.assertEqual(record["before"], 3)
        self.assertEqual(record["after"], 1)

    def test_the_box_boundary_is_inclusive(self):
        points = np.array([[1.0, 1.0, 1.0]])
        kept, _ = crop_roi(points, [-1, -1, 0], [1, 1, 1])
        self.assertEqual(len(kept), 1)

    def test_inverted_bounds_are_refused(self):
        with self.assertRaisesRegex(ValueError, "max must exceed min"):
            crop_roi(_grid(10), [1, 0, 0], [0, 1, 1])

    def test_a_bad_shape_is_refused(self):
        with self.assertRaisesRegex(ValueError, r"\(n, 3\)"):
            crop_roi(np.zeros((4, 2)), [0, 0, 0], [1, 1, 1])


class SelfFilterTest(unittest.TestCase):
    SPHERE = dict(center_body_m=[0.0, 0.0, 0.0], radius_m=0.1)

    def test_points_inside_the_sphere_plus_margin_are_dropped(self):
        points = np.array([[0.0, 0.0, 0.0], [0.105, 0.0, 0.0], [0.5, 0.0, 0.0]])
        kept, record = self_filter(points, [self.SPHERE], margin_m=0.01)
        self.assertEqual(len(kept), 1)
        self.assertAlmostEqual(kept[0][0], 0.5)
        self.assertEqual(record["removed"], 2)
        self.assertEqual(record["sphere_count"], 1)

    def test_the_margin_is_conservative_so_an_under_modelled_arm_leaves_nothing(self):
        """A point just outside the modelled skin must still be removed."""
        points = np.array([[0.1005, 0.0, 0.0]])
        kept, _ = self_filter(points, [self.SPHERE], margin_m=0.005)
        self.assertEqual(len(kept), 0)

    def test_an_empty_sphere_list_is_refused_rather_than_disabling_the_filter(self):
        with self.assertRaisesRegex(ValueError, "at least one sphere"):
            self_filter(_grid(10), [])

    def test_a_bad_sphere_is_refused(self):
        with self.assertRaisesRegex(ValueError, "positive radius"):
            self_filter(_grid(10), [dict(center_body_m=[0, 0, 0], radius_m=0.0)])

    def test_a_negative_margin_is_refused(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self_filter(_grid(10), [self.SPHERE], margin_m=-0.01)

    def test_the_removed_gap_is_reported_so_the_filter_can_be_audited(self):
        points = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
        _, record = self_filter(points, [self.SPHERE], margin_m=0.01)
        self.assertAlmostEqual(record["removed_gap_m"]["min"], -0.1, places=9)


class RemoveSupportTest(unittest.TestCase):
    def test_the_band_around_the_surface_is_removed(self):
        points = np.array([[0.0, 0.0, 0.75], [0.0, 0.0, 0.80], [0.0, 0.0, 0.90]])
        kept, record = remove_support(points, 0.75, half_band_m=0.03)
        self.assertEqual(len(kept), 2)
        self.assertEqual(record["removed"], 1)

    def test_a_zero_band_is_refused(self):
        with self.assertRaisesRegex(ValueError, "positive band"):
            remove_support(_grid(10), 0.75, half_band_m=0.0)

    def test_a_non_finite_height_is_refused(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            remove_support(_grid(10), float("nan"))


class AabbTest(unittest.TestCase):
    def test_inflation_grows_the_box_on_every_side(self):
        points = np.array([[0.0, 0.0, 0.0], [0.1, 0.1, 0.1]])
        box = aabb_from_points(points, inflation_m=0.02, min_points=2)
        self.assertAlmostEqual(box["dims_m"][0], 0.14, places=9)
        self.assertAlmostEqual(box["center_m"][0], 0.05, places=9)
        self.assertAlmostEqual(box["inflation_m"], 0.02, places=9)

    def test_a_cluster_below_the_voxel_floor_is_dropped(self):
        self.assertIsNone(aabb_from_points(_grid(5), 0.02, min_points=18))

    def test_a_background_sized_box_is_dropped_as_not_an_object(self):
        wide = np.array([[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]])
        self.assertIsNone(aabb_from_points(wide, 0.02, min_points=2, max_volume_m3=1.0))

    def test_a_bad_shape_is_refused(self):
        with self.assertRaisesRegex(ValueError, r"\(n, 3\)"):
            aabb_from_points(np.zeros((3, 2)), 0.02, min_points=1)


class SupportSlabTest(unittest.TestCase):
    def test_the_top_face_is_the_fitted_surface_not_its_centre(self):
        """Extending the box above the surface would invent occupied space."""
        box = support_slab([0.0, 0.0], [1.0, 1.0], top_z_m=0.747, thickness_m=0.05)
        self.assertAlmostEqual(box["max_m"][2], 0.747, places=9)
        self.assertAlmostEqual(box["min_m"][2], 0.697, places=9)

    def test_a_zero_thickness_is_refused(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            support_slab([0.0, 0.0], [1.0, 1.0], 0.75, 0.0)

    def test_bad_extents_are_refused(self):
        with self.assertRaisesRegex(ValueError, "two-vectors"):
            support_slab([0.0], [1.0, 1.0], 0.75, 0.05)


class JointStateTest(unittest.TestCase):
    def test_the_same_pose_matches(self):
        matched, worst = joint_state_matches([0.1] * 6, [0.1] * 6)
        self.assertTrue(matched)
        self.assertEqual(worst, 0.0)

    def test_a_creeping_arm_is_reported_with_its_worst_joint(self):
        matched, worst = joint_state_matches([0.0] * 6, [0.0, 0.0, 0.2, 0.0, 0.0, 0.0],
                                             tolerance_rad=0.001)
        self.assertFalse(matched)
        self.assertAlmostEqual(worst, 0.2, places=9)

    def test_the_tolerance_is_inclusive(self):
        matched, _ = joint_state_matches([0.0] * 6, [0.001] * 6, tolerance_rad=0.001)
        self.assertTrue(matched)

    def test_a_shape_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, "equal length"):
            joint_state_matches([0.0] * 6, [0.0] * 5)

    def test_a_non_finite_pose_is_refused(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            joint_state_matches([0.0] * 6, [float("inf")] + [0.0] * 5)


class CompletenessTest(unittest.TestCase):
    def test_the_missing_parts_are_named(self):
        report = self_filter_completeness(["right_arm"])
        self.assertFalse(report["complete"])
        self.assertIn("chassis", report["missing"])
        self.assertIn("right_gripper", report["missing"])
        self.assertNotIn("right_arm", report["missing"])

    def test_a_full_set_is_complete(self):
        from ares_r.perception.obstacle_world import REQUIRED_SELF_FILTER_PARTS
        self.assertTrue(self_filter_completeness(REQUIRED_SELF_FILTER_PARTS)["complete"])

    def test_an_empty_declaration_is_incomplete_rather_than_assumed(self):
        report = self_filter_completeness([])
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["missing"]), 7)


class SceneObjectSpecTest(unittest.TestCase):
    def test_the_support_comes_first_and_the_residuals_follow(self):
        specs = scene_object_specs(dict(center_m=[0, 0, 1], dims_m=[1, 1, 1]),
                                   [dict(center_m=[2, 2, 2], dims_m=[.1, .1, .1],
                                         inflation_m=0.02)], "OBS_x")
        self.assertEqual(specs[0]["identifier"], "known_support_table")
        self.assertEqual(specs[0]["role"], "FIXED")
        self.assertEqual(specs[1]["identifier"], "unknown_residual_000")
        self.assertEqual(specs[1]["role"], "OBSTACLE")

    def test_every_object_carries_its_observation(self):
        specs = scene_object_specs(dict(center_m=[0, 0, 1], dims_m=[1, 1, 1]), [], "OBS_y")
        self.assertTrue(all(item["source_observation_id"] == "OBS_y" for item in specs))


if __name__ == "__main__":
    unittest.main()
