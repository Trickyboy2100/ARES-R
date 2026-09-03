"""Strict trajectory file contract shared by Epic, cuRobo and JAKA adapters."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class Trajectory:
    schema_version: int
    planner: str
    arm: str
    joint_names: Tuple[str, ...]
    sample_period_s: float
    points: Tuple[Tuple[float, ...], ...]
    collision_checked: bool
    robot_model_revision: str
    world_revision: str
    tool_revision: str
    attached_object_revision: str


@dataclass(frozen=True)
class MotionLimits:
    joint_names: Tuple[str, ...]
    lower_rad: Tuple[float, ...]
    upper_rad: Tuple[float, ...]
    max_velocity_rad_s: Tuple[float, ...]
    max_acceleration_rad_s2: Tuple[float, ...]
    soft_limit_margin_rad: float
    max_start_error_rad: float
    commissioning_confirmed: bool


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


def _finite_tuple(values: Sequence[object], label: str) -> Tuple[float, ...]:
    converted = tuple(float(value) for value in values)
    if not converted or not all(math.isfinite(value) for value in converted):
        raise ValueError("%s must contain finite numeric values" % label)
    return converted


def load_trajectory(path: Path) -> Trajectory:
    data = json.loads(path.read_text(encoding="utf-8"))
    points = tuple(_finite_tuple(point, "points") for point in data["points"])
    return Trajectory(
        schema_version=int(data["schema_version"]),
        planner=str(data["planner"]),
        arm=str(data["arm"]),
        joint_names=tuple(str(name) for name in data["joint_names"]),
        sample_period_s=float(data["sample_period_s"]),
        points=points,
        collision_checked=bool(data["collision_checked"]),
        robot_model_revision=str(data["robot_model_revision"]),
        world_revision=str(data["world_revision"]),
        tool_revision=str(data["tool_revision"]),
        attached_object_revision=str(data["attached_object_revision"]),
    )


def load_motion_limits(path: Path) -> MotionLimits:
    data = json.loads(path.read_text(encoding="utf-8"))
    return MotionLimits(
        joint_names=tuple(str(name) for name in data["joint_names"]),
        lower_rad=_finite_tuple(data["lower_rad"], "lower_rad"),
        upper_rad=_finite_tuple(data["upper_rad"], "upper_rad"),
        max_velocity_rad_s=_finite_tuple(data["max_velocity_rad_s"], "max_velocity_rad_s"),
        max_acceleration_rad_s2=_finite_tuple(data["max_acceleration_rad_s2"], "max_acceleration_rad_s2"),
        soft_limit_margin_rad=float(data["soft_limit_margin_rad"]),
        max_start_error_rad=float(data["max_start_error_rad"]),
        commissioning_confirmed=bool(data["commissioning_confirmed"]),
    )


def validate_trajectory(
    trajectory: Trajectory,
    limits: MotionLimits,
    current_joints: Sequence[float] = (),
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    def error(code: str, message: str) -> None:
        issues.append(ValidationIssue("ERROR", code, message))

    if trajectory.schema_version != 1:
        error("SCHEMA", "schema_version must be 1")
    if trajectory.arm not in ("left", "right"):
        error("ARM", "arm must be left or right")
    if trajectory.joint_names != limits.joint_names:
        error("JOINT_ORDER", "trajectory and motion-limit joint order differ")
    if not limits.commissioning_confirmed:
        error("UNCONFIRMED_LIMITS", "site motion limits have not been commissioned")
    if trajectory.sample_period_s <= 0 or not math.isfinite(trajectory.sample_period_s):
        error("TIMING", "sample_period_s must be finite and positive")
    else:
        step_num = trajectory.sample_period_s / 0.008
        if abs(step_num - round(step_num)) > 1e-9:
            error("JAKA_PERIOD", "sample_period_s must be an integer multiple of 0.008 s")
    if len(trajectory.points) < 2:
        error("POINT_COUNT", "at least two trajectory points are required")
    if not trajectory.collision_checked:
        error("COLLISION", "planner did not attest collision checking")
    for field_name in ("robot_model_revision", "world_revision", "tool_revision", "attached_object_revision"):
        if not getattr(trajectory, field_name):
            error("REVISION", "%s is required" % field_name)

    dof = len(limits.joint_names)
    limit_vectors = (
        limits.lower_rad,
        limits.upper_rad,
        limits.max_velocity_rad_s,
        limits.max_acceleration_rad_s2,
    )
    if any(len(vector) != dof for vector in limit_vectors):
        error("LIMIT_SHAPE", "all motion-limit vectors must match joint_names")
        return issues
    if any(len(point) != dof for point in trajectory.points):
        error("POINT_SHAPE", "every point must match joint_names")
        return issues

    for point_index, point in enumerate(trajectory.points):
        for joint_index, value in enumerate(point):
            lower = limits.lower_rad[joint_index] + limits.soft_limit_margin_rad
            upper = limits.upper_rad[joint_index] - limits.soft_limit_margin_rad
            if not lower <= value <= upper:
                error("SOFT_LIMIT", "point %d joint %s is outside [%.6f, %.6f]" % (
                    point_index, limits.joint_names[joint_index], lower, upper))

    dt = trajectory.sample_period_s
    velocities: List[Tuple[float, ...]] = []
    for point_index in range(1, len(trajectory.points)):
        velocity = tuple((trajectory.points[point_index][j] - trajectory.points[point_index - 1][j]) / dt for j in range(dof))
        velocities.append(velocity)
        for joint_index, value in enumerate(velocity):
            if abs(value) > limits.max_velocity_rad_s[joint_index]:
                error("VELOCITY", "segment %d joint %s exceeds velocity limit" % (point_index - 1, limits.joint_names[joint_index]))
    for segment_index in range(1, len(velocities)):
        for joint_index in range(dof):
            acceleration = (velocities[segment_index][joint_index] - velocities[segment_index - 1][joint_index]) / dt
            if abs(acceleration) > limits.max_acceleration_rad_s2[joint_index]:
                error("ACCELERATION", "segment %d joint %s exceeds acceleration limit" % (segment_index, limits.joint_names[joint_index]))

    if current_joints:
        if len(current_joints) != dof:
            error("CURRENT_SHAPE", "current joint vector must match joint_names")
        elif any(abs(float(current_joints[j]) - trajectory.points[0][j]) > limits.max_start_error_rad for j in range(dof)):
            error("START_MISMATCH", "current joints differ from the first trajectory point")
    return issues
