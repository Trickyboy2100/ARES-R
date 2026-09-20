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


def compile_snapshot(snapshot, arm: str, T_body_model, planning_scope="DEMO_OFFLINE_ONLY") -> Mapping[str, object]:
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
        center, dims = transform_body_aabb(item.pose.xyz_m, item.dimensions_m, model_body)
        entry = {"dims": dims, "pose": center + [1, 0, 0, 0], "inflation_m": item.inflation_m}
        # The object about to be grasped has to be entered by the gripper, so it
        # cannot double as a solid obstacle. It is moved to ``targets`` rather
        # than dropped, so the scene still accounts for every observed object.
        if item.role is SceneObjectRole.TARGET:
            targets[item.object_id] = entry
        else:
            cuboids[item.object_id] = {"dims": entry["dims"], "pose": entry["pose"]}
        provenance.append({"object_id": item.object_id, "role": item.role.value,
                           "source_observation_id": item.source_observation_id,
                           "inflation_m": item.inflation_m,
                           "used_as": "target" if item.role is SceneObjectRole.TARGET
                           else "obstacle"})
    payload = {
        "schema_version": 1, "frame": "curobo_model_base", "arm": arm,
        "source": "scene_snapshot_compiler", "planning_scope": planning_scope,
        "execution_allowed": False, "scene_snapshot_id": snapshot.snapshot_id,
        "planning_context_digest": snapshot.planning_context_digest,
        "calibration_revision": dict(snapshot.calibration_revision),
        "cuboids": cuboids, "targets": targets, "provenance": provenance,
    }
    payload["digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload
