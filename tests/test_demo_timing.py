import math
import unittest
from ares_r.motion.demo_timing import sample_count_at_scale,MAX_JOINT_ACCEL_DEG_S2


class TimingTest(unittest.TestCase):
    def test_3x_with_unchanged_80ms_cadence(self):
        count,old=sample_count_at_scale(513,.08)
        self.assertEqual(count,172)
        self.assertAlmostEqual(old,40.96)
        self.assertAlmostEqual((count-1)*.08,13.68)
        self.assertGreaterEqual((count-1)*.08,old/3)
        self.assertLess((count-1)*.08,old/3+.08)

    def test_preserve_site_acceleration_and_validate_inputs(self):
        self.assertAlmostEqual(math.radians(MAX_JOINT_ACCEL_DEG_S2),.2)
        for count,dt in ((1,.08),(10,0),(10,float("nan"))):
            with self.assertRaises(ValueError):sample_count_at_scale(count,dt)
        self.assertEqual(sample_count_at_scale(513,.08,2)[0],257)
        with self.assertRaises(ValueError):sample_count_at_scale(513,.08,1)
