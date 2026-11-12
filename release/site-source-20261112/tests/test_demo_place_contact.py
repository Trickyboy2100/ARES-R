import unittest
import numpy as np
from ares_r.manipulation.demo_place_contact import outside_parts

class PlaceContactTests(unittest.TestCase):
    def test_outside_geometry_retained_and_only_contact_intersection_removed(self):
        lo=np.array([-1.]*3);hi=np.array([1.]*3);a=np.array([-.2]*3);b=-a
        parts=outside_parts(lo,hi,a,b)
        self.assertAlmostEqual(sum(float(np.prod(y-x)) for x,y in parts),8-.4**3)
        rng=np.random.RandomState(10)
        for point in rng.uniform(-.999,.999,(1000,3)):
            kept=any(np.all(point>=x)&np.all(point<=y) for x,y in parts)
            self.assertEqual(kept,not bool(np.all(point>=a)&np.all(point<=b)))
    def test_no_intersection_preserves_original_box(self):
        parts=outside_parts([0,0,0],[1,1,1],[2,2,2],[3,3,3])
        self.assertEqual(len(parts),1);np.testing.assert_array_equal(parts[0][1],[1,1,1])
