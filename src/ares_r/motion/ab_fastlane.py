"""P3.3A CLEAR-only ART backend. No function can execute a trajectory.

The mutable session pointer is merely a convenience; immutable scan, plan,
native-preview and preflight artifacts carry the authoritative provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from types import SimpleNamespace
from urllib.request import urlopen

from .execution_candidate import (digest, make_candidate_manifest,
                                  make_execution_lease_draft, trial_summary)
from .native_execution_package import package_native_preview, verify_installed_sender
from .safety_kernel import DualArmSafetyKernel

ROOT = Path(__file__).resolve().parents[3]
SEARCH = ROOT / "config/ab_demo_horizontal_forward.json"
SENDER = Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v5")
STATE = ROOT / "logs/ab_fastlane_session.json"
ACTIVE_NATIVE = ROOT / "logs/ab_native_active.json"
EVIDENCE = ROOT / "worklog/evidence/2026-09-22-p3-3a-clear-fastlane"
JOINT_MATCH_RAD = math.radians(0.02)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _run(command, *, timeout=300):
    result = subprocess.run([str(arg) for arg in command], cwd=ROOT,
                            env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), text=True,
                            capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("read-only/planning subprocess failed: %s\n%s" %
                           (command[1], (result.stderr or result.stdout)[-1500:]))
    return result.stdout


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def status():
    session = read_json(STATE) if STATE.exists() else {"state": "IDLE"}
    return dict(session, execution_enabled=False,
                motion_policy="CUROBO_DIRECT_START_GOAL", explicit_waypoints=[])


def scan(config):
    """Capture one new box-free scene; never reuse a previous scene pointer."""
    destination = EVIDENCE / ("art_scan_" + _stamp())
    python = config["epic_pointcloud"]["body_cloud_viewer_python"]
    # Camera acquisition itself invalidates the old scene, even if a later
    # JAKA state read or cloud process fails.
    write_json(STATE, {"state": "SCANNING", "candidate_id": None,
                       "plan_dir": None, "scene_dir": None, "execution_enabled": False})
    try:
        _run((python, ROOT / "scripts/p32_scan_scene.py", "--mode", "CLEAR",
              "--output", destination, "--open3d-python", python), timeout=240)
    except Exception:
        write_json(STATE, {"state": "SCENE_INVALID", "candidate_id": None,
                           "failed_capture_dir": str(destination),
                           "execution_enabled": False})
        raise
    result = read_json(destination / "fresh_scene_summary.json")
    session = {"state": "SCENE_READY", "scene_dir": str(destination),
               "scene_snapshot_id": result["snapshot_id"], "plan_dir": None,
               "candidate_id": None, "scanned_at_unix": time.time()}
    write_json(STATE, session)
    return status()


def _direction(scene_dir):
    actual = read_json(scene_dir / "right_fk_audit.json")["diagnostics"]["joint_position_rad"]
    target = read_json(SEARCH)["candidates"][0]
    def at(name):
        return max(abs(a-b) for a, b in zip(actual, target[name + "_joints_rad"])) <= JOINT_MATCH_RAD
    if at("A"):
        return "A_to_B"
    if at("B"):
        return "B_to_A"
    return "CURRENT_to_A"


def prepare_plan(scene_dir, plan_dir, speed_ceiling_rad_s=None):
    """Package exactly one already planned cuRobo path, with leg-specific gate."""
    scene_dir, plan_dir = Path(scene_dir), Path(plan_dir)
    plan = read_json(plan_dir / "planning.json")
    request = read_json(plan_dir / "planner_request.json")
    report = read_json(scene_dir / "scene/scene_report.json")
    contract = read_json(plan_dir / "ab_plan_contract.json")
    direction = contract["direction"]
    if direction in ("A_to_B", "B_to_A"):
        orientation = plan.get("orientation_validation") or {}
        if orientation.get("passed") is not True:
            raise ValueError("horizontal BODY-forward TCP orientation failed: %s" % orientation)
    gate = 0.030
    envelope = request["execution_tool_envelope"]
    selected = trial_summary(plan, expected_envelope_revision=envelope["revision"],
                             minimum_clearance_m=gate)
    if not selected["accepted"]:
        raise ValueError("P3.3A dense clearance/dynamics rejected: %s" % selected["rejections"])
    if request["point_to_point_policy"]["explicit_waypoints"] != []:
        raise ValueError("explicit waypoint forbidden")
    audit = read_json(scene_dir / "right_fk_audit.json")["diagnostics"]
    capture = read_json(read_json(scene_dir / "capture_pointer.json")["capture_manifest"])
    captured_at = float(capture["captured_at_unix"])
    site = read_json(ROOT / "config/jaka_mini2_motion.site.json")
    deployment=read_json(ROOT/"config/ab_demo_deployment_profile.json")
    tracking_stop=float(deployment["motion"]["tracking_stop_threshold_deg"])
    speed_cap=(0.015 if direction=="CURRENT_to_A" else
               float(speed_ceiling_rad_s if speed_ceiling_rad_s is not None else .070))
    accel_cap=0.03 if direction=="CURRENT_to_A" else .20
    if direction != "CURRENT_to_A":
        # Operator-authorized A/B commissioning override. Keep the generic
        # site profile untouched; only this supervised package may use it.
        site = dict(site)
        site["max_velocity_rad_s"] = [max(float(value), speed_cap)
                                      for value in site["max_velocity_rad_s"]]
    native_text, native_audit = package_native_preview(
        plan["trajectory_points_rad"], plan["smoothness"]["sample_period_s"], site,
        tool_id=audit["tool_id"],
        controller_tool_pose_mm_rad=audit["tool_data"]["pose_mm_rad"],
        captured_at_unix=captured_at,
        speed_ceiling_rad_s=speed_cap,accel_ceiling_rad_s2=accel_cap,
        tracking_stop_threshold_deg=tracking_stop)
    sender_hash = verify_installed_sender(SENDER)
    destination = plan_dir / "supervised_path_package_v5"
    if destination.exists():
        raise FileExistsError("package cannot overwrite a previewed trajectory")
    destination.mkdir()
    (destination / "native_preview.txt").write_text(native_text)
    write_json(destination / "native_audit.json", native_audit)
    timing = digest({"sample_period_s": native_audit["sample_period_s"],
                     "speed_cap_rad_s": native_audit["speed_cap_rad_s"],
                     "accel_cap_rad_s2": native_audit["accel_cap_rad_s2"],
                     "native_sender_mode": "supervised_path"})
    candidate = make_candidate_manifest(
        plan=plan, selection=selected, scene_report=report,
        pointcloud_sha256=report["pointcloud_sha256"],
        actual_start_joints_rad=audit["joint_position_rad"], tool_id=audit["tool_id"],
        controller_tool_pose_mm_rad=audit["tool_data"]["pose_mm_rad"],
        planner_profile_revision=digest(request["planning_parameters"]),
        timing_profile_revision=timing,
        native_trajectory_hash=native_audit["native_file_sha256"],
        native_duration_s=native_audit["duration_s"],
        native_sender_binary_sha256=sender_hash,
        expected_destination="B" if direction == "A_to_B" else "A",
        scene_captured_at_unix=captured_at)
    write_json(destination / "candidate_manifest.json", candidate)
    write_json(destination / "lease_draft.json", make_execution_lease_draft(candidate))
    write_json(destination / "selection.json", selected)
    return {"direction": direction, "package_dir": str(destination),
            "candidate_id": candidate["candidate_id"],
            "trajectory_hash": candidate["trajectory_hash"],
            "dense_clearance_m": selected["independent_clearance_m"],
            "native_duration_s": native_audit["duration_s"],
            "native_speed_rad_s": native_audit["max_joint_speed_rad_s"],
            "native_acceleration_rad_s2": native_audit["max_joint_accel_rad_s2"],
            "tracking_prediction_deg": native_audit["predicted_tracking_gate_deg"]}


def plan_next(config, speed_ceiling_rad_s=None):
    session = status()
    if session["state"] != "SCENE_READY":
        raise RuntimeError("fresh demo ab scan required before every leg")
    scene_dir = Path(session["scene_dir"])
    direction = _direction(scene_dir)
    if direction != "CURRENT_to_A" and read_json(SEARCH).get("leveling_only", False):
        raise RuntimeError("horizontal A/B sweep is uncommissioned; leveling target only")
    output = scene_dir / ("art_" + direction.lower() + "_plan")
    python = config["epic_pointcloud"]["body_cloud_viewer_python"]
    write_json(STATE, dict(session, state="PLANNING", candidate_id=None,
                           plan_dir=None, package_dir=None))
    try:
        _run((python, ROOT / "scripts/run_p32_ab_plan.py", scene_dir / "scene",
              "--audit", scene_dir / "right_fk_audit.json", "--search", SEARCH,
              "--candidate", "0", "--direction", direction, "--policy", "DIRECT",
              "--execution-tool-envelope", "--output", output), timeout=240)
        package = prepare_plan(scene_dir, output,speed_ceiling_rad_s)
    except Exception:
        write_json(STATE, dict(session, state="FAULT", candidate_id=None,
                               plan_dir=None, package_dir=None))
        raise
    write_json(STATE, dict(session, state="PLANNED", plan_dir=str(output),
                           package_dir=package["package_dir"],
                           candidate_id=package["candidate_id"],
                           direction=direction))
    return package


def preview():
    session = status()
    if session.get("state") not in ("PLANNED", "PREVIEWED", "PREFLIGHTED"):
        raise RuntimeError("no fresh packaged trajectory")
    package = Path(session["package_dir"])
    candidate = read_json(package / "candidate_manifest.json")
    audit = read_json(package / "native_audit.json")
    if session["state"] != "PREFLIGHTED":
        write_json(STATE, dict(session, state="PREVIEWED"))
    return {"direction": session["direction"], "candidate_id": candidate["candidate_id"],
            "scene_snapshot_id": candidate["scene_snapshot_id"],
            "trajectory_hash": candidate["trajectory_hash"],
            "clearance_m": candidate["dense_min_clearance_m"],
            "duration_s": audit["duration_s"],
            "speed_rad_s": audit["max_joint_speed_rad_s"],
            "acceleration_rad_s2": audit["max_joint_accel_rad_s2"],
            "tracking_prediction_deg": audit["predicted_tracking_gate_deg"],
            "native_file": str(package / "native_preview.txt"),
            "execution_enabled": False}


def base_stationarity(config, *, count=3, interval_s=1.0,
                      scene_dir=None, evidence_dir=None):
    """Read-only IDLE plus map stability or independent static-cloud check."""
    url = config["base"]["base_url"].rstrip("/") + "/robot/status"
    samples = []
    for index in range(count):
        if index:
            time.sleep(interval_s)
        with urlopen(url, timeout=5) as response:
            item = json.load(response)
        info = item["info"]
        samples.append({"at_unix": time.time(), "x_m": float(info["x"]),
                        "y_m": float(info["y"]), "yaw_deg": float(info["yawNumber"]),
                        "map_id": info["mapId"],
                        "state": item["state"]["current"]["state"],
                        "confidence": info.get("confidence")})
    drift_m = max(math.hypot(row["x_m"]-samples[0]["x_m"],
                             row["y_m"]-samples[0]["y_m"]) for row in samples)
    yaw_drift_deg = max(abs(row["yaw_deg"]-samples[0]["yaw_deg"]) for row in samples)
    idle = all(row["state"] == "IDLE" and row["map_id"] == samples[0]["map_id"]
               for row in samples)
    map_stable = drift_m <= 0.005 and yaw_drift_deg <= 0.1
    cloud = None
    if idle and not map_stable and scene_dir is not None and evidence_dir is not None:
        scene_dir = Path(scene_dir)
        current = scene_dir / "scene/clean_residual.npz"
        current_report = read_json(scene_dir / "scene/scene_report.json")
        prior = sorted((p for p in EVIDENCE.glob("*/scene/clean_residual.npz")
                        if p != current and p.stat().st_mtime < current.stat().st_mtime
                        and read_json(p.parent / "scene_report.json").get("calibration_revision")
                        == current_report.get("calibration_revision")),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if prior:
            output = Path(evidence_dir) / "cloud_stationarity.json"
            python = config["epic_pointcloud"]["body_cloud_viewer_python"]
            _run((python, ROOT / "scripts/check_base_stationary_cloud.py",
                  prior[0], current, "--output", output), timeout=60)
            cloud = read_json(output)
    stationary = bool(idle and (map_stable or (cloud and cloud["stationary"])))
    return {"stationary": stationary, "amr_idle": idle,
            "map_pose_stable": map_stable, "cloud_check": cloud,
            "translation_drift_m": drift_m,
            "yaw_drift_deg": yaw_drift_deg, "samples": samples,
            "method": "AMR IDLE plus map stability OR independent static-scene cloud registration; not safety-rated"}


def preflight(config):
    session = status()
    if session.get("state") not in ("PLANNED", "PREVIEWED", "PREFLIGHTED"):
        raise RuntimeError("previewed package required")
    package = Path(session["package_dir"])
    candidate = read_json(package / "candidate_manifest.json")
    native = read_json(package / "native_audit.json")
    scene_dir = Path(session["scene_dir"])
    model = read_json(config["robot_collision"]["model"])
    urdf = Path(model["asset_root"]) / model["urdf"]
    evidence = package / ("preflight_" + _stamp())
    evidence.mkdir()
    for side in ("left", "right"):
        _run(("python3", ROOT / "scripts/audit_curobo_fk.py", urdf,
              evidence / (side + "_fk_audit.json"), "--side", side), timeout=30)
    left = read_json(evidence / "left_fk_audit.json")["diagnostics"]
    right = read_json(evidence / "right_fk_audit.json")["diagnostics"]
    old_left = read_json(scene_dir / "left_fk_audit.json")["diagnostics"]
    left_unchanged = max(abs(a-b) for a, b in zip(
        left["joint_position_rad"], old_left["joint_position_rad"])) <= JOINT_MATCH_RAD
    left_unchanged &= (left["tool_id"] == old_left["tool_id"] and
                       left["tool_data"]["pose_mm_rad"] == old_left["tool_data"]["pose_mm_rad"])
    tool_unchanged = (right["tool_id"] == candidate["controller_tool_id"] and
                      right["tool_data"]["pose_mm_rad"] == candidate["controller_tool_pose_mm_rad"])
    base = base_stationarity(config, scene_dir=scene_dir, evidence_dir=evidence)
    write_json(evidence / "base_stationarity.json", base)
    keys = ("scene_snapshot_id", "scene_digest", "pointcloud_sha256",
            "T_body_camera_revision", "whole_robot_geometry_revision",
            "inactive_left_arm_revision", "tool_revision", "controller_tool_id",
            "controller_tool_pose_mm_rad", "execution_tool_envelope_revision",
            "planner_profile_revision", "trajectory_hash", "native_trajectory_hash",
            "timing_profile_revision", "native_sender_binary_sha256")
    live = {key: candidate[key] for key in keys}
    if not left_unchanged:
        live["inactive_left_arm_revision"] = "LIVE_LEFT_CHANGED"
    if not tool_unchanged:
        live["tool_revision"] = "LIVE_TOOL_CHANGED"
    live.update(actual_start_joints_rad=right["joint_position_rad"],
                base_stationary=base["stationary"], inactive_arm_known=left_unchanged)
    sender_sha = verify_installed_sender(SENDER)
    live["native_sender_binary_sha256"] = sender_sha
    deployment_limits = None
    if session["direction"] == "CURRENT_to_A":
        speed_profile = "precision"
        speed_state = read_json(ROOT / "config/speed_profiles.json")["profiles"][speed_profile]["state"]
    else:
        deployment = read_json(ROOT / "config/ab_demo_deployment_profile.json")
        motion = deployment["motion"]
        speed_profile = "ab_demo_deployment"
        speed_state = "UNCOMMISSIONED"
        deployment_limits = {
            "scope": deployment["scope"],
            "max_velocity_rad_s": max(motion["commissioning_speeds_rad_s"]),
            "max_acceleration_rad_s2": 0.20,
            "tracking_stop_threshold_deg": motion["tracking_stop_threshold_deg"],
        }
    kernel = DualArmSafetyKernel(False, {speed_profile: SimpleNamespace(state=speed_state)})
    result = kernel.preflight_execution_candidate(candidate, live, native,
                                                  speed_profile=speed_profile,
                                                  execution_limits=deployment_limits)
    result.update({"candidate_id": candidate["candidate_id"],
                   "speed_profile": speed_profile,
                   "base_evidence": str(evidence / "base_stationarity.json"),
                   "left_unchanged": left_unchanged, "right_tool_unchanged": tool_unchanged,
                   "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES"})
    write_json(evidence / "preflight.json", result)
    write_json(STATE, dict(session, state="PREFLIGHTED", preflight_dir=str(evidence)))
    return result


def _native_start_ticks(pid):
    """Linux process identity; PID alone is unsafe because it can be reused."""
    return int(Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[19])


def _matching_native(pid, start_ticks):
    try:
        command = Path("/proc/%d/cmdline" % pid).read_bytes().split(b"\0")
        return (_native_start_ticks(pid) == start_ticks and
                str(SENDER).encode() in command and b"supervised_path" in command)
    except (OSError, ValueError, IndexError):
        return False


def register_active_native(pid, candidate_id):
    ticks = _native_start_ticks(pid)
    if not _matching_native(pid, ticks):
        raise RuntimeError("refusing to register unknown native sender")
    write_json(ACTIVE_NATIVE, {"pid": pid, "start_ticks": ticks,
                               "candidate_id": candidate_id,
                               "registered_at_unix": time.time()})


def clear_active_native(pid):
    if ACTIVE_NATIVE.exists() and read_json(ACTIVE_NATIVE).get("pid") == pid:
        ACTIVE_NATIVE.unlink()


def stop():
    """Signal only the exact registered sender, then invalidate the candidate.

    Native SIGTERM handling performs motion_abort + servo disable. Physical
    E-stop remains the primary emergency control if motion does not cease.
    """
    old = status()
    signal_sent = False
    if ACTIVE_NATIVE.exists():
        active = read_json(ACTIVE_NATIVE)
        pid = int(active["pid"])
        if _matching_native(pid, int(active["start_ticks"])):
            os.kill(pid, signal.SIGTERM)
            signal_sent = True
    write_json(STATE, {"state": "STOPPED", "invalidated_at_unix": time.time(),
                       "previous_candidate_id": old.get("candidate_id"),
                       "execution_enabled": False})
    return dict(status(), native_abort_signal_sent=signal_sent,
                physical_estop_required_if_motion_continues=True)


def execute_next():
    raise PermissionError("P3.3A execute-next is locked; separate motion authorization required")


class FutureSupervisedKeyboardAbort:
    """Runner-injected callbacks only; never instantiated by ART P3.3A.

    Space and B both abort and disable servo; physical E-stop remains primary.
    No resume path exists: a fresh scan and replan are required after either.
    """

    def __init__(self, motion_abort, servo_disable, invalidate):
        self.motion_abort = motion_abort
        self.servo_disable = servo_disable
        self.invalidate = invalidate

    def handle(self, key):
        if key not in (" ", "b", "B"):
            return False
        try:
            self.motion_abort()
        finally:
            try:
                self.servo_disable()
            finally:
                self.invalidate("software_emergency_abort" if key in ("b", "B")
                                else "controlled_abort_hold")
        return True
