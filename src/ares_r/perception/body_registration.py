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


def _angle_delta(a: float, b: float) -> float:
    return (float(a) - float(b) + math.pi) % (2.0 * math.pi) - math.pi


def robust_translation_yaw(observations: Sequence[Mapping[str, object]],
                           yaw_prior_rad: float,
                           huber_deg: float = 3.0) -> Mapping[str, object]:
    """Fit BODY<-LEVEL yaw from directed translation observations.

    Commanded distance is deliberately ignored: site evidence shows that the
    AMR relative-motion endpoint can report completion without honoring the
    requested magnitude.  Only the declared BODY direction and the registered
    point-cloud translation direction participate in the estimate.
    """
    prior = float(yaw_prior_rad)
    if not math.isfinite(prior):
        raise ValueError("finite yaw prior required")
    accepted, rejected = [], []
    for raw in observations:
        item = dict(raw)
        label = str(item.get("label", "unnamed"))
        vector = np.asarray(item.get("translation_level_m"), dtype=float)
        reasons = []
        if vector.shape != (3,) or not np.isfinite(vector).all():
            reasons.append("finite translation_level_m required")
        else:
            horizontal = float(np.linalg.norm(vector[:2]))
            if horizontal < 0.02:
                reasons.append("horizontal translation below 0.02 m")
        fitness = float(item.get("fitness", 0.0))
        rmse = float(item.get("rmse_m", math.inf))
        drift = float(item.get("rotation_drift_deg", math.inf))
        valid_ratio = float(item.get("valid_ratio", 0.0))
        if fitness < 0.55: reasons.append("fitness below 0.55")
        if not math.isfinite(rmse) or rmse > 0.035: reasons.append("RMSE above 0.035 m")
        if not math.isfinite(drift) or drift > 1.5: reasons.append("rotation drift above 1.5 deg")
        if valid_ratio < 0.75: reasons.append("valid point ratio below 0.75")
        heading = math.radians(float(item.get("expected_body_heading_deg", math.nan)))
        if not math.isfinite(heading): reasons.append("finite expected BODY heading required")
        if reasons:
            rejected.append({"label": label, "reasons": reasons})
            continue
        observed = math.atan2(float(vector[1]), float(vector[0]))
        yaw = prior + _angle_delta(heading - observed, prior)
        base_weight = fitness * valid_ratio / max(rmse, 0.002) ** 2
        accepted.append({"label": label, "yaw_rad": yaw, "yaw_deg": math.degrees(yaw),
                         "horizontal_translation_m": horizontal,
                         "base_weight": base_weight,
                         "expected_body_heading_deg": math.degrees(heading)})
    if len(accepted) < 2:
        raise ValueError("at least two quality-gated translation observations are required")
    headings = [math.radians(item["expected_body_heading_deg"]) for item in accepted]
    independent = max(abs(math.sin(a - b)) for i, a in enumerate(headings) for b in headings[i + 1:])
    if independent < math.sin(math.radians(20.0)):
        raise ValueError("translation observations are not directionally independent")
    estimate = prior
    huber = math.radians(float(huber_deg))
    prior_weight = float(np.median([item["base_weight"] for item in accepted]))
    for _ in range(12):
        values = [(prior, prior_weight)]
        for item in accepted:
            residual = abs(_angle_delta(item["yaw_rad"], estimate))
            robust = 1.0 if residual <= huber else huber / residual
            values.append((estimate + _angle_delta(item["yaw_rad"], estimate), item["base_weight"] * robust))
        updated = sum(value * weight for value, weight in values) / sum(weight for _, weight in values)
        if abs(updated - estimate) < 1e-12: break
        estimate = updated
    residuals = []
    for item in accepted:
        residual = math.degrees(_angle_delta(item["yaw_rad"], estimate))
        item["residual_deg"] = residual
        residuals.append(abs(residual))
    return {
        "yaw_rad": estimate,
        "yaw_deg": math.degrees(estimate),
        "prior_deg": math.degrees(prior),
        "prior_residual_deg": math.degrees(_angle_delta(estimate, prior)),
        "max_translation_residual_deg": max(residuals),
        "accepted": accepted,
        "rejected": rejected,
        "directional_independence": independent,
    }
