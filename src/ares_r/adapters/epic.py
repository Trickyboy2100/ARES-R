"""Epic Pro TCP adapter with bounded reads and explicit parsing."""

import socket
import time
import uuid
from typing import Dict, List, Optional
from ..interfaces import Perception
from ..models import DetectionResult, DeviceState, Pose


class EpicProtocolError(RuntimeError):
    pass


class EpicClient(Perception):
    def __init__(self, config: Dict[str, object]) -> None:
        self.host = str(config["host"])
        self.port = int(config["port"])
        self.timeout = float(config.get("timeout_s", 8.0))
        self.pick_command = str(config["pick_command"])
        self.place_command = str(config["place_command"])
        self.terminator = str(config.get("response_terminator", ""))
        self.sock = None  # type: socket.socket
        self._last_probe = None  # type: Optional[bool]
        self._last_error = ""

    def _connect(self) -> None:
        self.close()
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.sock.settimeout(self.timeout)
            self._last_probe = True
            self._last_error = ""
        except Exception as exc:
            self._last_probe = False
            self._last_error = str(exc)
            raise

    def _exchange(self, command: str) -> str:
        self._connect()
        assert self.sock is not None
        self.sock.sendall(command.encode("utf-8"))
        chunks: List[bytes] = []
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            data = b"".join(chunks)
            if self.terminator and data.endswith(self.terminator.encode("utf-8")):
                break
            # Until the formal protocol is confirmed, a short packet is treated as complete.
            if not self.terminator and len(chunk) < 4096:
                break
        raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
        if not raw:
            raise EpicProtocolError("empty Epic response")
        return raw

    @staticmethod
    def _parse_pose(raw: str, kind: str, request_id: str) -> DetectionResult:
        fields = [item.strip() for item in raw.split(",")]
        if len(fields) < 6:
            raise EpicProtocolError("expected at least 6 comma-separated fields")
        try:
            values = [float(value) for value in fields[-6:]]
        except ValueError as exc:
            raise EpicProtocolError("pose contains non-numeric fields: %s" % exc)
        # Epic prototype returns millimetres and degrees; convert at the boundary.
        deg = 3.141592653589793 / 180.0
        pose = Pose("left_arm_base", values[0] / 1000.0, values[1] / 1000.0, values[2] / 1000.0, values[3] * deg, values[4] * deg, values[5] * deg)
        return DetectionResult(True, request_id, kind, pose=pose, raw_response=raw)

    def _detect(self, command: str, kind: str) -> DetectionResult:
        request_id = str(uuid.uuid4())
        raw = ""
        try:
            raw = self._exchange(command)
            return self._parse_pose(raw, kind, request_id)
        except Exception as exc:
            # A received protocol/error frame proves the endpoint is reachable.
            self._last_probe = True if raw else False
            self._last_error = str(exc)
            return DetectionResult(False, request_id, kind, raw_response=raw, error=str(exc))

    def detect_pick(self) -> DetectionResult:
        return self._detect(self.pick_command, "pick")

    def detect_place(self, dock_id: int) -> DetectionResult:
        return self._detect(self.place_command, "place:%d" % dock_id)

    def state(self) -> DeviceState:
        endpoint = "%s:%d" % (self.host, self.port)
        if self._last_probe is None:
            return DeviceState(False, False, "not checked; " + endpoint)
        if self._last_probe:
            return DeviceState(True, True, "reachable; " + endpoint)
        return DeviceState(False, False, "unreachable; %s; %s" % (endpoint, self._last_error))

    def probe(self) -> DeviceState:
        try:
            self._connect()
        except Exception:
            return self.state()
        finally:
            self.close()
        return self.state()

    def close(self) -> None:
        if self.sock is not None:
            try: self.sock.close()
            finally: self.sock = None
