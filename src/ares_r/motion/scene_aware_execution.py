"""Native packaging and hard-only preflight for SceneAwareMotionService."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from .execution_candidate import digest, trajectory_hash
from .live_state import base_stationarity
from .native_execution_package import package_native_preview, verify_installed_sender
from .safety_kernel import DualArmSafetyKernel


ROOT = Path(__file__).resolve().parents[3]
SENDER = Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v5")
JOINT_MATCH_RAD = math.radians(.02)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class GenericNativePackager:
    def __init__(self, config, profile):
        self.config = config
        self.profile = profile

    def __call__(self, motion, scene, output, plan, hard_validity):
        if motion.arm != "right":
            raise RuntimeError("left native SceneAware executor is not commissioned")
        speed = self.profile["speed_profiles"].get(motion.speed_profile)
        if speed is None:
            raise RuntimeError("unknown scene-aware speed profile")
        if (speed["scope"] == "RIGHT_ARM_AB_DEMO_ONLY" and
                not motion.request_label.startswith("AB_DEMO_")):
            raise RuntimeError("A/B commissioned speed cannot be used by another motion client")
        if (speed["scope"] == "RIGHT_ARM_SCENE_AWARE_FREE_SPACE" and
                (motion.arm != "right" or motion.goal is None)):
            raise RuntimeError("generic free-space speed requires a right-arm runtime MotionGoal")
        output = Path(output)
        request = _load(output / "planner_request.json")
        scene_root = Path(scene["scene_dir"])
        audit = _load(scene_root / "right_fk_audit.json")["diagnostics"]
        report = _load(scene_root / "scene/scene_report.json")
        capture = _load(_load(scene_root / "capture_pointer.json")["capture_manifest"])
        site = _load(ROOT / "config/jaka_mini2_motion.site.json")
        velocity = float(speed["max_velocity_rad_s"])
        acceleration = float(speed["max_acceleration_rad_s2"])
        if speed["scope"] == "RIGHT_ARM_AB_DEMO_ONLY":
            site = dict(site)
            site["max_velocity_rad_s"] = [max(float(v), velocity)
                                          for v in site["max_velocity_rad_s"]]
        native_text, native_audit = package_native_preview(
            plan["trajectory_points_rad"], plan["smoothness"]["sample_period_s"], site,
            tool_id=audit["tool_id"],
            controller_tool_pose_mm_rad=audit["tool_data"]["pose_mm_rad"],
            captured_at_unix=float(capture["captured_at_unix"]),
            speed_ceiling_rad_s=velocity,
            accel_ceiling_rad_s2=acceleration,
            tracking_stop_threshold_deg=float(speed["tracking_stop_threshold_deg"]))
        package = output / "native_package"
        package.mkdir(exist_ok=False)
        (package / "native_preview.txt").write_text(native_text)
        _write(package / "native_audit.json", native_audit)
        path_hash = trajectory_hash(plan["trajectory_points_rad"],
                                    plan["smoothness"]["sample_period_s"])
        payload = {
            "schema_version": 2,
            "motion_contract": "SCENE_AWARE_FREE_SPACE_V1",
            "motion_policy": "CUROBO_DIRECT_START_GOAL",
            "explicit_waypoints": [],
            "arm": motion.arm,
            "request_label": motion.request_label,
            "runtime_motion_goal": plan.get("runtime_motion_goal"),
            "orientation_validation": plan.get("orientation_validation"),
            "actual_start_joints_rad": audit["joint_position_rad"],
            "planned_start_joints_rad": plan["start_rad"],
            "destination_joints_rad": plan["goal_rad"],
            "scene_epoch": scene["scene_epoch"],
            "base_pose_revision": scene["base_pose_revision"],
            "scene_snapshot_id": scene["scene_snapshot_id"],
            "scene_digest": scene["scene_digest"],
            "pointcloud_sha256": scene["pointcloud_sha256"],
            "calibration_revision": scene["calibration_revision"],
            "whole_robot_geometry_revision": scene["geometry_revision"],
            "inactive_arm_revision": report["inactive_arm_revision"],
            "tool_revision": scene["tool_revision"],
            "controller_tool_id": audit["tool_id"],
            "controller_tool_pose_mm_rad": audit["tool_data"]["pose_mm_rad"],
            "execution_tool_envelope_revision": plan["execution_tool_envelope_revision"],
            "planner_profile_revision": self.profile["planner"]["profile_revision"],
            "planner_clearance_policy": plan["planner_clearance_policy"],
            "hard_validity": hard_validity,
            "trajectory_hash": path_hash,
            "native_trajectory_hash": native_audit["native_file_sha256"],
            "native_sender_binary_sha256": verify_installed_sender(SENDER),
            "native_duration_s": native_audit["duration_s"],
            "speed_profile": motion.speed_profile,
            "speed_profile_revision": self.profile["revision"],
            "scene_captured_at_unix": float(capture["captured_at_unix"]),
            "created_at_unix": time.time(),
            "expires_at_unix": time.time() + 300,
            "central_tcp_margin_m": plan["independent_dense_validation"]["central_tcp_margin_m"],
        }
        candidate = dict(payload, candidate_id=digest(payload))
        _write(package / "candidate_manifest.json", candidate)
        return {"package_dir": str(package), "candidate": candidate,
                "native_audit": native_audit}


def _audit_arm(config, output, side):
    model = _load(config["robot_collision"]["model"])
    urdf = Path(model["asset_root"]) / model["urdf"]
    result = subprocess.run(
        ["python3", str(ROOT / "scripts/audit_curobo_fk.py"), str(urdf),
         str(output), "--side", side], cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
        text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError("live %s arm audit failed: %s" % (side, result.stderr[-800:]))
    return _load(output)["diagnostics"]


def preflight(config, local_scene, candidate, native_audit, profile):
    scene = local_scene.snapshot()
    evidence = Path(candidate["package_dir"]) / ("preflight_%d" % time.time_ns())
    evidence.mkdir()
    left = _audit_arm(config, evidence / "left_fk_audit.json", "left")
    right = _audit_arm(config, evidence / "right_fk_audit.json", "right")
    source = Path(scene["scene_dir"])
    old_left = _load(source / "left_fk_audit.json")["diagnostics"]
    left_known = (max(abs(a-b) for a, b in zip(left["joint_position_rad"],
                                                old_left["joint_position_rad"])) <= JOINT_MATCH_RAD
                  and left["tool_id"] == old_left["tool_id"]
                  and left["tool_data"]["pose_mm_rad"] == old_left["tool_data"]["pose_mm_rad"])
    manifest = candidate["candidate"]
    scene_bound = all((scene.get(key) == manifest.get(key)) for key in (
        "scene_epoch", "base_pose_revision", "scene_snapshot_id", "scene_digest",
        "pointcloud_sha256", "calibration_revision", "tool_revision"))
    start_match = max(abs(a-b) for a, b in zip(
        right["joint_position_rad"], manifest["planned_start_joints_rad"])) <= JOINT_MATCH_RAD
    base = base_stationarity(config)
    sender_match = verify_installed_sender(SENDER) == manifest["native_sender_binary_sha256"]
    speed = profile["speed_profiles"][manifest["speed_profile"]]
    gates = {
        "START_MATCH": start_match,
        "SCENE_FRESH": scene_bound and time.time() <= manifest["expires_at_unix"],
        "BASE_STATIONARY": base["stationary"],
        "INACTIVE_ARM_KNOWN": left_known,
        "TOOL_REVISION_MATCH": (
            right["tool_id"] == manifest["controller_tool_id"] and
            right["tool_data"]["pose_mm_rad"] == manifest["controller_tool_pose_mm_rad"]),
        "TRAJECTORY_COLLISION_CHECKED": DualArmSafetyKernel.scene_aware_collision_gate(manifest),
        "CENTRAL_EXCLUSION": manifest["central_tcp_margin_m"] > 0,
        "VELOCITY": native_audit["max_joint_speed_rad_s"] <= speed["max_velocity_rad_s"] + 1e-12,
        "ACCELERATION": native_audit["max_joint_accel_rad_s2"] <= speed["max_acceleration_rad_s2"] + 1e-12,
        "NATIVE_SENDER_LIMITS": (
            sender_match and native_audit["sample_period_s"] == .08 and
            native_audit["native_file_sha256"] == manifest["native_trajectory_hash"]),
        "TRACKING_PREDICTION": (
            native_audit["predicted_tracking_gate_deg"] <=
            speed["tracking_stop_threshold_deg"] + 1e-9),
        "SPEED_PROFILE_COMMISSIONED": str(speed["state"]).startswith("COMMISSIONED"),
        "EXECUTION_ENABLED": False,
    }
    result = {"gates": gates, "blockers": [key for key, value in gates.items() if not value],
              "ready_except_execution_authority": all(value for key, value in gates.items()
                                                       if key != "EXECUTION_ENABLED"),
              "hard_validator_role": "HARD_COLLISION_STATE_BINDING_DYNAMICS_ONLY",
              "preferred_clearance_is_execution_gate": False,
              "base": base, "evidence_dir": str(evidence)}
    _write(evidence / "preflight.json", result)
    return result
