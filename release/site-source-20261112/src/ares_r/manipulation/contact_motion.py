"""Target-aware terminal contact without weakening free-space collision rules."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping, Sequence

from ares_r.perception.robot_collision import CollisionBox, obb_overlap


def _vector(values, label):
    result = tuple(float(item) for item in values)
    if len(result) != 3 or not all(math.isfinite(item) for item in result):
        raise ValueError("%s must contain three finite values" % label)
    return result


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _subtract(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _norm(a):
    return math.sqrt(_dot(a, a))


def _collision_box(value, identifier):
    rotation = value.get("rotation_body", ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    half = value.get("half_extents_m")
    if half is None:
        half = [float(item)/2.0 for item in value["dims_m"]]
    return CollisionBox(identifier, "contact_validator", "contact_component",
                        tuple(float(v) for v in value["center_body_m"]),
                        tuple(tuple(float(v) for v in row) for row in rotation),
                        tuple(float(v) for v in half), False, "P3.8B1")


def _geometry_overlap(first, second):
    return obb_overlap(_collision_box(first, first.get("geometry_id", "first")),
                       _collision_box(second, second.get("geometry_id", "second")))


@dataclass(frozen=True)
class TargetContactPolicy:
    revision: str
    target_object_id: str
    approach_direction_body: Sequence[float]
    approach_length_m: float
    terminal_contact_corridor_m: float = .012
    maximum_lateral_deviation_m: float = .002

    def validate(self):
        direction = _vector(self.approach_direction_body, "approach direction")
        norm = _norm(direction)
        if not self.revision or not self.target_object_id or abs(norm-1.0) > 1e-6:
            raise ValueError("contact policy needs identity and a unit BODY direction")
        if not 0 < self.terminal_contact_corridor_m < self.approach_length_m <= .20:
            raise ValueError("invalid terminal contact corridor")
        if not 0 < self.maximum_lateral_deviation_m <= .01:
            raise ValueError("invalid approach lateral tolerance")


def validate_contact_approach(samples: Sequence[Mapping[str, object]],
                              target: Mapping[str, object],
                              obstacles: Mapping[str, Mapping[str, object]],
                              policy: TargetContactPolicy, *,
                              expected_component_revision=None) -> dict:
    """Validate dense geometry; only tool/gripper may contact target at the end."""
    policy.validate()
    if len(samples) < 2:
        raise ValueError("dense contact samples required")
    start = _vector(samples[0]["tcp_position_body_m"], "start TCP")
    direction = _vector(policy.approach_direction_body, "approach direction")
    prior = -math.inf
    contacts = []
    for index, sample in enumerate(samples):
        tcp = _vector(sample["tcp_position_body_m"], "TCP")
        delta = _subtract(tcp, start)
        progress = _dot(delta, direction)
        lateral = _norm(tuple(delta[i]-progress*direction[i] for i in range(3)))
        if progress + 1e-9 < prior or progress < -1e-6 or progress > policy.approach_length_m + .003:
            raise RuntimeError("contact approach is not monotonic and bounded")
        if lateral > policy.maximum_lateral_deviation_m:
            raise RuntimeError("contact approach left its straight BODY corridor")
        prior = progress
        components = sample.get("components") or {}
        if not {"arm_links", "tool", "gripper"}.issubset(components):
            raise RuntimeError("full arm/tool/gripper dense geometry is required")
        for component, boxes in components.items():
            for box in boxes:
                if component == "gripper" and expected_component_revision is not None:
                    if box.get("component_revision") != expected_component_revision:
                        raise RuntimeError("gripper component geometry revision mismatch")
                for obstacle_id, obstacle in obstacles.items():
                    if _geometry_overlap(box, obstacle):
                        raise RuntimeError("%s contacted non-target %s" % (component, obstacle_id))
                if _geometry_overlap(box, target):
                    if component == "arm_links":
                        raise RuntimeError("arm link contacted target")
                    if component not in ("tool", "gripper"):
                        raise RuntimeError("unapproved component contacted target")
                    earliest = policy.approach_length_m - policy.terminal_contact_corridor_m
                    if progress + 1e-9 < earliest:
                        raise RuntimeError("tool/gripper contacted target before terminal corridor")
                    contacts.append({"sample": index, "component": component,
                                     "progress_m": progress})
    if abs(prior-policy.approach_length_m) > .003:
        raise RuntimeError("contact approach did not reach its terminal pose")
    return {"valid": True, "policy_revision": policy.revision,
            "target_object_id": policy.target_object_id,
            "gripper_component_revision": expected_component_revision,
            "samples": len(samples), "contacts": contacts,
            "arm_target_contact_allowed": False,
            "tool_target_contact_scope": "FINAL_CONTACT_CORRIDOR_ONLY",
            "non_target_collision_policy": "HARD_COLLISION_ALWAYS"}


def plan_constrained_contact(start_pose_body, goal_pose_body, *, policy,
                             solve_ik: Callable, geometry_at: Callable,
                             target, obstacles, dense_step_m=.002,
                             expected_component_revision=None):
    """Cartesian interpolation + continuous IK + target-aware dense validation."""
    start = _vector(start_pose_body[:3], "start pose")
    goal = _vector(goal_pose_body[:3], "goal pose")
    delta = _subtract(goal, start)
    length = _norm(delta)
    if abs(length-policy.approach_length_m) > .003:
        raise RuntimeError("pose separation differs from TargetContactPolicy")
    count = max(2, int(math.ceil(length / float(dense_step_m))) + 1)
    poses = []
    joints = []
    seed = None
    for index in range(count):
        fraction = index / (count-1)
        position = tuple(start[axis] + fraction*delta[axis] for axis in range(3))
        pose = position + tuple(float(item) for item in goal_pose_body[3:])
        seed = tuple(float(item) for item in solve_ik(pose, seed))
        if len(seed) != 6:
            raise RuntimeError("continuous IK did not return six joints")
        poses.append(pose); joints.append(seed)
    samples = [geometry_at(joints[index], poses[index]) for index in range(count)]
    validation = validate_contact_approach(
        samples, target, obstacles, policy,
        expected_component_revision=expected_component_revision)
    return {"schema_version": 1, "motion_contract": "TARGET_CONTACT_APPROACH_V1",
            "trajectory_points_rad": [list(row) for row in joints],
            "tcp_poses_body_m_rad": [list(row) for row in poses],
            "contact_validation": validation,
            "gripper_component_revision": expected_component_revision,
            "execution_allowed": False}
