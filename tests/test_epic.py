import unittest

from ares_r.adapters.epic import EpicClient, EpicProtocolError


class EpicProtocolTest(unittest.TestCase):
    def test_parse_prototype_pose_and_convert_units(self):
        result = EpicClient._parse_pose("320,0,123.0,-45.0,300.0,180.0,0.0,-45.0", "pick", "request-1")
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.pose.x, 0.123)
        self.assertAlmostEqual(result.pose.y, -0.045)
        self.assertAlmostEqual(result.pose.z, 0.300)
        self.assertAlmostEqual(result.pose.rx, 3.141592653589793)
        self.assertAlmostEqual(result.pose.rz, -0.7853981633974483)
        self.assertEqual(result.raw_response, "320,0,123.0,-45.0,300.0,180.0,0.0,-45.0")

    def test_reject_short_response(self):
        with self.assertRaises(EpicProtocolError):
            EpicClient._parse_pose("320,0,1", "pick", "request-2")

    def test_reject_non_numeric_pose(self):
        with self.assertRaises(EpicProtocolError):
            EpicClient._parse_pose("ok,x,y,z,rx,ry,rz", "pick", "request-3")


if __name__ == "__main__":
    unittest.main()
