"""Immutable environment, observation and planning snapshot contracts."""

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any, Dict, Optional, Sequence, Tuple

from .robot_state import PoseSE3, RobotState


class SceneObjectRole(str,Enum):
    FIXED="FIXED"
    OBSTACLE="OBSTACLE"
    TARGET="TARGET"


@dataclass(frozen=True)
class SceneObject:
    object_id: str
    role: SceneObjectRole
    geometry_type: str
    pose: PoseSE3
    dimensions_m: Tuple[float, ...]
    inflation_m: float
    source_observation_id: str
    confidence: float=1.0

    def __post_init__(self) -> None:
        role=SceneObjectRole(self.role)
        dimensions=tuple(float(value) for value in self.dimensions_m)
        if not self.object_id or self.geometry_type not in ("cuboid",): raise ValueError("invalid scene object identity/geometry")
        if len(dimensions)!=3 or not all(math.isfinite(value) and value>0 for value in dimensions): raise ValueError("cuboid dimensions must be positive SI values")
        if not math.isfinite(self.inflation_m) or self.inflation_m<0: raise ValueError("inflation_m must be finite and nonnegative")
        if not math.isfinite(self.confidence) or not 0<=self.confidence<=1: raise ValueError("confidence must be 0..1")
        if not self.source_observation_id: raise ValueError("source_observation_id is required")
        object.__setattr__(self,"role",role);object.__setattr__(self,"dimensions_m",dimensions)


@dataclass(frozen=True)
class AttachedObject:
    object_id: str
    attached_to: str
    tcp_to_object: PoseSE3
    collision_geometry: SceneObject
    source_revision: str

    def __post_init__(self) -> None:
        if self.attached_to not in ("left","right") or not self.object_id or not self.source_revision:
            raise ValueError("invalid attached object")


@dataclass(frozen=True)
class SafetyConstraint:
    constraint_id: str
    kind: str
    parameters: Tuple[Tuple[str, float], ...]

    def __post_init__(self) -> None:
        parameters=tuple(sorted((str(key),float(value)) for key,value in self.parameters))
        if not self.constraint_id or not self.kind or any(not math.isfinite(value) for _,value in parameters):
            raise ValueError("invalid safety constraint")
        if len(dict(parameters))!=len(parameters): raise ValueError("constraint parameter names must be unique")
        object.__setattr__(self,"parameters",parameters)


@dataclass(frozen=True)
class CalibrationSet:
    revisions: Tuple[Tuple[str, str], ...]

    def __post_init__(self) -> None:
        revisions=tuple(sorted((str(key),str(value)) for key,value in self.revisions))
        if not revisions or any(not key or not value for key,value in revisions) or len(dict(revisions))!=len(revisions):
            raise ValueError("calibration revisions must be unique and non-empty")
        object.__setattr__(self,"revisions",revisions)


@dataclass(frozen=True)
class PointCloudRef:
    pointcloud_id: str
    sha256: str
    coordinate_frame: str

    def __post_init__(self) -> None:
        if not self.pointcloud_id or len(self.sha256)!=64 or any(c not in "0123456789abcdef" for c in self.sha256.lower()) or not self.coordinate_frame:
            raise ValueError("invalid pointcloud reference")
        object.__setattr__(self,"sha256",self.sha256.lower())


@dataclass(frozen=True)
class ObservationEpoch:
    observation_id: str
    captured_wall_unix_ns: int
    captured_monotonic_ns: int
    runtime_id: str
    calibration: CalibrationSet
    pointcloud: PointCloudRef
    obstacles: Tuple[SceneObject, ...]
    detection_ids: Tuple[str, ...]=()

    def __post_init__(self) -> None:
        if not self.observation_id or not self.runtime_id or self.captured_wall_unix_ns<=0 or self.captured_monotonic_ns<0:
            raise ValueError("invalid observation epoch identity/timestamps")
        obstacles=tuple(sorted(self.obstacles,key=lambda item:item.object_id))
        if any(item.source_observation_id!=self.observation_id for item in obstacles):
            raise ValueError("all obstacles must belong to the same observation epoch")
        ids=[item.object_id for item in obstacles]
        if len(ids)!=len(set(ids)): raise ValueError("scene object IDs must be unique")
        object.__setattr__(self,"obstacles",obstacles)
        object.__setattr__(self,"detection_ids",tuple(sorted(self.detection_ids)))


@dataclass(frozen=True)
class EnvironmentRevision:
    environment_revision_id: str
    observation: ObservationEpoch
    obstacle_digest: str
    scene_digest: str

    def __post_init__(self) -> None:
        if not self.environment_revision_id or len(self.obstacle_digest)!=64 or len(self.scene_digest)!=64:
            raise ValueError("invalid environment revision")


@dataclass(frozen=True)
class SceneSnapshot:
    schema_version: int
    snapshot_id: str
    created_wall_unix_ns: int
    created_monotonic_ns: int
    runtime_id: str
    environment: EnvironmentRevision
    robot_state: RobotState
    left_attached_object: Optional[AttachedObject]
    right_attached_object: Optional[AttachedObject]
    constraints: Tuple[SafetyConstraint, ...]
    robot_model_revision: str
    tool_revision: str
    robot_state_digest: str
    attachment_digest: str
    planning_context_digest: str

    def __post_init__(self) -> None:
        if self.schema_version!=1 or not self.snapshot_id or not self.runtime_id:
            raise ValueError("invalid scene snapshot identity")
        if not self.robot_model_revision or not self.tool_revision:
            raise ValueError("robot and tool revisions are required")
        for value in (self.robot_state_digest,self.attachment_digest,self.planning_context_digest):
            if len(value)!=64: raise ValueError("snapshot digests must be SHA-256")

    @property
    def pointcloud_id(self) -> str: return self.environment.observation.pointcloud.pointcloud_id

    @property
    def pointcloud_sha256(self) -> str: return self.environment.observation.pointcloud.sha256

    @property
    def calibration_revision(self) -> Tuple[Tuple[str,str], ...]:
        return self.environment.observation.calibration.revisions


def _plain(value: Any) -> Any:
    if isinstance(value,Enum): return value.value
    if is_dataclass(value): return {key:_plain(item) for key,item in asdict(value).items()}
    if isinstance(value,dict): return {str(key):_plain(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)): return [_plain(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value),sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def snapshot_dict(snapshot: SceneSnapshot) -> Dict[str,Any]:
    return _plain(snapshot)
