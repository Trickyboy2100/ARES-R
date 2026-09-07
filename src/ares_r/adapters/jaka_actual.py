"""Right-only actual joint telemetry via the site's compressed status endpoint.

Protocol audited from SDK V2.1.5 send_command_to_10004_port/data_request.
Only a fixed read request is exposed; there is no motion or arbitrary RPC API.
"""

import json
import math
import socket
import time
import zlib

MAX_FRAME = 131072


def parse_actual_status(body):
    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError("invalid actual status object")
    if abs(int(data["len"]) - len(body)) > 2:
        raise RuntimeError("actual status length mismatch")
    error = data["errcode"]
    error = int(error, 0) if isinstance(error, str) else int(error)
    if error or any(data[k] for k in ("emergency_stop", "protective_stop", "on_soft_limit", "drag_status")):
        raise RuntimeError("actual telemetry reports controller safety stop/error")
    if not data["powered_on"] or not data["enabled"]:
        raise RuntimeError("actual telemetry reports power/enable off")
    vectors = {}
    for key in ("joint_actual_position", "joint_position"):
        values = [float(v) for v in data[key]]
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise RuntimeError("invalid joint telemetry")
        vectors[key + "_rad"] = [math.radians(v) for v in values]
    vectors["tool_id"] = int(data["current_tool_id"])
    vectors["user_frame_id"] = int(data["current_user_id"])
    return vectors


class JakaActualReader:
    def __init__(self, ip):
        if ip != "192.168.99.101":
            raise RuntimeError("actual telemetry demo is restricted to right controller .101")
        self.socket = socket.create_connection((ip, 10004), timeout=1.0)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.first_request = True

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self): self.socket.close()

    def read(self):
        # Connection warm-up is allowed only before arming; subsequent frames
        # must meet the strict servo monitoring deadline.
        budget = 1.0 if self.first_request else 0.04
        self.socket.settimeout(budget if self.first_request else 0.03)
        started = time.monotonic()
        self.socket.sendall(b'{"cmdName":"data_request"}\n')
        decoder = zlib.decompressobj()
        body = b""
        wire_size = 0
        while not decoder.eof:
            if time.monotonic() - started > budget:
                raise RuntimeError("actual telemetry deadline exceeded")
            block = self.socket.recv(16384)
            if not block:
                raise RuntimeError("actual telemetry connection closed")
            wire_size += len(block)
            body += decoder.decompress(block, MAX_FRAME + 1 - len(body))
            if wire_size > MAX_FRAME or len(body) > MAX_FRAME:
                raise RuntimeError("actual telemetry frame too large")
        if decoder.unused_data:
            raise RuntimeError("unexpected unsolicited telemetry frame")
        result = parse_actual_status(body)
        result["received_monotonic"] = time.monotonic()
        result["roundtrip_s"] = result["received_monotonic"] - started
        if result["roundtrip_s"] > budget:
            raise RuntimeError("actual telemetry response too old")
        self.first_request = False
        return result
