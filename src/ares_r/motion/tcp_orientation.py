"""BODY-frame fixed-orientation contract for the right A/B demo.

The controller TCP's local +Z is the gripper approach axis.  Local +/-X is
the finger-closing axis; the 180-degree roll branch below keeps that axis
horizontal while reducing the current-to-A joint excursion.  This is a
geometric contract, not a substitute for whole-arm collision validation.
"""

import math

import numpy as np


HORIZONTAL_FORWARD_R_BODY = np.array(
    [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]], dtype=float)
MAX_ORIENTATION_ERROR_DEG = 3.0


def level_rotation(yaw_rad):
    """Return the established level gripper branch at a BODY +Z yaw."""
    c, s = math.cos(float(yaw_rad)), math.sin(float(yaw_rad))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]) @ HORIZONTAL_FORWARD_R_BODY


def tcp_yaw_rad(rotation):
    """Yaw of the TCP +Z approach axis projected onto the BODY plane."""
    rotation = np.asarray(rotation, dtype=float)
    return math.atan2(float(rotation[1, 2]), float(rotation[0, 2]))


def validate_level_path(fk_body_tcp, joints, *, subdivisions=4,
                        tolerance_deg=MAX_ORIENTATION_ERROR_DEG,
                        final_yaw_rad=None):
    """Validate horizontal TCP axes while deliberately allowing BODY yaw."""
    rows = np.asarray(joints, dtype=float)
    if rows.ndim != 2 or rows.shape[1] != 6 or len(rows) < 2 or not np.isfinite(rows).all():
        raise ValueError("finite six-joint path with at least two samples required")
    yaws = []
    worst_forward = worst_finger = 0.0
    for index in range(len(rows) - 1):
        samples = [rows[index] + fraction / subdivisions * (rows[index + 1] - rows[index])
                   for fraction in range(subdivisions)]
        for q in samples:
            rotation = np.asarray(fk_body_tcp(q), dtype=float)[:3, :3]
            worst_forward = max(worst_forward, math.degrees(math.asin(
                min(1.0, abs(float(rotation[2, 2]))))))
            worst_finger = max(worst_finger, math.degrees(math.asin(
                min(1.0, abs(float(rotation[2, 0]))))))
            yaws.append(tcp_yaw_rad(rotation))
    rotation = np.asarray(fk_body_tcp(rows[-1]), dtype=float)[:3, :3]
    worst_forward = max(worst_forward, math.degrees(math.asin(
        min(1.0, abs(float(rotation[2, 2]))))))
    worst_finger = max(worst_finger, math.degrees(math.asin(
        min(1.0, abs(float(rotation[2, 0]))))))
    yaws.append(tcp_yaw_rad(rotation))
    unwrapped = np.unwrap(np.asarray(yaws, dtype=float))
    final_error = None
    if final_yaw_rad is not None:
        final_error = abs(math.degrees(math.atan2(
            math.sin(yaws[-1] - float(final_yaw_rad)),
            math.cos(yaws[-1] - float(final_yaw_rad)))))
    maximum = max(worst_forward, worst_finger)
    passed = maximum <= tolerance_deg and (final_error is None or final_error <= tolerance_deg)
    return {
        "passed": passed,
        "mode": "LEVEL_YAW_TARGET" if final_yaw_rad is not None else "LEVEL_YAW_FREE",
        "max_level_error_deg": maximum,
        "max_forward_tilt_deg": worst_forward,
        "max_finger_axis_tilt_deg": worst_finger,
        "yaw_range_deg": math.degrees(float(unwrapped.max() - unwrapped.min())),
        "final_yaw_deg": math.degrees(float(yaws[-1])),
        "final_yaw_error_deg": final_error,
        "tolerance_deg": tolerance_deg,
        "dense_samples": len(yaws),
        "tcp_forward_axis": "+Z",
        "finger_closing_axis": "X",
    }


def validate_path(fk_body_tcp, joints, *, subdivisions=4,
                  tolerance_deg=MAX_ORIENTATION_ERROR_DEG,
                  target_rotation=HORIZONTAL_FORWARD_R_BODY):
    """Independently check every interpolated joint interval, not just endpoints."""
    rows = np.asarray(joints, dtype=float)
    if rows.ndim != 2 or rows.shape[1] != 6 or len(rows) < 2 or not np.isfinite(rows).all():
        raise ValueError("finite six-joint path with at least two samples required")
    if subdivisions < 1 or not 0.0 < tolerance_deg <= 5.0:
        raise ValueError("invalid orientation validation settings")
    target_rotation = np.asarray(target_rotation, dtype=float)
    if (target_rotation.shape != (3, 3) or not np.isfinite(target_rotation).all() or
            not np.allclose(target_rotation.T @ target_rotation, np.eye(3), atol=1e-5) or
            not np.isclose(np.linalg.det(target_rotation), 1.0, atol=1e-5)):
        raise ValueError("target orientation must be a proper 3x3 rotation")
    worst_rotation = worst_forward_tilt = worst_finger_tilt = 0.0
    samples = 0
    for i in range(len(rows) - 1):
        for fraction in range(subdivisions):
            q = rows[i] + fraction / subdivisions * (rows[i + 1] - rows[i])
            R = np.asarray(fk_body_tcp(q), dtype=float)[:3, :3]
            if R.shape != (3, 3) or not np.isfinite(R).all():
                raise ValueError("invalid BODY TCP rotation")
            cosine = float(np.clip((np.trace(target_rotation.T @ R) - 1.0) / 2.0, -1.0, 1.0))
            worst_rotation = max(worst_rotation, math.degrees(math.acos(cosine)))
            worst_forward_tilt = max(worst_forward_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 2]))))))
            worst_finger_tilt = max(worst_finger_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 0]))))))
            samples += 1
    R = np.asarray(fk_body_tcp(rows[-1]), dtype=float)[:3, :3]
    cosine = float(np.clip((np.trace(target_rotation.T @ R) - 1.0) / 2.0, -1.0, 1.0))
    worst_rotation = max(worst_rotation, math.degrees(math.acos(cosine)))
    worst_forward_tilt = max(worst_forward_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 2]))))))
    worst_finger_tilt = max(worst_finger_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 0]))))))
    return {"passed": worst_rotation <= tolerance_deg,
            "max_orientation_error_deg": worst_rotation,
            "max_forward_tilt_deg": worst_forward_tilt,
            "max_finger_axis_tilt_deg": worst_finger_tilt,
            "tolerance_deg": tolerance_deg,
            "dense_samples": samples + 1,
            "target_R_body_tcp": target_rotation.tolist(),
            "tcp_forward_axis": "+Z", "finger_closing_axis": "X"}
