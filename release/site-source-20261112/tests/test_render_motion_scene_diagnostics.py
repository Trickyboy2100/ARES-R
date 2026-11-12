import importlib.util
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_motion_scene_diagnostics",
    ROOT / "scripts/render_motion_scene_diagnostics.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MotionSceneDiagnosticRendererTest(unittest.TestCase):
    def test_box_corners_have_requested_extent(self):
        points = MODULE.box_corners([1, 2, 3], np.eye(3), [.1, .2, .3])
        self.assertEqual(points.shape, (8, 3))
        np.testing.assert_allclose(points.min(axis=0), [.9, 1.8, 2.7])
        np.testing.assert_allclose(points.max(axis=0), [1.1, 2.2, 3.3])

    def test_curobo_identity_box_is_already_body_aligned(self):
        value = {"dims": [2, 4, 6], "pose": [1, 2, 3, 1, 0, 0, 0]}
        points = MODULE.curobo_cuboid_body_corners(value, np.eye(4))
        np.testing.assert_allclose(points.min(axis=0), [0, 0, 0])
        np.testing.assert_allclose(points.max(axis=0), [2, 4, 6])

    def test_plan_argument_preserves_label_and_path(self):
        label, path = MODULE.parse_plan_argument("candidate A=/tmp/planning.json")
        self.assertEqual(label, "candidate A")
        self.assertEqual(path, Path("/tmp/planning.json"))

    def test_plan_argument_requires_label_separator(self):
        with self.assertRaises(Exception):
            MODULE.parse_plan_argument("planning.json")


if __name__ == "__main__":
    unittest.main()
