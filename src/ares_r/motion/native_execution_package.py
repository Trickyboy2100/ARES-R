"""Offline, fail-closed P3.3 packaging for the existing right ServoJ sender.

This module only prepares bytes for its ARES_R_RIGHT_V1 file contract. It
never starts the native bridge, enables servo mode, or mints a SafetyPermit.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from ares_r.motion.native_demo import (
    NATIVE_MAX_JOINT_ACCEL_RAD_S2, NATIVE_MAX_JOINT_SPEED_RAD_S,
    NATIVE_TRACKING_BUDGET_DEG, NATIVE_TRACKING_SPEED_CAP_RAD_S,
    SUPERVISED_HARD_TRACKING_GATE_DEG, SUPERVISED_TRACKING_BUDGET_DEG,
    SUPERVISED_TRACKING_SPEED_CAP_RAD_S, SUPERVISED_MAX_JOINT_SPEED_RAD_S,
    SUPERVISED_MAX_JOINT_ACCEL_RAD_S2,
    native_move_violations, predicted_tracking_gate_deg, resample_for_native,
)

NATIVE_DT_S = 0.08
NATIVE_MAX_DURATION_S = 240.0
NATIVE_MAX_SAMPLES = 10000
NATIVE_MAX_EXCURSION_RAD = math.radians(150)
# Supervised A/B preview ceiling; the separate generic native-demo cap remains
# unchanged. This does not certify a particular path for physical execution.
FIRST_DEMO_SPEED_RAD_S = SUPERVISED_MAX_JOINT_SPEED_RAD_S
FIRST_DEMO_ACCEL_RAD_S2 = SUPERVISED_MAX_JOINT_ACCEL_RAD_S2
# Built from the explicit supervised_path source with the site SDK.  The old
# demo/pregrasp binary is intentionally not accepted for an A/B package.
AUDITED_SITE_SENDER_SHA256 = "0d5de69b6b277a8f585232ced8a035eebb568dad60f66365cc4edc810f237dac"


def verify_installed_sender(path):
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != AUDITED_SITE_SENDER_SHA256:
        raise ValueError("native sender binary differs from audited source build")
    return actual


def _geometry_error(source, sampled):
    """Worst distance from resampled points to the original joint polyline."""
    import numpy as np
    a = np.asarray(source[:-1], dtype=float)
    b = np.asarray(source[1:], dtype=float)
    delta = b - a
    denom = np.maximum(np.sum(delta * delta, axis=1), 1e-30)
    worst = 0.0
    for start in range(0, len(sampled), 256):
        q = np.asarray(sampled[start:start + 256], dtype=float)
        relative = q[:, None, :] - a[None, :, :]
        fraction = np.clip(np.einsum("nkd,kd->nk", relative, delta) / denom, 0, 1)
        nearest = a[None, :, :] + fraction[:, :, None] * delta[None, :, :]
        distance = np.linalg.norm(q[:, None, :] - nearest, axis=-1)
        worst = max(worst, float(np.min(distance, axis=1).max()))
    return worst


def package_native_preview(points, source_dt_s, site_limits, *, tool_id,
                           controller_tool_pose_mm_rad, captured_at_unix,
                           max_duration_s=NATIVE_MAX_DURATION_S,
                           speed_ceiling_rad_s=FIRST_DEMO_SPEED_RAD_S,
                           accel_ceiling_rad_s2=FIRST_DEMO_ACCEL_RAD_S2,
                           tracking_stop_threshold_deg=SUPERVISED_HARD_TRACKING_GATE_DEG):
    """Return native file text and audit, or raise without writing a file."""
    source = [[float(v) for v in row] for row in points]
    if (len(source) < 2 or any(len(row) != 6 or not all(math.isfinite(v) for v in row)
                               for row in source)):
        raise ValueError("finite six-joint cuRobo path required")
    if len(controller_tool_pose_mm_rad) != 6 or not all(
            math.isfinite(float(v)) for v in controller_tool_pose_mm_rad):
        raise ValueError("valid controller tool pose required")
    lower = [float(v) for v in site_limits["lower_rad"]]
    upper = [float(v) for v in site_limits["upper_rad"]]
    soft = float(site_limits["soft_limit_margin_rad"])
    if not 0 < speed_ceiling_rad_s <= FIRST_DEMO_SPEED_RAD_S or not 0 < accel_ceiling_rad_s2 <= FIRST_DEMO_ACCEL_RAD_S2:
        raise ValueError("supervised sender speed/acceleration ceiling exceeded")
    if not 0 < tracking_stop_threshold_deg <= SUPERVISED_HARD_TRACKING_GATE_DEG:
        raise ValueError("A/B tracking stop threshold outside versioned site maximum")
    speed = [min(float(site_limits["max_velocity_rad_s"][i]),
                 SUPERVISED_MAX_JOINT_SPEED_RAD_S, SUPERVISED_TRACKING_SPEED_CAP_RAD_S,
                 speed_ceiling_rad_s) for i in range(6)]
    accel = [min(float(site_limits["max_acceleration_rad_s2"][i]),
                 NATIVE_MAX_JOINT_ACCEL_RAD_S2, accel_ceiling_rad_s2)
             for i in range(6)]
    if not 0 < max_duration_s <= NATIVE_MAX_DURATION_S:
        raise ValueError("cannot exceed 240 s native reposition duration")
    sampled = resample_for_native(source, float(source_dt_s), NATIVE_DT_S,
                                  speed, accel, max_duration_s=max_duration_s)
    duration = (len(sampled) - 1) * NATIVE_DT_S
    if len(sampled) > NATIVE_MAX_SAMPLES or duration > NATIVE_MAX_DURATION_S:
        raise ValueError("native point/duration cap")
    if sampled[0] != source[0] or sampled[-1] != source[-1]:
        raise ValueError("time scaling changed path endpoints")
    geometry_error = _geometry_error(source, sampled)
    if geometry_error > 1e-8:
        raise ValueError("time scaling changed joint-path geometry")
    excursion = max(abs(value - source[0][joint])
                    for row in sampled for joint, value in enumerate(row))
    if excursion > NATIVE_MAX_EXCURSION_RAD:
        raise ValueError("native 150-degree per-joint excursion cap")
    for row in sampled:
        if any(row[i] < lower[i] + soft or row[i] > upper[i] - soft for i in range(6)):
            raise ValueError("site soft joint limit")
    violations = native_move_violations(sampled, NATIVE_DT_S, speed, accel)
    if violations:
        raise ValueError("native velocity/acceleration cap: %s" % violations[:3])
    predicted_tracking = predicted_tracking_gate_deg(sampled, NATIVE_DT_S)
    tracking_budget=min(SUPERVISED_TRACKING_BUDGET_DEG,tracking_stop_threshold_deg-.02)
    if predicted_tracking > tracking_budget + 1e-9:
        raise ValueError("predicted native tracking budget")
    rows = ["ARES_R_RIGHT_V2 %d %.17g %d %d %.17g %.17g %.17g" % (
                len(sampled), NATIVE_DT_S, int(captured_at_unix), int(tool_id),
                speed_ceiling_rad_s,accel_ceiling_rad_s2,tracking_stop_threshold_deg),
            " ".join("%.17g" % float(v) for v in controller_tool_pose_mm_rad),
            " ".join("%.17g" % (v + soft) for v in lower),
            " ".join("%.17g" % (v - soft) for v in upper)]
    rows.extend(" ".join("%.17g" % value for value in row) for row in sampled)
    content = "\n".join(rows) + "\n"
    velocity = max(abs(b[i]-a[i]) / NATIVE_DT_S
                   for a, b in zip(sampled, sampled[1:]) for i in range(6))
    acceleration = max(abs((sampled[j][i]-sampled[j-1][i]) / NATIVE_DT_S
                           - (sampled[j-1][i]-sampled[j-2][i]) / NATIVE_DT_S)
                       / NATIVE_DT_S for j in range(2, len(sampled)) for i in range(6))
    audit = {
        "format": "ARES_R_RIGHT_V2", "native_sender_mode_for_future_review": "supervised_path",
        "planning_only": True, "execution_allowed": False,
        "sample_period_s": NATIVE_DT_S, "sample_count": len(sampled),
        "duration_s": duration, "max_joint_speed_rad_s": velocity,
        "max_joint_accel_rad_s2": acceleration,
        "speed_cap_rad_s": min(speed), "accel_cap_rad_s2": min(accel),
        "tracking_speed_cap_rad_s": SUPERVISED_TRACKING_SPEED_CAP_RAD_S,
        "predicted_tracking_gate_deg": predicted_tracking,
        "tracking_budget_deg": tracking_budget,
        "tracking_margin_deg": tracking_budget-predicted_tracking,
        "native_sender_hard_tracking_gate_deg": tracking_stop_threshold_deg,
        "predicted_margin_to_sender_hard_gate_deg": tracking_stop_threshold_deg-predicted_tracking,
        "max_excursion_rad": excursion,
        "max_joint_geometry_error_rad": geometry_error,
        "native_file_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "source_point_count": len(source),
        "source_endpoints_preserved": True,
    }
    return content, audit
