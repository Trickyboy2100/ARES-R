import json
import math
import unittest
from unittest.mock import patch
import zlib

from ares_r.adapters.jaka_actual import JakaActualReader, parse_actual_status


def frame(**changes):
    data = dict(len=0, errcode="0x0", emergency_stop=0, protective_stop=0,
                on_soft_limit=0, drag_status=False, powered_on=1, enabled=True,
                joint_actual_position=[180.0]*6, joint_position=[0.0]*6,
                current_tool_id=2, current_user_id=0)
    data.update(changes)
    for _ in range(4):
        body = json.dumps(data).encode()
        data["len"] = len(body)
    return json.dumps(data).encode()


class FakeSocket:
    def __init__(self, blocks): self.blocks = list(blocks); self.sent = []
    def settimeout(self, value): pass
    def setsockopt(self, *args): pass
    def sendall(self, value): self.sent.append(value)
    def recv(self, count): return self.blocks.pop(0) if self.blocks else b""
    def close(self): pass


class ActualTelemetryTest(unittest.TestCase):
    def test_actual_not_reported_position_and_degrees_to_radians(self):
        data = parse_actual_status(frame())
        self.assertEqual(data["joint_actual_position_rad"], [math.pi]*6)
        self.assertEqual(data["joint_position_rad"], [0.0]*6)

    def test_fragmented_compressed_response(self):
        wire = zlib.compress(frame())
        sock = FakeSocket([wire[:3], wire[3:21], wire[21:]])
        with patch("ares_r.adapters.jaka_actual.socket.create_connection", return_value=sock):
            with JakaActualReader("192.168.99.101") as reader:
                data = reader.read()
        self.assertEqual(data["tool_id"], 2)
        self.assertEqual(sock.sent, [b'{"cmdName":"data_request"}\n'])

    def test_safety_fault_and_nonfinite_feedback_blocked(self):
        for change in (dict(protective_stop=1), dict(errcode="0x1"), dict(enabled=False),
                       dict(joint_actual_position=[float("nan")]*6)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                parse_actual_status(frame(**change))

    def test_left_connection_never_opened(self):
        with patch("ares_r.adapters.jaka_actual.socket.create_connection") as connect:
            with self.assertRaises(RuntimeError): JakaActualReader("192.168.99.100")
            connect.assert_not_called()

    def test_truncated_and_unsolicited_frames_blocked(self):
        wire = zlib.compress(frame())
        for blocks in ([wire[:10]], [wire+wire]):
            sock = FakeSocket(blocks)
            with patch("ares_r.adapters.jaka_actual.socket.create_connection", return_value=sock):
                with JakaActualReader("192.168.99.101") as reader, self.assertRaises(RuntimeError):
                    reader.read()
