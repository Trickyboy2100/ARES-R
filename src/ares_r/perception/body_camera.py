"""Commission ``T_body_camera`` from the arm-base chain, not from a fit.

The 2026-09-17 attempt solved BODY pose by fitting the point cloud and failed
closed with a 17 deg yaw spread and a 233 mm translation spread. This module
takes a route that has no such ambiguity: Epic has already calibrated its camera
against the right arm base, and ``robot_world.json`` already states where that
base sits in BODY. Composing the two is a multiplication, not an inference.

What still has to be earned is evidence, so the transform is checked against
invariants that owe nothing to the numbers being validated:

* a horizontal surface in the depth frame must stay horizontal in BODY, which
  tests the rotation;
* the ground must land at BODY z = 0, because BODY's origin is defined as the
  ground projection between the arm bases, which tests the translation.

Neither check consults an Epic-reported pose, so neither can be satisfied by a
matrix that is merely self-consistent.
"""

import math
from typing import Iterable, Mapping, Sequence

import numpy as np

from .body_registration import canonical_transform_revision

BODY_UP = np.array([0.0, 0.0, 1.0])

#: The Epic hand-eye matrix is transcribed from a config page that shows four
#: decimals, so its rows are orthonormal only to about 1e-4. Anything past this
#: is a transcription mistake rather than display rounding, and is refused.
ORTHONORMAL_TOLERANCE = 2e-3


def _se3(matrix: Iterable[Iterable[float]], label: str,
         tolerance: float = ORTHONORMAL_TOLERANCE) -> tuple:
    """Vet one transform and snap its rotation onto the nearest proper rotation.

    Returns the repaired matrix plus how far the rotation had to move, so a
    caller can record that a repair happened instead of silently absorbing it.
    """
    value = np.asarray(matrix, dtype=float)
    if value.shape != (4, 4) or not np.isfinite(value).all():
        raise ValueError("%s must be a finite 4x4 matrix" % label)
    if not np.allclose(value[3], [0.0, 0.0, 0.0, 1.0], atol=1e-9):
        raise ValueError("%s bottom row must be [0, 0, 0, 1]" % label)
    left, _, right = np.linalg.svd(value[:3, :3])
    rotation = left @ right
    if float(np.linalg.det(rotation)) < 0.0:
        left[:, -1] *= -1.0
        rotation = left @ right
    error = float(np.max(np.abs(value[:3, :3] - rotation)))
    if error > float(tolerance):
        raise ValueError(
            "%s rotation is off the nearest proper rotation by %.6f, beyond the "
            "%.6f transcription tolerance; it was probably copied with too few digits"
            % (label, error, tolerance))
    repaired = value.copy()
    repaired[:3, :3] = rotation
    return repaired, error


def compose_body_camera(T_body_base: Iterable[Iterable[float]],
                        T_base_camera: Iterable[Iterable[float]],
                        tolerance: float = ORTHONORMAL_TOLERANCE) -> dict:
    """``T_body_camera = T_body_base . T_base_camera``, with both inputs vetted.

    The result carries the orthonormalisation corrections so the commissioning
    record can state that a repair took place and how large it was.
    """
    base, base_error = _se3(T_body_base, "T_body_base", tolerance)
    camera, camera_error = _se3(T_base_camera, "T_base_camera", tolerance)
    return dict(transform=base @ camera, base_orthonormalisation=base_error,
                camera_orthonormalisation=camera_error)


def camera_origin_in_body(T_body_camera: Iterable[Iterable[float]]) -> np.ndarray:
    return _se3(T_body_camera, "T_body_camera")[0][:3, 3].copy()


