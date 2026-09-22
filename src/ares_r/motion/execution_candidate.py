"""P3.3 offline trajectory selection and immutable execution-candidate binding.

No function in this module sends controller commands or mints a SafetyPermit.
"""

from __future__ import annotations

import hashlib
import json
import math
import time


MIN_FIRST_DEMO_CLEARANCE_M = 0.030
NATIVE_START_TOLERANCE_RAD = math.radians(0.02)


def digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def trajectory_hash(points, sample_period_s):
    if len(points) < 2 or any(len(row) != 6 or not all(math.isfinite(float(v)) for v in row)
                              for row in points):
        raise ValueError("finite six-axis trajectory required")
    return digest({"points": points, "sample_period_s": float(sample_period_s)})


def trial_summary(plan, *, expected_envelope_revision, minimum_clearance_m=MIN_FIRST_DEMO_CLEARANCE_M):
    """Filter one planned result using its independent dense CPU validation."""
    reasons = []
    validation = plan.get("independent_dense_validation") or {}
    gap = validation.get("min_clearance_m")
    planner_gap = plan.get("clearance_m", {}).get("planned_path")
    smooth = plan.get("smoothness") or (plan.get("ab_demo") or {}).get("smoothness") or {}
    points = plan.get("trajectory_points_rad") or []
    dt = smooth.get("sample_period_s")
    if plan.get("observed_result") != "SUCCESS" or not points:
        reasons.append("PLANNER_OR_POSTVALIDATION_FAILED")
    if plan.get("execution_tool_envelope_revision") != expected_envelope_revision:
        reasons.append("TOOL_ENVELOPE_MISMATCH")
    if validation.get("validator") != "independent_cpu_urdf_sphere_cuboid_v1":
        reasons.append("INDEPENDENT_VALIDATION_MISSING")
    if not validation.get("collision_free") or gap is None or gap < minimum_clearance_m:
        reasons.append("DENSE_CLEARANCE_BELOW_GATE")
    if planner_gap is None or planner_gap < minimum_clearance_m:
        reasons.append("PLANNER_CLEARANCE_BELOW_GATE")
    if validation.get("central_tcp_margin_m", -math.inf) <= 0:
        reasons.append("CENTRAL_EXCLUSION")
    if dt is None or dt <= 0 or smooth.get("max_joint_step_rad", math.inf) > 0.15:
        reasons.append("DYNAMICS_DISCONTINUITY")
    if any(not math.isfinite(float(smooth.get(key, math.inf))) for key in (
            "max_joint_speed_rad_s", "max_joint_accel_rad_s2", "max_joint_jerk_rad_s3")):
        reasons.append("SMOOTHNESS_METRICS_MISSING")
    length = plan.get("path_metrics", {}).get("path_length_m")
    if length is None or not math.isfinite(length) or length <= 0:
        reasons.append("INVALID_PATH_LENGTH")
    value = {
        "trajectory_hash": trajectory_hash(points, dt) if points and dt else None,
        "accepted": not reasons, "rejections": reasons,
        "independent_clearance_m": gap, "planner_clearance_m": planner_gap,
        "limiting_object_id": validation.get("limiting_object_id"),
        "path_length_m": length,
        "max_tcp_z_m": ((plan.get("ab_demo") or {}).get("max_tcp_z_m")
                        or (max((row[2] for row in plan.get("tcp_path_body_m", [])), default=None))),
        "max_joint_step_rad": smooth.get("max_joint_step_rad"),
        "max_joint_speed_rad_s": smooth.get("max_joint_speed_rad_s"),
        "max_joint_accel_rad_s2": smooth.get("max_joint_accel_rad_s2"),
        "max_joint_jerk_rad_s3": smooth.get("max_joint_jerk_rad_s3"),
        "planning_time_s": (plan.get("timing_s", {}).get("planning_samples") or [None])[-1],
        "scene_snapshot_id": plan.get("scene_snapshot_id"),
        "active_collision_revision": plan.get("active_collision_revision"),
    }
    return value


def select_reproducible_candidate(trials, *, minimum_repeats=3):
    """Fail closed unless every repeat passed; then rank deterministically."""
    if len(trials) < minimum_repeats or any(not row["accepted"] for row in trials):
        return None
    scene_ids = {row["scene_snapshot_id"] for row in trials}
    geometry = {row["active_collision_revision"] for row in trials}
    if len(scene_ids) != 1 or len(geometry) != 1:
        return None
    return sorted(trials, key=lambda row: (
        -min(row["independent_clearance_m"], row["planner_clearance_m"]),
        row["path_length_m"], row["max_joint_jerk_rad_s3"],
        row["trajectory_hash"]))[0]


