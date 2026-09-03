"""Deterministic mock devices. These never contact hardware."""

import time
import uuid
from typing import Optional
from ..interfaces import Arm, Gripper, MobileBase, Perception
from ..models import DetectionResult, DeviceState, Pose


class MockPerception(Perception):
    def __init__(self) -> None:
        self._connected = True

    def detect_pick(self) -> DetectionResult:
        time.sleep(0.2)
        return DetectionResult(True, str(uuid.uuid4()), "pick", pose=Pose("left_arm_base", 0.42, -0.18, 0.21, 3.14159, 0.0, -0.78), confidence=0.98, raw_response="mock")

    def detect_place(self, dock_id: int) -> DetectionResult:
        time.sleep(0.2)
        return DetectionResult(True, str(uuid.uuid4()), "place", pose=Pose("left_arm_base", 0.35, -0.25 + 0.04 * dock_id, 0.18, 3.14159, 0.0, -0.78), confidence=0.97, raw_response="mock")

    def state(self) -> DeviceState:
        return DeviceState(self._connected, True, "mock camera")


class MockArm(Arm):
    def __init__(self, name: str) -> None:
        self.name = name
        self.pose_name = "park"
        self.stopped = False

    def _check(self) -> None:
        if self.stopped:
            raise RuntimeError("%s arm is stopped; reset is required" % self.name)

    def move_to_pose(self, pose: Pose) -> None:
        self._check(); time.sleep(0.15); self.pose_name = "pose:%s" % pose.frame_id

    def move_linear_tool(self, distance_m: float) -> None:
        self._check(); time.sleep(0.1)

    def move_named(self, name: str) -> None:
        self._check(); time.sleep(0.15); self.pose_name = name

    def stop(self) -> None:
        self.stopped = True

    def reset(self) -> None:
        self.stopped = False

    def state(self) -> DeviceState:
        return DeviceState(True, not self.stopped, "%s; %s" % (self.name, self.pose_name))


class MockGripper(Gripper):
    def __init__(self) -> None:
        self.closed = False
        self.stopped = False

    def open(self) -> None:
        if self.stopped: raise RuntimeError("gripper is stopped")
        time.sleep(0.1); self.closed = False

    def close(self) -> None:
        if self.stopped: raise RuntimeError("gripper is stopped")
        time.sleep(0.1); self.closed = True

    def has_object(self) -> bool:
        return self.closed

    def stop(self) -> None:
        self.stopped = True

    def reset(self) -> None:
        self.stopped = False

    def state(self) -> DeviceState:
        return DeviceState(True, not self.stopped, "closed" if self.closed else "open")


class MockBase(MobileBase):
    def __init__(self) -> None:
        self._station: Optional[str] = None
        self.stopped = False

    def navigate(self, station: str) -> None:
        if self.stopped: raise RuntimeError("base is stopped")
        time.sleep(0.25); self._station = station

    def stop(self) -> None:
        self.stopped = True

    def reset(self) -> None:
        self.stopped = False

    def station(self) -> Optional[str]:
        return self._station

    def state(self) -> DeviceState:
        return DeviceState(True, not self.stopped, self._station or "unknown station")
