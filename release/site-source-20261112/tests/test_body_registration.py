import math
import unittest

import numpy as np

from ares_r.perception.body_registration import (
    align_vector, choose_support_tracks, level_transform, plane_metrics,
    robust_translation_yaw,
)


class BodyRegistrationTest(unittest.TestCase):
    def test_align_vector_is_a_proper_rotation(self):
        rotation = align_vector([0, 1, 0], [0, 0, 1])
        np.testing.assert_allclose(rotation @ [0, 1, 0], [0, 0, 1], atol=1e-9)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-9)
        self.assertAlmostEqual(np.linalg.det(rotation), 1.0)

    def test_level_transform_places_plane_at_zero(self):
        normal = np.array([0.0, math.sin(.7), math.cos(.7)])
        point = normal * .8
        transform = level_transform(normal, -.8)
        level = transform @ np.r_[point, 1.0]
        self.assertAlmostEqual(level[2], 0.0, places=9)
        np.testing.assert_allclose(transform[:3, :3] @ (-normal), [0, 0, 1], atol=1e-9)

    def test_plane_metrics_and_tracking_do_not_assume_first_plane(self):
        points = np.array([[0, 0, 1], [1, 0, 1], [0, 1, 1]], dtype=float)
        plane = dict(plane_metrics(points, [0, 0, 1], -1), plane_id="frame0_plane1")
        plane2 = dict(plane, plane_id="frame1_plane3", plane_d_m=-1.002)
        distractor = dict(plane, plane_id="frame0_plane0", normal_camera=[1, 0, 0], plane_d_m=-.2)
        tracks = choose_support_tracks([[distractor, plane], [plane2]])
        self.assertEqual(tracks[0]["frame_coverage"], 2)
        self.assertEqual(len(tracks[0]["members"]), 2)

    def test_translation_yaw_rejects_bad_cloud_and_ignores_distance(self):
        observations = [
            {"label": "forward", "translation_level_m": [0.02, 0.09, 0],
             "expected_body_heading_deg": 0, "fitness": .72, "rmse_m": .009,
             "rotation_drift_deg": .4, "valid_ratio": .83},
            {"label": "right", "translation_level_m": [.07, -.011, 0],
             "expected_body_heading_deg": -90, "fitness": .88, "rmse_m": .006,
             "rotation_drift_deg": .1, "valid_ratio": .82},
            {"label": "bad", "translation_level_m": [.01, .03, 0],
             "expected_body_heading_deg": 0, "fitness": .81, "rmse_m": .007,
             "rotation_drift_deg": .1, "valid_ratio": .62},
        ]
        result = robust_translation_yaw(observations, math.radians(-79.5))
        self.assertLess(abs(result["yaw_deg"] + 79.5), 3.0)
        self.assertEqual([item["label"] for item in result["rejected"]], ["bad"])

    def test_translation_yaw_requires_independent_directions(self):
        sample = {"translation_level_m": [0.02, .08, 0],
                  "expected_body_heading_deg": 0, "fitness": .8,
                  "rmse_m": .008, "rotation_drift_deg": .1, "valid_ratio": .8}
        with self.assertRaisesRegex(ValueError, "directionally independent"):
            robust_translation_yaw([dict(sample, label="a"), dict(sample, label="b")], 0)


if __name__ == "__main__":
    unittest.main()