def make_candidate_manifest(*, plan, selection, scene_report, pointcloud_sha256,
                            actual_start_joints_rad, tool_id, controller_tool_pose_mm_rad,
                            planner_profile_revision, timing_profile_revision,
                            native_trajectory_hash, native_duration_s,
                            native_sender_binary_sha256,
                            expected_destination, scene_captured_at_unix,
                            created_at_unix=None, ttl_s=300):
    smooth = plan.get("smoothness") or (plan.get("ab_demo") or {}).get("smoothness") or {}
    if not selection or selection["trajectory_hash"] != trajectory_hash(
            plan["trajectory_points_rad"], smooth["sample_period_s"]):
        raise ValueError("selected exact trajectory mismatch")
    if not 0 < ttl_s <= 300:
        raise ValueError("candidate TTL exceeds native freshness bound")
    if expected_destination not in ("A", "B"):
        raise ValueError("expected A/B destination required")
    now = time.time() if created_at_unix is None else float(created_at_unix)
    payload = {
        "schema_version": 1, "execution_allowed": False,
        "motion_policy": "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG",
        "explicit_waypoints": [],
        "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
        "arm": "right", "actual_start_joints_rad": list(actual_start_joints_rad),
        "planned_start_joints_rad": plan["start_rad"],
        "destination_joints_rad": plan["goal_rad"],
        "scene_snapshot_id": plan["scene_snapshot_id"],
        "scene_digest": plan["scene_digest"],
        "pointcloud_sha256": pointcloud_sha256,
        "T_body_camera_revision": scene_report["calibration_revision"]["T_body_camera"],
        "whole_robot_geometry_revision": scene_report["geometry_revision"],
        "inactive_left_arm_revision": scene_report["inactive_arm_revision"],
        "tool_revision": scene_report["tool_revision"],
        "controller_tool_id": int(tool_id),
        "controller_tool_pose_mm_rad": list(controller_tool_pose_mm_rad),
        "execution_tool_envelope_revision": plan["execution_tool_envelope_revision"],
        "planner_profile_revision": planner_profile_revision,
        "trajectory_hash": selection["trajectory_hash"],
        "native_trajectory_hash": native_trajectory_hash,
        "native_sender_binary_sha256": native_sender_binary_sha256,
        "timing_profile_revision": timing_profile_revision,
        "native_duration_s": native_duration_s,
        "dense_min_clearance_m": selection["independent_clearance_m"],
        "central_tcp_margin_m": plan["independent_dense_validation"]["central_tcp_margin_m"],
        "expected_destination": expected_destination,
        "scene_captured_at_unix": float(scene_captured_at_unix),
        "created_at_unix": now, "expires_at_unix": now + ttl_s,
    }
    return dict(payload, candidate_id=digest(payload))


def candidate_binding_reasons(candidate, live, *, now=None):
    """Return all stale/mismatched bindings; never silently rebind a candidate."""
    now = time.time() if now is None else float(now)
    reasons = []
    if now > candidate["expires_at_unix"] or now < candidate["created_at_unix"]:
        reasons.append("EXPIRED")
    keys = ("scene_snapshot_id", "scene_digest", "pointcloud_sha256",
            "T_body_camera_revision", "whole_robot_geometry_revision",
            "inactive_left_arm_revision", "tool_revision", "controller_tool_id",
            "controller_tool_pose_mm_rad", "execution_tool_envelope_revision",
            "planner_profile_revision", "trajectory_hash", "native_trajectory_hash",
            "timing_profile_revision", "native_sender_binary_sha256")
    reasons.extend(key.upper() + "_CHANGED" for key in keys if live.get(key) != candidate.get(key))
    joints = live.get("actual_start_joints_rad")
    if joints is None or len(joints) != 6:
        reasons.append("START_MISMATCH")
        reasons.append("ACTUAL_START_CHANGED")
    else:
        if max(abs(float(a)-float(b)) for a, b in zip(
                joints, candidate["planned_start_joints_rad"])) > NATIVE_START_TOLERANCE_RAD:
            reasons.append("START_MISMATCH")
        if max(abs(float(a)-float(b)) for a, b in zip(
                joints, candidate["actual_start_joints_rad"])) > NATIVE_START_TOLERANCE_RAD:
            reasons.append("ACTUAL_START_CHANGED")
    return reasons


def make_execution_lease_draft(candidate):
    """Bind resources without acquiring a live lock or granting authority."""
    payload = {"schema_version": 1, "state": "DRY_RUN_UNISSUED",
               "execution_allowed": False,
               "candidate_id": candidate["candidate_id"],
               "scene_snapshot_id": candidate["scene_snapshot_id"],
               "trajectory_hash": candidate["trajectory_hash"],
               "locked_resources_if_issued": ["RIGHT_ARM", "CENTER_SHARED", "BASE_STATIONARY",
                                              "LEFT_ARM_STATE", "CAMERA_CALIBRATION"],
               "expires_at_unix": candidate["expires_at_unix"],
               "invalidated_by": ["arrival", "stop", "fault", "scene_change",
                                  "base_move", "left_arm_move", "tool_change",
                                  "start_joint_change", "timeout", "process_restart"]}
    return dict(payload, lease_id=digest(payload))
