import math
import unittest
from unittest.mock import patch

from ares_r.adapters.epic import EpicClient, EpicProtocolError


#: Captured from the site camera on 2026-09-16. Real envelope, real numbers.
REAL_RESPONSE = ("320,0,1,1,1,1,1,0,0,0,0,0,-792.70367,-222.73137,-180.46941,"
                 "-87.13487,179.04689,136.74011")


def epic_config():
    profile = dict(arm="left", purpose="pick", command="320,1,1,1,1,0", camera_id=1,
                   space_id=1, object_id=1, output_frame="left_arm_base_candidate",
                   translation_unit="mm", rotation_unit="deg", orientation_convention="UNKNOWN",
                   approach_axis="UNKNOWN", tool_revision="UNCOMMISSIONED",
                   calibration_revision="UNCOMMISSIONED", state="UNCOMMISSIONED")
    place = dict(profile, purpose="place", command="320,1,2,1,1,0", object_id=2)
    return {"host": "127.0.0.1", "port": 5700, "timeout_s": 0.1,
            "default_pick_profile": "left_pick", "default_place_profile": "left_place",
            "task_profiles": {"left_pick": profile, "left_place": place}}


class EpicProtocolTest(unittest.TestCase):
    def setUp(self):
        self.client = EpicClient(epic_config())
        self.profile = self.client.profiles["left_pick"]

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

    def test_parse_real_response_preserves_candidates_and_meta(self):
        result = self.client._parse_pose(REAL_RESPONSE, "pick", "request-1", self.profile)
        self.assertTrue(result.success)
        self.assertEqual(result.pose.frame_id, "left_arm_base_candidate")
        self.assertAlmostEqual(result.pose.x, -0.79270367)
        self.assertAlmostEqual(result.pose.y, -0.22273137)
        self.assertAlmostEqual(result.pose.z, -0.18046941)
        self.assertAlmostEqual(result.pose.rx, math.radians(-87.13487))
        self.assertAlmostEqual(result.pose.rz, math.radians(136.74011))
        self.assertEqual([candidate for candidate in result.candidates], [result.pose])
        self.assertEqual(result.meta["space_id"], 1)
        self.assertEqual(result.meta["object_id"], 1)
        self.assertEqual(result.meta["grasp_index"], 0)
        self.assertEqual(result.meta["total_grasp_count"], 1)
        self.assertEqual(result.meta["pose_type"], "cartesian")
        self.assertFalse(result.meta["pose_frame_verified"])

    def test_every_grasp_candidate_survives_parsing(self):
        raw = "320,0,2,1,2,1,1,0,0,0,0,0,100,200,300,0,0,0,110,210,310,0,0,0"
        result = self.client._parse_pose(raw, "pick", "request-candidates", self.profile)
        self.assertEqual(len(result.candidates), 2)
        self.assertAlmostEqual(result.candidates[0].x, 0.100)
        self.assertAlmostEqual(result.candidates[1].x, 0.110)
        self.assertEqual(result.meta["total_grasp_count"], 2)

    def test_reject_short_response(self):
        with self.assertRaises(EpicProtocolError) as context:
            self.client._parse_pose("320,0,1", "pick", "request-2", self.profile)
        self.assertIn("12-field header", str(context.exception))

    def test_reject_non_numeric_pose(self):
        with self.assertRaises(EpicProtocolError):
            self.client._parse_pose("ok,x,y,z,rx,ry,rz", "pick", "request-3", self.profile)

    def test_reject_joint_path_points(self):
        raw = "320,1,1,1,1,1,1,0,0,0,0,0,0.1,0.2,0.3,0.4,0.5,0.6"
        with self.assertRaises(EpicProtocolError) as context:
            self.client._parse_pose(raw, "pick", "request-joint", self.profile)
        self.assertIn("joint path points", str(context.exception))

    def test_unknown_source_units_are_refused(self):
        broken = epic_config()
        broken["task_profiles"]["left_pick"]["translation_unit"] = "metres"
        with self.assertRaises(ValueError):
            EpicClient(broken)

    @patch.object(EpicClient, "_exchange", return_value="000,3020")
    def test_protocol_error_does_not_mark_reachable_camera_offline(self, exchange):
        result = self.client.detect_pick()
        self.assertFalse(result.success)
        self.assertEqual(result.raw_response, "000,3020")
        self.assertTrue(self.client.state().ready)

    @patch.object(EpicClient, "_exchange", return_value="000,3020")
    def test_documented_error_code_becomes_a_sentence(self, exchange):
        result = self.client.detect_pick()
        self.assertIn("未检测出结果", result.error)

    def test_acknowledgement_is_not_reported_as_a_malformed_result(self):
        with self.assertRaises(EpicProtocolError) as context:
            self.client._parse_pose("130", "pick", "request-ack", self.profile)
        message = str(context.exception)
        self.assertIn("130", message)
        self.assertIn("切换空间下抓取物", message)
        self.assertIn("no grasp poses", message)

    def test_undocumented_short_frame_still_reports_the_header_rule(self):
        with self.assertRaises(EpicProtocolError) as context:
            self.client._parse_pose("999,1,2", "pick", "request-short", self.profile)
        self.assertIn("12-field header", str(context.exception))

    @patch.object(EpicClient, "_exchange", return_value="130")
    def test_switch_space_accepts_the_documented_acknowledgement(self, exchange):
        acknowledgement = self.client.switch_space(2, 1)
        self.assertEqual(acknowledgement.command_code, 130)
        self.assertEqual(acknowledgement.description, "切换空间下抓取物")
        exchange.assert_called_once_with("130,2,1")

    @patch.object(EpicClient, "_exchange", return_value="000,3007")
    def test_switch_space_surfaces_a_failure_frame(self, exchange):
        with self.assertRaises(EpicProtocolError) as context:
            self.client.switch_space(9, 1)
        self.assertIn("3007", str(context.exception))

    @patch.object(EpicClient, "_exchange", return_value="320,0,1,1,1,2,1,0,0,0,0,0,1,2,3,0,0,0")
    def test_switch_space_rejects_a_detection_frame(self, exchange):
        with self.assertRaises(EpicProtocolError):
            self.client.switch_space(2, 1)

    def test_switch_space_rejects_negative_ids(self):
        with self.assertRaises(ValueError):
            self.client.switch_space(-1, 1)


if __name__ == "__main__":
    unittest.main()
