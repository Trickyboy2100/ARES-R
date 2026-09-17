"""Shared domain models. Internal units are metres, radians and seconds."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import time


class TaskState(str, Enum):
    IDLE = "IDLE"
    DETECTING_PICK = "DETECTING_PICK"
    PICK_READY = "PICK_READY"
    APPROACHING = "APPROACHING"
    GRASPING = "GRASPING"
    LIFTING = "LIFTING"
    HOLDING = "HOLDING"
    NAVIGATING = "NAVIGATING"
    DETECTING_PLACE = "DETECTING_PLACE"
    PLACE_READY = "PLACE_READY"
    PLACING = "PLACING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Pose:
    frame_id: str
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float

    def values(self) -> List[float]:
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]


@dataclass
class DetectionResult:
    success: bool
    request_id: str
    kind: str
    timestamp: float = field(default_factory=time.time)
    pose: Optional[Pose] = None
    confidence: Optional[float] = None
    raw_response: str = ""
    error: str = ""
    #: Every pose the camera reported, in the order it reported them. ``pose``
    #: stays the first candidate so existing task code keeps its meaning; the
    #: list is what a grasp planner scores, and dropping it loses the opposite
    #: grasp direction.
    candidates: List[Pose] = field(default_factory=list)
    #: Camera-side identifiers that must travel with the pose: space/object ids,
    #: grasp index and total, pose type. Never inferred, never defaulted.
    meta: Dict[str, object] = field(default_factory=dict)


@dataclass
class DeviceState:
    connected: bool
    ready: bool
    detail: str = ""


@dataclass
class SystemSnapshot:
    mode: str
    task_state: TaskState
    devices: Dict[str, DeviceState]
    active_arm: str
    carrying_object: bool
    last_detection: Optional[DetectionResult]
    last_error: str = ""
