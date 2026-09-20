import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ares_r.perception.body_pointcloud import (build_body_cloud, fit_support_table,
                                                load_artifact, save_artifact,
                                                transform_camera_mm_to_body)
from ares_r.visualization.body_cloud_viewer import scene_spec
from ares_r.visualization.body_cloud_live import ScanSchedule


REPOSITORY = Path(__file__).resolve().parents[1]


def config():
    return json.loads((REPOSITORY / "config/system.json").read_text())


class BodyPointCloudTest(unittest.TestCase):
    def test_live_scan_scheduler_keeps_scan_and_render_independent(self):
        schedule = ScanSchedule(interval_s=2.0, auto=True)
        self.assertTrue(schedule.due(10.0))
        schedule.started(10.0)
        self.assertFalse(schedule.due(15.0))
        schedule.finished()
        self.assertFalse(schedule.due(11.9))
        self.assertTrue(schedule.due(12.0))
        schedule.started(15.0)
        self.assertEqual(schedule.actual_start_intervals_s, [5.0])
        schedule.finished(); schedule.auto = False; schedule.request_once()
        self.assertTrue(schedule.due(15.1))

    def test_invalid_unit_conversion_and_rigid_transform(self):
        points = np.array([[0, 0, 0], [np.nan, 1, 1], [1000, 0, 0]], dtype=float)
        colors = np.array([[0, 0, 0], [1, 2, 3], [255, 128, 0]], dtype=np.uint8)
        cloud = transform_camera_mm_to_body(points, colors, config())
        expected = np.asarray(config()["epic_pointcloud"]["T_body_camera"])
        np.testing.assert_allclose(cloud.points_body_m[0],
                                   expected[:3, :3] @ [1.0, 0.0, 0.0] + expected[:3, 3],
                                   atol=1e-7)
        self.assertEqual(cloud.raw_point_count, 3)
        self.assertEqual(cloud.valid_point_count, 1)
        self.assertEqual(cloud.frame, "BODY")
        self.assertEqual(cloud.unit, "m")

    def test_revision_propagation_and_regression_origin(self):
        cloud = transform_camera_mm_to_body(np.array([[0, 0, 1]], dtype=float),
                                            np.zeros((1, 3), dtype=np.uint8), config())
        section = config()["epic_pointcloud"]
        self.assertEqual(cloud.transform_revision, section["T_body_camera_revision"])
        self.assertEqual(cloud.validation_revision,
                         section["T_body_camera_validation"]["validation_revision"])
        np.testing.assert_allclose(cloud.T_body_camera[:3, 3],
                                   [0.091844968437, -0.083593394675, 1.5649768], atol=1e-9)

    def test_table_fit_and_artifact_viewer_smoke_without_hardware(self):
        rng = np.random.default_rng(4)
        xy = rng.uniform([-0.3, -0.4], [0.7, 0.4], size=(5000, 2))
        body = np.column_stack((xy, 0.75 + rng.normal(0, 0.001, len(xy))))
        cfg = config(); transform = np.asarray(cfg["epic_pointcloud"]["T_body_camera"])
        camera_m = (body - transform[:3, 3]) @ transform[:3, :3]
        cloud = transform_camera_mm_to_body(camera_m * 1000.0,
                                            np.full((len(body), 3), 127, dtype=np.uint8), cfg)
        table = fit_support_table(cloud)
        self.assertLess(abs(table["height_error_mm"]), 1.0)
        self.assertLess(table["normal_to_body_up_deg"], 0.2)
        with tempfile.TemporaryDirectory() as directory:
            manifest = save_artifact(cloud, table, Path(directory) / "artifact")
            loaded, metadata = load_artifact(manifest)
            self.assertEqual(loaded.valid_point_count, len(body))
            crosscheck = Path(directory) / "crosscheck.json"
            crosscheck.write_text(json.dumps({"board_check": {"right": {"T_body_board": np.eye(4).tolist()}}}))
            spec = scene_spec(manifest, REPOSITORY / "config/robot_world.json", crosscheck)
            self.assertEqual(set(spec["frames"]), {"BODY", "CAMERA", "LEFT_BASE", "RIGHT_BASE", "BOARD"})
            self.assertEqual(metadata["self_filter"], "NOT_RUN")
            self.assertEqual(metadata["curobo"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
