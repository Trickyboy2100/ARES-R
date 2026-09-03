import unittest
from unittest.mock import patch

from ares_r.adapters.epic import EpicClient, EpicProtocolError


class EpicProtocolTest(unittest.TestCase):
    def setUp(self):
        self.client = EpicClient({"host": "127.0.0.1", "port": 5700, "timeout_s": 0.1, "pick_command": "pick", "place_command": "place"})

    def test_initial_state_is_not_checked(self):
        state = self.client.state()
        self.assertFalse(state.ready)
        self.assertIn("not checked", state.detail)

    @patch("ares_r.adapters.epic.socket.create_connection")
    def test_probe_reports_reachable_without_detection(self, connection):
        connection.return_value.settimeout.return_value = None
        state = self.client.probe()
        self.assertTrue(state.ready)
        self.assertIn("reachable", state.detail)
        connection.assert_called_once_with(("127.0.0.1", 5700), 0.1)

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

    @patch.object(EpicClient, "_exchange", return_value="000,3020")
    def test_protocol_error_does_not_mark_reachable_camera_offline(self, exchange):
        result = self.client.detect_pick()
        self.assertFalse(result.success)
        self.assertEqual(result.raw_response, "000,3020")
        self.assertTrue(self.client.state().ready)


if __name__ == "__main__":
    unittest.main()
