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


def validate_path(fk_body_tcp, joints, *, subdivisions=4, tolerance_deg=MAX_ORIENTATION_ERROR_DEG):
    """Independently check every interpolated joint interval, not just endpoints."""
    rows = np.asarray(joints, dtype=float)
    if rows.ndim != 2 or rows.shape[1] != 6 or len(rows) < 2 or not np.isfinite(rows).all():
        raise ValueError("finite six-joint path with at least two samples required")
    if subdivisions < 1 or not 0.0 < tolerance_deg <= 5.0:
        raise ValueError("invalid orientation validation settings")
    worst_rotation = worst_forward_tilt = worst_finger_tilt = 0.0
    samples = 0
    for i in range(len(rows) - 1):
        for fraction in range(subdivisions):
            q = rows[i] + fraction / subdivisions * (rows[i + 1] - rows[i])
            R = np.asarray(fk_body_tcp(q), dtype=float)[:3, :3]
            if R.shape != (3, 3) or not np.isfinite(R).all():
                raise ValueError("invalid BODY TCP rotation")
            cosine = float(np.clip((np.trace(HORIZONTAL_FORWARD_R_BODY.T @ R) - 1.0) / 2.0, -1.0, 1.0))
            worst_rotation = max(worst_rotation, math.degrees(math.acos(cosine)))
            worst_forward_tilt = max(worst_forward_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 2]))))))
            worst_finger_tilt = max(worst_finger_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 0]))))))
            samples += 1
    R = np.asarray(fk_body_tcp(rows[-1]), dtype=float)[:3, :3]
    cosine = float(np.clip((np.trace(HORIZONTAL_FORWARD_R_BODY.T @ R) - 1.0) / 2.0, -1.0, 1.0))
    worst_rotation = max(worst_rotation, math.degrees(math.acos(cosine)))
    worst_forward_tilt = max(worst_forward_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 2]))))))
    worst_finger_tilt = max(worst_finger_tilt, math.degrees(math.asin(min(1.0, abs(float(R[2, 0]))))))
    return {"passed": worst_rotation <= tolerance_deg,
            "max_orientation_error_deg": worst_rotation,
            "max_forward_tilt_deg": worst_forward_tilt,
            "max_finger_axis_tilt_deg": worst_finger_tilt,
            "tolerance_deg": tolerance_deg,
            "dense_samples": samples + 1,
            "target_R_body_tcp": HORIZONTAL_FORWARD_R_BODY.tolist(),
            "tcp_forward_axis": "+Z", "finger_closing_axis": "X"}
