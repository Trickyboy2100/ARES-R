import unittest
import numpy as np
from ares_r.motion.production_scene_worker import bounded_validation_knots,grid_spheres,path_metrics


class ProductionGeometryTest(unittest.TestCase):
    def test_grid_spheres_cover_box_corners(self):
        box={"center_m":[0,0,0],"half_extents_m":[.1,.04,.03]}
        spheres=grid_spheres(box,.06)
        self.assertGreater(len(spheres),1)
        # The extreme corner belongs to at least one circumscribed cell sphere.
        corner=[.1,.04,.03]
        self.assertTrue(any(sum((a-b)**2 for a,b in zip(corner,s["center"]))**.5<=s["radius"]+1e-12 for s in spheres))

    def test_straight_path_metrics(self):
        value=path_metrics([[0,0,0],[.5,0,0],[1,0,0]])
        self.assertAlmostEqual(value["length_ratio"],1.)
        self.assertAlmostEqual(value["max_straight_line_deviation_m"],0.)

    def test_finer_grid_reduces_conservative_sphere_overhang(self):
        box={"center_m":[0,0,0],"half_extents_m":[.1,.04,.03]}
        coarse=grid_spheres(box,.060)
        fine=grid_spheres(box,.035)
        self.assertGreater(len(fine),len(coarse))
        self.assertLess(fine[0]["radius"],coarse[0]["radius"])

    def test_bounded_validation_knots_remove_only_time_redundancy(self):
        rows=np.linspace(np.zeros(6),np.full(6,.01),101)
        knots=bounded_validation_knots(rows,.002)
        self.assertLess(len(knots),len(rows))
        self.assertTrue(np.array_equal(knots[0],rows[0]))
        self.assertTrue(np.array_equal(knots[-1],rows[-1]))


if __name__=="__main__":unittest.main()
