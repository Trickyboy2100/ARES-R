import unittest
from types import SimpleNamespace

import numpy as np

from ares_r.perception.support_decomposition import (
    DecompositionProfile, decompose_support_objects, detect_support_levels,
    refine_robot_adjacent_primitives)


class SupportDecompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import open3d
        except ImportError:
            raise unittest.SkipTest("Open3D scene tests run in the calib environment")

    def setUp(self):
        x, y = np.meshgrid(np.linspace(.4, .8, 45), np.linspace(-.3, .3, 45))
        support = np.column_stack((x.ravel(), y.ravel(), np.full(x.size, .85)))
        bx, by, bz = np.meshgrid(np.linspace(.57, .65, 12),
                                 np.linspace(-.04, .04, 12),
                                 np.linspace(.88, 1.08, 20))
        box = np.column_stack((bx.ravel(), by.ravel(), bz.ravel()))
        self.points = np.vstack((support, box))

    def test_detects_support_and_protrusion(self):
        levels = detect_support_levels(self.points)
        self.assertTrue(any(abs(item["z_m"] - .85) < .01 for item in levels))
        old = [{"min_m": self.points.min(0).tolist(), "max_m": self.points.max(0).tolist()}]
        result = decompose_support_objects(self.points, old, DecompositionProfile())
        semantics = {item["semantic"] for item in result["primitives"]}
        self.assertIn("SUPPORT_SURFACE", semantics)
        self.assertIn("PROTRUDING_OBSTACLE", semantics)
        self.assertGreater(result["multi_primitive_count"], 1)
        self.assertEqual(result["observed_point_accounting_ratio"],1.0)
        self.assertLess(result["multi_primitive_occupied_volume_m3"],
                        result["old_single_aabb_occupied_volume_m3"])

    def test_robot_adjacent_refinement_splits_without_deleting_points(self):
        points=np.asarray([[-.05,0,0],[.05,0,0]])
        primitive={"primitive_id":"bridge","semantic":"UNKNOWN_OCCUPIED",
                   "source_cluster":"test","point_count":2,"center_m":[0,0,0],
                   "dims_m":[.1,.004,.004],"inflation_m":.01,
                   "observed_bounds_m":[[-.05,0,0],[.05,0,0]]}
        report={"primitives":[primitive],"old_single_aabb_occupied_volume_m3":.001,
                "multi_primitive_count":1,"multi_primitive_occupied_volume_m3":.001,
                "occupied_volume_ratio":1.0}
        owned=SimpleNamespace(spheres=(SimpleNamespace(center_body_m=(0,0,0),radius_m=.02),))
        refined=refine_robot_adjacent_primitives(points,report,owned,cell_m=.015)
        self.assertEqual(sum(item["point_count"] for item in refined["primitives"]),2)
        self.assertEqual(len(refined["primitives"]),2)


if __name__ == "__main__":
    unittest.main()