def support_tilt_deg(T_body_camera: Iterable[Iterable[float]],
                     normal_camera: Sequence[float]) -> float:
    """Angle between a depth-frame surface normal and BODY +Z, in degrees.

    A support surface that is level in the cell must be level in BODY, so this
    number is a property of the physical site rather than of the transform. It
    constrains the two tilt degrees of freedom; yaw about the vertical is left
    free and has to be pinned by a separate observation.
    """
    transform = _se3(T_body_camera, "T_body_camera")[0]
    normal = np.asarray(normal_camera, dtype=float)
    if normal.shape != (3,) or not np.isfinite(normal).all():
        raise ValueError("a finite three-vector normal is required")
    norm = float(np.linalg.norm(normal))
    if norm < 1e-12:
        raise ValueError("zero normal has no direction")
    mapped = transform[:3, :3] @ (normal / norm)
    cosine = float(np.clip(abs(float(mapped @ BODY_UP)), -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def ground_height_m(points_body: np.ndarray, half_width_m: float = 0.08) -> dict:
    """Height of the ground as seen in BODY, from points near z = 0.

    Reports the population and flatness as well, because a median taken from a
    handful of stray points would look like agreement while proving nothing.
    """
    points = np.asarray(points_body, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("points must be an (n, 3) array")
    if not len(points):
        raise ValueError("no points to measure the ground with")
    band = points[np.abs(points[:, 2]) <= float(half_width_m)]
    if not len(band):
        return dict(point_count=0, median_z_m=None, spread_m=None, fraction=0.0)
    return dict(point_count=int(len(band)),
                median_z_m=float(np.median(band[:, 2])),
                spread_m=float(np.std(band[:, 2])),
                fraction=float(len(band) / len(points)))


def dominant_plane(points_camera: np.ndarray, threshold_m: float = 0.01,
                   iterations: int = 4000, seed: int = 0) -> dict:
    """Largest planar cluster in a depth frame, by RANSAC then a PCA refit.

    The normal is oriented away from the sensor origin, which is the convention
    :func:`support_tilt_deg` expects: the plane sign has to be pinned by the
    measurement rather than left to chance.
    """
    points = np.asarray(points_camera, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
        raise ValueError("at least three (x, y, z) points are required")
    if not np.isfinite(points).all():
        raise ValueError("plane fitting requires finite points")
    rng = np.random.default_rng(seed)
    best_count, best = -1, None
    for _ in range(int(iterations)):
        sample = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-12:
            continue
        normal = normal / norm
        offset = -float(normal @ sample[0])
        count = int(np.count_nonzero(np.abs(points @ normal + offset) < threshold_m))
        if count > best_count:
            best_count, best = count, (normal, offset)
    if best is None:
        raise ValueError("no plane could be fitted")
    normal, offset = best
    inliers = points[np.abs(points @ normal + offset) < threshold_m]
    centre = inliers.mean(axis=0)
    _, _, vectors = np.linalg.svd(inliers - centre, full_matrices=False)
    normal = vectors[2] / float(np.linalg.norm(vectors[2]))
    if float(normal @ centre) > 0.0:
        normal = -normal  # point the normal back toward the sensor origin
    return dict(normal=normal, centre=centre, point_count=int(len(inliers)),
                inlier_ratio=float(len(inliers) / len(points)))


def body_camera_verdict(tilt_deg: float, ground: Mapping[str, object],
                        max_tilt_deg: float, max_ground_offset_m: float,
                        min_ground_points: int) -> str:
    """One sentence that says whether the transform earned its commission."""
    if tilt_deg > max_tilt_deg:
        return ("拒绝：水平面在 BODY 中倾斜 %.3f deg，超出 %.3f deg，"
                "旋转部分不成立" % (tilt_deg, max_tilt_deg))
    if int(ground.get("point_count", 0)) < min_ground_points:
        return ("拒绝：地面只取到 %s 个点，不足以判定 z 平移"
                % ground.get("point_count"))
    offset = ground.get("median_z_m")
    if offset is None or abs(float(offset)) > max_ground_offset_m:
        return ("拒绝：地面落在 BODY z = %s m，偏离 0 超过 %.3f m，"
                "z 平移不成立" % (offset, max_ground_offset_m))
    return ("通过：水平面倾斜 %.3f deg（<= %.3f），地面在 BODY z = %.4f m "
            "（%d 点，平面度 ±%.4f m），偏离 0 在 %.3f m 以内"
            % (tilt_deg, max_tilt_deg, float(offset), int(ground["point_count"]),
               float(ground["spread_m"]), max_ground_offset_m))


def commission_record(T_body_base, T_base_camera, *, arm: str,
                      handeye_revision: str, tilt_deg: float,
                      ground: Mapping[str, object], verdict: str,
                      evidence: Mapping[str, object],
                      recorded_at: str = "") -> dict:
    """Immutable record of one commissioning, including how it was checked.

    ``recorded_at`` is a sibling of the revision rather than part of it: a
    revision that changed every time the same measurement was re-recorded would
    identify the moment instead of the transform, and could not be cited.
    """
    composed = compose_body_camera(T_body_base, T_base_camera)
    transform = composed["transform"]
    carried = dict(evidence)
    carried["arm"] = arm
    carried["handeye_revision"] = handeye_revision
    carried["tilt_deg"] = round(float(tilt_deg), 6)
    carried["ground"] = dict(ground)
    carried["verdict"] = verdict
    return dict(schema_version=1, kind="body_camera_commission", arm=arm,
                T_body_camera=[list(row) for row in transform.round(12)],
                camera_origin_body_m=list(camera_origin_in_body(transform)),
                translation_unit="m",
                revision=canonical_transform_revision(transform, carried),
                checks=dict(support_tilt_deg=round(float(tilt_deg), 6),
                            ground=dict(ground),
                            orthonormalisation_max_element=round(
                                max(float(composed["base_orthonormalisation"]),
                                    float(composed["camera_orthonormalisation"])), 12)),
                verdict=verdict, recorded_at=recorded_at, evidence=carried)
