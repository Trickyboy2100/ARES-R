import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ares_r.motion.feedback_audit import run_audit, status_connections


class FeedbackAuditTest(unittest.TestCase):
    def test_cpp_auditor_only_uses_public_read_and_session_apis(self):
        import re
        source = (Path(__file__).resolve().parents[1]/"scripts/audit_jaka_v222_feedback.cpp").read_text()
        calls=set(re.findall(r"robot\.([a-zA-Z_]+)\(",source))
        self.assertEqual(calls, {"login_in","login_out","get_sdk_version","get_robot_status",
            "get_actual_joint_position","get_joint_position","get_robot_status_simple",
            "get_motion_status","get_tool_id","get_user_frame_id"})
        self.assertNotIn("192.168.99.100",source)

    def test_socket_filter_only_right_status_peer(self):
        rows = "ESTAB 0 0 192.168.99.32:111 192.168.99.101:10004 users:pid1\n" \
               "ESTAB 0 0 192.168.99.32:112 192.168.99.100:10004 users:pid2\n" \
               "TIME-WAIT 0 0 192.168.99.32:113 192.168.99.101:10004\n"
        with patch("ares_r.motion.feedback_audit.subprocess.run",return_value=Mock(stdout=rows)):
            self.assertEqual(len(status_connections()),1)

    def test_competing_connection_blocks_before_reader(self):
        with tempfile.TemporaryDirectory() as root:
            factory = Mock()
            path = run_audit(root,5,reader_factory=factory,connection_probe=lambda:["occupied"])
            self.assertEqual(json.loads(path.read_text())["result"],"BLOCKED")
            factory.assert_not_called()

    def test_missing_inspection_blocks_before_reader(self):
        with tempfile.TemporaryDirectory() as root:
            factory = Mock()
            path = run_audit(root,5,reader_factory=factory,connection_probe=Mock(side_effect=FileNotFoundError("ss")))
            self.assertEqual(json.loads(path.read_text())["frames"],0)
            factory.assert_not_called()

    def test_soak_and_disconnect_no_reconnect(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as root:
                tick=[0.0]
                def sleep(dt): tick[0]+=dt
                class Reader:
                    reads=0
                    closed=False
                    def __enter__(self): return self
                    def __exit__(self,*args): self.closed=True
                    def read(self):
                        self.reads+=1
                        if fail and self.reads==4: raise RuntimeError("connection closed")
                        return dict(tool_id=2,user_frame_id=0,roundtrip_s=.01,
                                    joint_actual_position_rad=[0.0]*6)
                reader=Reader()
                factory=Mock(return_value=reader)
                path=run_audit(root,5,reader_factory=factory,connection_probe=lambda:[],
                               clock=lambda:tick[0],sleeper=sleep,progress=lambda s:None)
                report=json.loads(path.read_text())
                self.assertEqual(report["result"],"FAILED" if fail else "READ_ONLY_SOAK_PASSED")
                self.assertTrue(reader.closed)
                factory.assert_called_once_with("192.168.99.101")

    def test_invalid_durations_never_connect(self):
        for value in (0,601,float("nan")):
            with self.assertRaises(ValueError): run_audit("unused",value)
