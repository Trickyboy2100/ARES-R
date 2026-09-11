"""Immutable, planning-grade robot state in explicit SI/SE(3) form."""

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple


def _finite(values: Sequence[float], size: int, label: str) -> Tuple[float, ...]:
    result=tuple(float(value) for value in values)
    if len(result)!=size or not all(math.isfinite(value) for value in result):
        raise ValueError("%s must contain %d finite values"%(label,size))
    return result


@dataclass(frozen=True)
class PoseSE3:
    frame_id: str
    xyz_m: Tuple[float, float, float]
    quaternion_wxyz: Tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if not self.frame_id: raise ValueError("PoseSE3 frame_id is required")
        xyz=_finite(self.xyz_m,3,"xyz_m");quaternion=_finite(self.quaternion_wxyz,4,"quaternion_wxyz")
        norm=math.sqrt(sum(value*value for value in quaternion))
        if abs(norm-1.0)>1e-6: raise ValueError("quaternion_wxyz must be normalized")
        object.__setattr__(self,"xyz_m",xyz);object.__setattr__(self,"quaternion_wxyz",quaternion)


@dataclass(frozen=True)
class RobotState:
    captured_wall_unix_ns: int
    captured_monotonic_ns: int
    runtime_id: str
    left_joints_rad: Optional[Tuple[float, ...]]=None
    right_joints_rad: Optional[Tuple[float, ...]]=None
    left_tcp: Optional[PoseSE3]=None
    right_tcp: Optional[PoseSE3]=None
    left_gripper_position: Optional[int]=None
    right_gripper_position: Optional[int]=None
    base_pose: Optional[PoseSE3]=None
    base_station: Optional[str]=None
    source_revisions: Tuple[Tuple[str, str], ...]=()

    def __post_init__(self) -> None:
        if self.captured_wall_unix_ns<=0 or self.captured_monotonic_ns<0 or not self.runtime_id:
            raise ValueError("robot state timestamps and runtime_id are required")
        for name in ("left_joints_rad","right_joints_rad"):
            value=getattr(self,name)
            if value is not None: object.__setattr__(self,name,_finite(value,6,name))
        for name in ("left_gripper_position","right_gripper_position"):
            value=getattr(self,name)
            if value is not None and (type(value) is not int or not 0<=value<=1000):
                raise ValueError("%s must be an integer in 0..1000"%name)
        revisions=tuple(sorted((str(key),str(value)) for key,value in self.source_revisions))
        if any(not key or not value for key,value in revisions) or len(dict(revisions))!=len(revisions):
            raise ValueError("source revisions must be unique and non-empty")
        object.__setattr__(self,"source_revisions",revisions)
