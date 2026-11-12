"""Deterministic dual-arm validation of the fixed BODY-to-camera transform.

This module never talks to hardware.  It composes the two Epic Pro eye-to-hand
results with the installed arm-base transforms, evaluates both possible matrix
directions, and projects one already captured calibration-board pose.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np


REPORT_RELATIVE = Path("worklog/evidence/2026-09-20-body-camera-dual-arm-crosscheck/report.json")


def _proper_se3(value: Iterable[Iterable[float]]) -> tuple[np.ndarray, float]:
    matrix = np.asarray(value, dtype=float).copy()
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError("finite 4x4 transform required")
    if not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
        raise ValueError("invalid homogeneous bottom row")
    left, _, right = np.linalg.svd(matrix[:3, :3])
    rotation = left @ right
    if np.linalg.det(rotation) < 0.0:
        left[:, -1] *= -1.0
        rotation = left @ right
    correction = float(np.max(np.abs(matrix[:3, :3] - rotation)))
    matrix[:3, :3] = rotation
    return matrix, correction


def _body_base(world: dict, arm: str) -> np.ndarray:
    item = world["arms"][arm]
    roll, pitch, yaw = [float(value) for value in item["base_rpy_rad"]]
    if abs(roll) > 1e-12 or abs(pitch) > 1e-12:
        raise ValueError("P0-B expects the commissioned level arm-base installation")
    cosine, sine = math.cos(yaw), math.sin(yaw)
    result = np.eye(4)
    result[:3, :3] = [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]]
    result[:3, 3] = np.asarray(item["base_xyz_m"], dtype=float)
    return result


def _angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    cosine = np.clip((np.trace(first.T @ second) - 1.0) / 2.0, -1.0, 1.0)
    return math.degrees(math.acos(float(cosine)))


def _rotation_vector(vector_deg: Iterable[float]) -> np.ndarray:
    vector = np.radians(np.asarray(list(vector_deg), dtype=float))
    theta = float(np.linalg.norm(vector))
    if theta < 1e-12:
        return np.eye(3)
    axis = vector / theta
    x, y, z = axis
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(theta) * skew + (1.0 - math.cos(theta)) * (skew @ skew)


def _quaternion_xyzw(value: dict) -> np.ndarray:
    x, y, z, w = [float(value[key]) for key in ("x", "y", "z", "w")]
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _serialise(matrix: np.ndarray) -> list[list[float]]:
    return [[round(float(value), 12) for value in row] for row in matrix]


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_report(repository: Path) -> dict:
    repository = Path(repository)
    world = _load(repository / "config/robot_world.json")
    system = _load(repository / "config/system.json")
    estimates: dict[str, dict[str, np.ndarray]] = {}
    rounding: dict[str, dict[str, float]] = {}

    for arm in ("left", "right"):
        source = repository / (
            "worklog/evidence/2026-09-20-epic-handeye/handeye-%s-from-ui.json" % arm)
        evidence = _load(source)
        raw = np.asarray(evidence["transform"], dtype=float)
        raw[:3, 3] /= 1000.0
        handeye, correction = _proper_se3(raw)
        body_base = _body_base(world, arm)
        h1 = body_base @ handeye
        h2 = body_base @ np.linalg.inv(handeye)
        rotation_vector = _rotation_vector(evidence["rotation_vector_deg"])
        rounding[arm] = {
            "matrix_orthonormalisation_max_element": correction,
            "matrix_vs_rotation_vector_deg": _angle_deg(handeye[:3, :3], rotation_vector),
        }
        estimates[arm] = {"H1": h1, "H2": h2}

    hypotheses = {}
    for name in ("H1", "H2"):
        left, right = estimates["left"][name], estimates["right"][name]
        hypotheses[name] = {
            "left_camera_origin_body_m": left[:3, 3].tolist(),
            "right_camera_origin_body_m": right[:3, 3].tolist(),
            "translation_disagreement_mm": float(np.linalg.norm(left[:3, 3] - right[:3, 3]) * 1000.0),
            "rotation_disagreement_deg": _angle_deg(left[:3, :3], right[:3, :3]),
            "T_body_camera_left": _serialise(left),
            "T_body_camera_right": _serialise(right),
        }

    board = _load(repository / "worklog/evidence/2026-09-20-epic-board-frame/board_pose.json")["board"]
    camera_board = np.eye(4)
    camera_board[:3, :3] = _quaternion_xyzw(board["rotation"])
    camera_board[:3, 3] = [float(board["translation"][axis]) / 1000.0 for axis in "xyz"]
    board_checks = {}
    for arm in ("left", "right"):
        body_board = estimates[arm]["H1"] @ camera_board
        normal = body_board[:3, 2]
        board_checks[arm] = {
            "T_body_board": _serialise(body_board),
            "origin_body_m": body_board[:3, 3].tolist(),
            "normal_body": normal.tolist(),
            "normal_to_body_up_deg": math.degrees(math.acos(float(np.clip(normal[2], -1.0, 1.0)))),
            "origin_table_height_error_mm": float((body_board[2, 3] - 0.750) * 1000.0),
            "board_x_yaw_body_deg": math.degrees(math.atan2(body_board[1, 0], body_board[0, 0])),
        }
    left_board = np.asarray(board_checks["left"]["T_body_board"])
    right_board = np.asarray(board_checks["right"]["T_body_board"])
    board_checks["left_right_disagreement"] = {
        "translation_mm": float(np.linalg.norm(left_board[:3, 3] - right_board[:3, 3]) * 1000.0),
        "rotation_deg": _angle_deg(left_board[:3, :3], right_board[:3, :3]),
        "note": "board-point delta includes the 0.72 deg hand-eye residual over a roughly 1.3 m lever arm",
    }

    existing = _load(repository / "worklog/evidence/2026-09-18-body-camera/right-2026-09-18-115006.json")
    configured = np.asarray(system["epic_pointcloud"]["T_body_camera"], dtype=float)
    right = estimates["right"]["H1"]
    config_match = {
        "translation_delta_mm": float(np.linalg.norm(configured[:3, 3] - right[:3, 3]) * 1000.0),
        "rotation_delta_deg": _angle_deg(configured[:3, :3], right[:3, :3]),
        "existing_revision": system["epic_pointcloud"]["T_body_camera_revision"],
        "is_right_H1_chain": bool(np.allclose(configured, right, atol=1e-9)),
    }
    pointcloud = {
        "source": "worklog/evidence/2026-09-18-body-camera/right-2026-09-18-115006.json",
        "support_plane_tilt_body_deg": existing["checks"]["support_tilt_deg"],
        "support_plane_interpretation": "table/support plane; level check only, not z=0 ground",
        "ground_median_z_m": existing["checks"]["ground"]["median_z_m"],
        "ground_spread_m": existing["checks"]["ground"]["spread_m"],
        "ground_point_count": existing["checks"]["ground"]["point_count"],
        "ground_interpretation": "ground band near BODY z=0; distinct from table at z≈0.750 m",
    }

    h1, h2 = hypotheses["H1"], hypotheses["H2"]
    semantic_passed = (
        h1["translation_disagreement_mm"] < 5.0
        and h1["rotation_disagreement_deg"] < 2.0
        and h2["translation_disagreement_mm"] > 100.0
    )
    validation_passed = (
        semantic_passed
        and board_checks["right"]["normal_to_body_up_deg"] < 2.0
        and abs(board_checks["right"]["origin_table_height_error_mm"]) < 30.0
        and pointcloud["support_plane_tilt_body_deg"] < 1.0
        and abs(pointcloud["ground_median_z_m"]) < 0.03
        and config_match["is_right_H1_chain"]
    )
    state = "COMMISSIONED" if validation_passed else ("CANDIDATE" if semantic_passed else "FAIL")
    result = {
        "schema_version": 1,
        "kind": "dual_arm_epic_handeye_crosscheck",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "selected_semantic": "T_armbase_camera" if semantic_passed else None,
        "selected_hypothesis": "H1" if semantic_passed else None,
        "hypotheses": hypotheses,
        "ui_rounding": rounding,
        "board_check": board_checks,
        "table_ground_check": pointcloud,
        "configured_transform_check": config_match,
        "production_source": "right Epic hand-eye H1 chain; left retained as independent validator",
        "fusion_policy": "no left/right averaging",
        "state": state,
        "p1_allowed": validation_passed,
    }
    result["validation_revision"] = _digest({key: value for key, value in result.items()
                                             if key not in ("recorded_at", "validation_revision")})
    return result


def read_report(repository: Path) -> dict:
    path = Path(repository) / REPORT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError("P0-B report not generated: %s" % path)
    return _load(path)
