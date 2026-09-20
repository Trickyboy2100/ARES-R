import numpy as np
import unittest

from ares_r.perception.body_camera import (ORTHONORMAL_TOLERANCE, body_camera_verdict,
                                           camera_origin_in_body, compose_body_camera,
                                           dominant_plane, ground_height_m,
                                           support_tilt_deg)

YAW_45 = np.array([[np.cos(np.pi / 4), -np.sin(np.pi / 4), 0.0],
                   [np.sin(np.pi / 4), np.cos(np.pi / 4), 0.0],
                   [0.0, 0.0, 1.0]])


def _base(yaw_rad=np.pi / 4, xyz=(0.0, -0.2, 1.2)):
    matrix = np.eye(4)
    c, s = np.cos(yaw_rad), np.sin(yaw_rad)
    matrix[:3, :3] = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    matrix[:3, 3] = xyz
    return matrix


def _camera(truncated=True):
    """A plausible fixed-camera pose, optionally rounded like the Epic UI.

    The rotation is built from exact axis rotations so the untruncated form is
    orthonormal to machine precision; rounding to four decimals reproduces what
    copying the displayed matrix actually gives.
    """
    r, p, y = np.deg2rad([-50.0, 140.0, -60.0])
    rz = np.array([[np.cos(y), -np.sin(y), 0.0], [np.sin(y), np.cos(y), 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[np.cos(p), 0.0, np.sin(p)], [0.0, 1.0, 0.0], [-np.sin(p), 0.0, np.cos(p)]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, np.cos(r), -np.sin(r)], [0.0, np.sin(r), np.cos(r)]])
    matrix = np.eye(4)
    matrix[:3, :3] = rz @ ry @ rx
    matrix[:3, 3] = [0.1472561, 0.0173677, 0.3649768]
    if truncated:
        matrix[:3, :3] = np.round(matrix[:3, :3], 4)
    return matrix


class ComposeTest(unittest.TestCase):
    def test_composition_multiplies_in_the_documented_order(self):
        # An exactly orthonormal camera so the product is compared, not a repair.
        base, camera = _base(), _camera(truncated=False)
        composed = compose_body_camera(base, camera)
        self.assertTrue(np.allclose(composed["transform"], base @ camera, atol=1e-12))
        self.assertAlmostEqual(composed["camera_orthonormalisation"], 0.0, places=9)

    def test_the_camera_origin_lands_where_the_product_puts_it(self):
        composed = compose_body_camera(_base(), _camera())
        origin = camera_origin_in_body(composed["transform"])
        self.assertTrue(np.allclose(origin, composed["transform"][:3, 3]))

    def test_display_rounding_is_repaired_and_reported(self):
        composed = compose_body_camera(_base(), _camera(truncated=True))
        self.assertGreater(composed["camera_orthonormalisation"], 0.0)
        self.assertLess(composed["camera_orthonormalisation"], ORTHONORMAL_TOLERANCE)
        rotation = composed["transform"][:3, :3]
        self.assertTrue(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12))
        self.assertAlmostEqual(float(np.linalg.det(rotation)), 1.0, places=12)

    def test_a_mirrored_rotation_is_refused(self):
        camera = _camera(truncated=False)
        camera[0, :3] *= -1.0
        with self.assertRaisesRegex(ValueError, "proper rotation"):
            compose_body_camera(_base(), camera)

    def test_a_copied_wrong_rotation_is_refused(self):
        camera = _camera(truncated=False)
        camera[0, 0] += 0.2
        with self.assertRaisesRegex(ValueError, "transcription tolerance"):
            compose_body_camera(_base(), camera)

    def test_a_bad_bottom_row_is_refused(self):
        camera = _camera(truncated=False)
        camera[3, 3] = 2.0
        with self.assertRaisesRegex(ValueError, "bottom row"):
            compose_body_camera(_base(), camera)

    def test_a_non_finite_matrix_is_refused(self):
        camera = _camera(truncated=False)
        camera[1, 2] = np.nan
        with self.assertRaisesRegex(ValueError, "finite 4x4"):
            compose_body_camera(_base(), camera)


class SupportTiltTest(unittest.TestCase):
    def test_a_level_surface_stays_level(self):
        identity = np.eye(4)
        self.assertAlmostEqual(support_tilt_deg(identity, [0.0, 0.0, -1.0]), 0.0, places=9)

    def test_the_surface_normal_sign_does_not_matter(self):
        identity = np.eye(4)
        self.assertAlmostEqual(support_tilt_deg(identity, [0.0, 0.0, 1.0]),
                               support_tilt_deg(identity, [0.0, 0.0, -1.0]), places=12)

    def test_yaw_about_the_vertical_cannot_change_the_tilt(self):
        """This is why the tilt check constrains only two degrees of freedom."""
        camera = _camera(truncated=False)
        surface = [0.1, 0.2, -0.97]
        plain = support_tilt_deg(compose_body_camera(_base(), camera)["transform"], surface)
        spun = compose_body_camera(_base(np.pi / 4 + 0.4), camera)["transform"]
        self.assertAlmostEqual(plain, support_tilt_deg(spun, surface), places=6)

    def test_a_vertical_surface_is_ninety_degrees(self):
        self.assertAlmostEqual(support_tilt_deg(np.eye(4), [1.0, 0.0, 0.0]), 90.0, places=9)

    def test_a_zero_normal_is_refused(self):
        with self.assertRaisesRegex(ValueError, "zero normal"):
            support_tilt_deg(np.eye(4), [0.0, 0.0, 0.0])


class DominantPlaneTest(unittest.TestCase):
    def test_a_synthetic_plane_is_recovered(self):
        rng = np.random.default_rng(3)
        flat = np.column_stack([rng.uniform(-1, 1, 4000), rng.uniform(-1, 1, 4000),
                                np.full(4000, 1.5) + rng.normal(0, 0.002, 4000)])
        clutter = rng.uniform(-1, 1, (400, 3))
        fit = dominant_plane(np.vstack([flat, clutter]), threshold_m=0.01, seed=1)
        self.assertAlmostEqual(abs(float(fit["normal"][2])), 1.0, places=2)
        self.assertGreater(fit["inlier_ratio"], 0.85)

    def test_the_normal_points_back_toward_the_sensor(self):
        rng = np.random.default_rng(5)
        plane = np.column_stack([rng.uniform(-1, 1, 2000), rng.uniform(-1, 1, 2000),
                                 np.full(2000, 2.0)])
        fit = dominant_plane(plane, threshold_m=0.01, seed=2)
        # The sensor sits at the origin, below the plane at z = 2.
        self.assertLess(float(fit["normal"] @ fit["centre"]), 0.0)

    def test_too_few_points_are_refused(self):
        with self.assertRaisesRegex(ValueError, "at least three"):
            dominant_plane(np.zeros((2, 3)))

    def test_non_finite_points_are_refused(self):
        points = np.zeros((4, 3))
        points[0, 1] = np.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            dominant_plane(points)


class GroundHeightTest(unittest.TestCase):
    def test_the_band_median_is_reported(self):
        points = np.column_stack([np.zeros(900), np.zeros(900),
                                  np.concatenate([np.full(600, -0.008),
                                                  np.full(300, 1.2)])])
        ground = ground_height_m(points, half_width_m=0.05)
        self.assertEqual(ground["point_count"], 600)
        self.assertAlmostEqual(ground["median_z_m"], -0.008, places=9)
        self.assertAlmostEqual(ground["fraction"], 600 / 900, places=9)

    def test_an_empty_band_is_reported_as_such_not_as_agreement(self):
        points = np.full((100, 3), 1.5)
        ground = ground_height_m(points, half_width_m=0.05)
        self.assertEqual(ground["point_count"], 0)
        self.assertIsNone(ground["median_z_m"])

    def test_no_points_at_all_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no points"):
            ground_height_m(np.zeros((0, 3)))

    def test_a_wrong_shape_is_refused(self):
        with self.assertRaisesRegex(ValueError, r"\(n, 3\)"):
            ground_height_m(np.zeros((5, 2)))


class VerdictTest(unittest.TestCase):
    GOOD_GROUND = dict(point_count=40000, median_z_m=-0.0074, spread_m=0.015, fraction=0.045)

    def test_a_good_commission_passes_and_says_what_it_checked(self):
        text = body_camera_verdict(0.42, self.GOOD_GROUND, 1.0, 0.03, 500)
        self.assertTrue(text.startswith("通过"))
        self.assertIn("0.420", text)
        self.assertIn("-0.0074", text)

    def test_a_tilted_surface_is_refused(self):
        text = body_camera_verdict(35.0, self.GOOD_GROUND, 1.0, 0.03, 500)
        self.assertTrue(text.startswith("拒绝"))
        self.assertIn("旋转部分不成立", text)

    def test_a_ground_offset_is_refused(self):
        ground = dict(self.GOOD_GROUND, median_z_m=0.277)
        text = body_camera_verdict(0.4, ground, 1.0, 0.03, 500)
        self.assertTrue(text.startswith("拒绝"))
        self.assertIn("z 平移不成立", text)

    def test_too_few_ground_points_is_refused(self):
        ground = dict(self.GOOD_GROUND, point_count=12)
        text = body_camera_verdict(0.4, ground, 1.0, 0.03, 500)
        self.assertTrue(text.startswith("拒绝"))
        self.assertIn("不足以判定", text)

    def test_a_missing_band_is_refused_rather_than_treated_as_zero(self):
        ground = dict(point_count=600, median_z_m=None, spread_m=None)
        text = body_camera_verdict(0.4, ground, 1.0, 0.03, 500)
        self.assertTrue(text.startswith("拒绝"))


if __name__ == "__main__":
    unittest.main()
