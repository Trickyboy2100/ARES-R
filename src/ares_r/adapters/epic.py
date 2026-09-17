"""Epic Pro TCP adapter with bounded reads and explicit parsing."""

import math
import socket
import time
import uuid
from typing import Dict, List, Optional
from ..interfaces import Perception
from ..models import DetectionResult, DeviceState, Pose
from .epic_protocol import EpicAcknowledgement, parse_5700_response, parse_acknowledgement


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
        # The camera reports its own frame; ARES-R never renames it silently.
        # ``pose_frame_verified`` is what a motion planner must gate on, because
        # a plausible-looking millimetre triple is not evidence that it is in the
        # arm base frame the planner assumes.
        self.pose_frame = str(config.get("pose_frame", "left_arm_base"))
        self.pose_frame_verified = bool(config.get("pose_frame_verified", False))
        self.translation_unit = str(config.get("pose_translation_unit", "mm"))
        self.rotation_unit = str(config.get("pose_rotation_unit", "deg"))
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

    def _as_pose(self, values) -> Pose:
        """Convert one documented pose row into SI units in the declared frame."""
        if self.translation_unit != "mm" or self.rotation_unit != "deg":
            raise EpicProtocolError(
                "the 5700 transport reports millimetres and degrees; refusing to guess what "
                "%r/%r mean" % (self.translation_unit, self.rotation_unit))
        if len(values) < 6:
            raise EpicProtocolError("a pose row needs six values, got %d" % len(values))
        numbers = [float(value) for value in values[:6]]
        if not all(math.isfinite(value) for value in numbers):
            raise EpicProtocolError("a pose row contains a non-finite value")
        degrees = math.radians(1.0)
        return Pose(self.pose_frame, numbers[0] / 1000.0, numbers[1] / 1000.0, numbers[2] / 1000.0,
                    numbers[3] * degrees, numbers[4] * degrees, numbers[5] * degrees)

    def _parse_pose(self, raw: str, kind: str, request_id: str) -> DetectionResult:
        """One 5700 response -> every candidate plus the camera's own identifiers.

        The header carries space id, object id, grasp index and the total grasp
        count. Reading only the last six numbers, as this client used to, threw
        all of that away and accepted frames it could not actually interpret.
        """
        try:
            response = parse_5700_response(raw)
        except ValueError as exc:
            acknowledgement = parse_acknowledgement(raw)
            if acknowledgement is not None:
                raise EpicProtocolError(
                    "Epic acknowledged %r (%s) but sent no grasp poses; a detection needs a "
                    "120 or 320 command" % (acknowledgement.raw, acknowledgement.description)) from exc
            raise EpicProtocolError(str(exc)) from exc
        if response.pose_type != "cartesian":
            raise EpicProtocolError(
                "Epic returned pose type %s; this client converts Cartesian end-effector "
                "poses only, and joint path points must go through the trajectory route"
                % response.pose_type)
        if response.pose_count != len(response.poses):
            raise EpicProtocolError("Epic declared %d poses but sent %d"
                                    % (response.pose_count, len(response.poses)))
        candidates = [self._as_pose(values) for values in response.poses]
        meta = dict(
            command_code=response.command_code, pose_type=response.pose_type,
            pose_count=response.pose_count, object_count=response.object_count,
            total_grasp_count=response.total_grasp_count, space_id=response.space_id,
            object_id=response.object_id, grasp_index=response.grasp_index,
            grasp_sequence=response.grasp_sequence, status=response.status,
            pose_frame=self.pose_frame, pose_frame_verified=self.pose_frame_verified,
            source_translation_unit=self.translation_unit,
            source_rotation_unit=self.rotation_unit,
        )
        return DetectionResult(True, request_id, kind, pose=candidates[0],
                               candidates=candidates, raw_response=raw, meta=meta)

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

    def switch_space(self, space_id: int, object_id: int) -> EpicAcknowledgement:
        """Select a configured space and object, e.g. space 2 for the right arm.

        Detection commands already carry the space id, so this exists for the
        cases where the selection has to stand on its own: auditing which space
        is active, or preparing a command that has no space field.
        """
        if space_id < 0 or object_id < 0:
            raise ValueError("space and object ids cannot be negative")
        raw = self._exchange("130,%d,%d" % (space_id, object_id))
        self._last_probe, self._last_error = True, ""
        acknowledgement = parse_acknowledgement(raw)
        if acknowledgement is None or acknowledgement.command_code != 130:
            raise EpicProtocolError("switching to space %d object %d was not acknowledged: %r"
                                    % (space_id, object_id, raw))
        return acknowledgement

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
