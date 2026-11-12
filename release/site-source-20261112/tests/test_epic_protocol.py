import unittest

from ares_r.adapters.epic_protocol import parse_5700_response


class Epic5700ProtocolTest(unittest.TestCase):
    def test_parse_joint_path(self):
        raw = "220,1,2,1,3,1,2,0,4,2006,0,0,0.1,0.2,0.3,0.4,0.5,0.6,0.2,0.3,0.4,0.5,0.6,0.7"
        result = parse_5700_response(raw)
        self.assertEqual(result.pose_type, "joint")
        self.assertEqual(result.pose_count, 2)
        self.assertEqual(result.status, 2006)
        self.assertEqual(result.poses[1][-1], 0.7)

    def test_error_response(self):
        with self.assertRaisesRegex(ValueError, "3020"):
            parse_5700_response("000,3020")

    def test_reject_bad_payload_shape(self):
        with self.assertRaisesRegex(ValueError, "divided"):
            parse_5700_response("220,1,2,1,3,1,2,0,4,2006,0,0,1,2,3,4,5,6,7")


if __name__ == "__main__":
    unittest.main()
