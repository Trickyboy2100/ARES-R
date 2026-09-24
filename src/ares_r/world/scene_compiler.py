"""Compile immutable BODY SceneSnapshots into arm-local cuRobo cuboids."""

import hashlib
import itertools
import json
from typing import Mapping, Sequence

import numpy as np

from .scene_snapshot import SceneObjectRole, snapshot_dict


def _matrix(value: Sequence[Sequence[float]], label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (4, 4) or not np.isfinite(result).all():
        raise ValueError("%s must be a finite 4x4 matrix" % label)
    if not np.allclose(result[3], [0, 0, 0, 1], atol=1e-9):
        raise ValueError("%s is not homogeneous" % label)
    return result


def transform_body_aabb(center_m, dimensions_m, T_arm_body):
    center = np.asarray(center_m, dtype=float)
    dims = np.asarray(dimensions_m, dtype=float)
    transform = _matrix(T_arm_body, "T_arm_body")
    if center.shape != (3,) or dims.shape != (3,) or not np.isfinite(center).all() or np.any(dims <= 0):
        raise ValueError("finite center and positive dimensions required")
    corners = np.asarray([center + dims * np.asarray(signs) / 2.0
                          for signs in itertools.product((-1.0, 1.0), repeat=3)])
    local = (np.c_[corners, np.ones(len(corners))] @ transform.T)[:, :3]
    low, high = local.min(axis=0), local.max(axis=0)
    return ((low + high) / 2.0).tolist(), (high - low).tolist()


def _quaternion_wxyz(rotation):
    """Normalized quaternion for a proper 3x3 rotation matrix."""
    matrix = np.asarray(rotation, dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(np.asarray([
        [matrix[0, 0]-matrix[1, 1]-matrix[2, 2], matrix[1, 0]+matrix[0, 1], matrix[2, 0]+matrix[0, 2], matrix[1, 2]-matrix[2, 1]],
        [matrix[1, 0]+matrix[0, 1], matrix[1, 1]-matrix[0, 0]-matrix[2, 2], matrix[2, 1]+matrix[1, 2], matrix[2, 0]-matrix[0, 2]],
        [matrix[2, 0]+matrix[0, 2], matrix[2, 1]+matrix[1, 2], matrix[2, 2]-matrix[0, 0]-matrix[1, 1], matrix[0, 1]-matrix[1, 0]],
        [matrix[1, 2]-matrix[2, 1], matrix[2, 0]-matrix[0, 2], matrix[0, 1]-matrix[1, 0], matrix.trace()],
    ]) / 3.0)
    xyzw = eigenvectors[:, int(np.argmax(eigenvalues))]
    value = np.asarray([xyzw[3], xyzw[0], xyzw[1], xyzw[2]])
    if value[0] < 0: value = -value
    return (value / np.linalg.norm(value)).tolist()


def transform_body_cuboid(center_m, dimensions_m, T_arm_body):
    transform = _matrix(T_arm_body, "T_arm_body")
    center = transform[:3, :3] @ np.asarray(center_m, dtype=float) + transform[:3, 3]
    return center.tolist(), list(dimensions_m), _quaternion_wxyz(transform[:3, :3])


def compile_snapshot(snapshot, arm: str, T_body_model, planning_scope="DEMO_OFFLINE_ONLY",
                     target_policy="HARD") -> Mapping[str, object]:
    if arm not in ("left", "right"):
        raise ValueError("arm must be left or right")
    body_model = _matrix(T_body_model, "T_body_model")
    model_body = np.linalg.inv(body_model)
    objects = snapshot.environment.observation.obstacles
    cuboids = {}
    targets = {}
    provenance = []
    for item in objects:
        if item.pose.frame_id != "body" or item.geometry_type != "cuboid":
            raise ValueError("SceneCompiler accepts BODY cuboids only")
        inflated = (np.asarray(item.dimensions_m, dtype=float) + 2.0 * item.inflation_m).tolist()
        if planning_scope == "P3_PRODUCTION_PLANNING_ONLY":
            center, dims, orientation = transform_body_cuboid(item.pose.xyz_m, inflated, model_body)
        else:
            center, dims = transform_body_aabb(item.pose.xyz_m, inflated, model_body)
            orientation = [1, 0, 0, 0]
        entry = {"dims": dims, "pose": center + orientation, "inflation_m": item.inflation_m}
        if item.role is SceneObjectRole.TARGET:
            targets[item.object_id] = entry
            if target_policy not in ("HARD", "CONTACT_CORRIDOR"):
                raise ValueError("target_policy must be HARD or CONTACT_CORRIDOR")
            if target_policy == "HARD":
                cuboids[item.object_id] = {"dims": entry["dims"], "pose": entry["pose"]}
        else:
            cuboids[item.object_id] = {"dims": entry["dims"], "pose": entry["pose"]}
        provenance.append({"object_id": item.object_id, "role": item.role.value,
                           "source_observation_id": item.source_observation_id,
                           "inflation_m": item.inflation_m,
                           "used_as": ("hard_target" if item.role is SceneObjectRole.TARGET
                                       and target_policy == "HARD" else
                                       "contact_corridor_target" if item.role is SceneObjectRole.TARGET
                                       else "obstacle")
                           })
    payload = {
        "schema_version": 1, "frame": "curobo_model_base", "arm": arm,
        "source": "scene_snapshot_compiler", "planning_scope": planning_scope,
        "execution_allowed": False, "scene_snapshot_id": snapshot.snapshot_id,
        "planning_context_digest": snapshot.planning_context_digest,
        "calibration_revision": dict(snapshot.calibration_revision),
        "cuboids": cuboids, "targets": targets, "target_policy": target_policy,
        "provenance": provenance,
    }
    payload["digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload
