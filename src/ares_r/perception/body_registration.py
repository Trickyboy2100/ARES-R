"""Pure geometry for auditable CAMERA-to-BODY registration candidates.

This module deliberately does not import Open3D, cuRobo, a camera SDK, or a
robot adapter.  Device capture, plane extraction and GPU model evaluation are
orchestrated by scripts; the frame math remains independently testable.
"""

import hashlib
import json
import math
from typing import Iterable, Mapping, Sequence

import numpy as np


def _unit(values: Sequence[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError("a finite three-vector is required")
    norm = float(np.linalg.norm(vector))
    if norm < 1e-12:
        raise ValueError("zero vector has no direction")
    return vector / norm


def align_vector(source: Sequence[float], target: Sequence[float]) -> np.ndarray:
    """Return a proper rotation mapping ``source`` onto ``target``."""
    a, b = _unit(source), _unit(target)
    cross = np.cross(a, b)
    sine = float(np.linalg.norm(cross))
    cosine = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if sine < 1e-12:
        if cosine > 0:
            return np.eye(3)
        # Deterministic 180-degree axis orthogonal to the input.
        basis = np.array([1.0, 0.0, 0.0])
        if abs(a[0]) > 0.8:
            basis = np.array([0.0, 1.0, 0.0])
        axis = _unit(np.cross(a, basis))
        return 2.0 * np.outer(axis, axis) - np.eye(3)
    axis = cross / sine
    skew = np.array([[0.0, -axis[2], axis[1]],
                     [axis[2], 0.0, -axis[0]],
                     [-axis[1], axis[0], 0.0]])
    return np.eye(3) + sine * skew + (1.0 - cosine) * (skew @ skew)


def level_transform(normal_camera: Sequence[float], plane_d: float) -> np.ndarray:
    """Create LEVEL<-CAMERA with the support surface at LEVEL z=0.

    RANSAC plane signs are arbitrary.  The supplied normal must point from the
    support surface away from the camera origin (positive signed depth).  BODY
    +Z points from the support toward the camera, hence ``-normal`` maps to +Z.
    Yaw and horizontal translation remain deliberately unobserved.
    """
    normal = _unit(normal_camera)
    d = float(plane_d) / float(np.linalg.norm(np.asarray(normal_camera, dtype=float)))
    if not math.isfinite(d):
        raise ValueError("finite plane offset required")
    # Make the origin lie on the camera-negative side; this fixes plane sign.
    if d > 0:
        normal, d = -normal, -d
    rotation = align_vector(-normal, [0.0, 0.0, 1.0])
    transform = np.eye(4)
    transform[:3, :3] = rotation
    # For a plane point n.p + d=0, (R.p).z = -n.p = d.
    transform[2, 3] = -d
    return transform


def plane_metrics(points: np.ndarray, normal: Sequence[float], plane_d: float) -> Mapping[str, object]:
    values = np.asarray(points, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or not len(values):
        raise ValueError("plane points must be a non-empty Nx3 array")
    n = _unit(normal)
    d = float(plane_d) / float(np.linalg.norm(np.asarray(normal, dtype=float)))
    residual = values @ n + d
    low, high = values.min(axis=0), values.max(axis=0)
    return {
        "normal_camera": n.tolist(),
        "plane_d_m": d,
        "inlier_count": int(len(values)),
        "centroid_camera_m": values.mean(axis=0).tolist(),
        "aabb_min_camera_m": low.tolist(),
        "aabb_max_camera_m": high.tolist(),
        "extent_camera_m": (high - low).tolist(),
        "rms_residual_m": float(np.sqrt(np.mean(residual * residual))),
    }


def choose_support_tracks(frames: Sequence[Sequence[Mapping[str, object]]],
                          normal_cosine: float = 0.998,
                          offset_tolerance_m: float = 0.035) -> list:
    """Associate repeatable planes and rank without assuming plane 0 is table."""
    tracks = []
    for frame_index, planes in enumerate(frames):
        for plane in planes:
            normal = _unit(plane["normal_camera"])
            d = float(plane["plane_d_m"])
            if d > 0:
                normal, d = -normal, -d
            match = None
            for track in tracks:
                mean_n = _unit(np.mean(track["normals"], axis=0))
                if abs(float(np.dot(normal, mean_n))) >= normal_cosine and abs(abs(d) - abs(np.mean(track["offsets"]))) <= offset_tolerance_m:
                    match = track
                    if float(np.dot(normal, mean_n)) < 0:
                        normal, d = -normal, -d
                    break
            if match is None:
                match = {"normals": [], "offsets": [], "members": []}
                tracks.append(match)
            match["normals"].append(normal)
            match["offsets"].append(d)
            match["members"].append({"frame_index": frame_index, **dict(plane)})
    ranked = []
    frame_count = max(1, len(frames))
    for index, track in enumerate(tracks):
        members = track["members"]
        distinct = len({item["frame_index"] for item in members})
        normal = _unit(np.mean(track["normals"], axis=0))
        angular = [math.degrees(math.acos(float(np.clip(np.dot(normal, _unit(value)), -1, 1))))
                   for value in track["normals"]]
        extents = [sorted(item["extent_camera_m"], reverse=True) for item in members]
        area_proxy = float(np.median([extent[0] * extent[1] for extent in extents]))
        count = float(np.median([item["inlier_count"] for item in members]))
        stability = max(0.0, 1.0 - max(angular, default=180.0) / 5.0)
        score = 4.0 * distinct / frame_count + min(2.0, area_proxy) + min(2.0, count / 2500.0) + stability
        ranked.append({
            "track_id": "plane_track_%02d" % index,
            "frame_coverage": distinct,
            "mean_normal_camera": normal.tolist(),
            "normal_max_deviation_deg": max(angular, default=0.0),
            "mean_plane_d_m": float(np.mean(track["offsets"])),
            "offset_std_m": float(np.std(track["offsets"])),
            "median_area_proxy_m2": area_proxy,
            "median_inlier_count": int(count),
            "score": score,
            "members": members,
        })
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def canonical_transform_revision(matrix: Iterable[Iterable[float]], evidence: Mapping[str, object]) -> str:
    transform = np.asarray(matrix, dtype=float)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("finite 4x4 transform required")
    payload = {"T_body_camera": transform.round(12).tolist(), "evidence": evidence}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
