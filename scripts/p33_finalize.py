#!/usr/bin/env python3
"""Select reproducible P3.3 plans and create *offline-only* native previews.

No live motion or controller API is imported. This script refuses to create an
execution candidate unless one activation profile passes every frozen-scene
repeat for CURRENT→A and both CLEAR/AVOID A↔B directions.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion.execution_candidate import (
    digest, make_candidate_manifest, make_execution_lease_draft,
    select_reproducible_candidate,
)
from ares_r.motion.native_execution_package import package_native_preview, verify_installed_sender
from ares_r.motion.safety_kernel import DualArmSafetyKernel
from p33_sweep import CASES, EVIDENCE


def load(path):
    return json.loads(Path(path).read_text())


def scene_time(report, capture_pointer_path=None):
    if capture_pointer_path is not None and Path(capture_pointer_path).exists():
        pointer = load(capture_pointer_path)
        capture = Path(pointer.get("capture_manifest", ""))
        if capture.is_file():
            value = load(capture).get("captured_at_unix")
            if isinstance(value, (int, float)):
                return float(value)
    path = Path(report["fresh_manifest"])
    if not path.exists():
        return 0.0
    manifest = load(path)
    for name in ("captured_at_unix", "timestamp_unix", "acquired_at_unix"):
        if isinstance(manifest.get(name), (int, float)):
            return float(manifest[name])
    for name in ("captured_at_utc", "timestamp_utc", "timestamp"):
        if isinstance(manifest.get(name), str):
            try:
                return datetime.fromisoformat(manifest[name].replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
    return 0.0


def choose_global_profile(summary):
    profiles = []
    for activation in summary["profiles_mm"]:
        groups = []
        for case in summary["cases"]:
            rows = [row for row in summary["trials"]
                    if row["case"] == case and row["activation_mm"] == activation]
            chosen = select_reproducible_candidate(rows, minimum_repeats=summary["repeats"])
            if chosen is None:
                break
            groups.append((case, chosen))
        if len(groups) == len(summary["cases"]):
            profiles.append((activation, groups))
    if not profiles:
        return None
    return sorted(profiles, key=lambda entry: (
        -min(row["independent_clearance_m"] for _, row in entry[1]),
        sum(row["path_length_m"] for _, row in entry[1]), entry[0]))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep_summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite execution candidate review")
    summary = load(args.sweep_summary)
    if "completed_at_unix" not in summary:
        raise RuntimeError("incomplete sweep cannot produce execution candidates")
    args.output.mkdir(parents=True)
    decision = choose_global_profile(summary)
    if decision is None:
        result = {"READY_TO_REQUEST_FIRST_SUPERVISED_MOTION": "NO",
                  "reason": "no common 10/20/30/40 mm profile passed all three repeats in every case",
                  "tool_tcp_physical_semantics_unresolved": True,
                  "execution_enabled": False}
        (args.output / "decision.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return
    activation, choices = decision
    site = load(ROOT / "config/jaka_mini2_motion.site.json")
    sender_sha = verify_installed_sender("/home/yikun/ares-r-curobo-assets/jaka_right_demo")
    speed_state = load(ROOT / "config/speed_profiles.json")["profiles"]["slow"]["state"]
    kernel = DualArmSafetyKernel(False, {"slow": SimpleNamespace(state=speed_state)})
    output = {"chosen_activation_mm": activation,
              "planner_profile_revision": None, "cases": {},
              "READY_TO_REQUEST_FIRST_SUPERVISED_MOTION": "NO",
              "execution_enabled": False}
    for case, selected in choices:
        plan_dir = ROOT / selected["artifact"]
        plan = load(plan_dir / "planning.json")
        request = load(plan_dir / "planner_request.json")
        source_dir, scene_name, direction = CASES[case]
        base = EVIDENCE / source_dir
        report = load(base / scene_name / "scene_report.json")
        captured = scene_time(report, base / "capture_pointer.json")
        audit = load(base / "right_fk_audit.json")["diagnostics"]
        profile_revision = digest(request["planning_parameters"])
        if output["planner_profile_revision"] is None:
            output["planner_profile_revision"] = profile_revision
        elif output["planner_profile_revision"] != profile_revision:
            raise RuntimeError("profile revision changed across selected legs")
        destination = "A" if direction.endswith("to_A") else "B"
        case_dir = args.output / case
        case_dir.mkdir()
        try:
            native_text, native_audit = package_native_preview(
                plan["trajectory_points_rad"],
                plan["smoothness"]["sample_period_s"], site,
                tool_id=audit["tool_id"],
                controller_tool_pose_mm_rad=audit["tool_data"]["pose_mm_rad"],
                captured_at_unix=captured)
        except Exception as exc:
            output["cases"][case] = {"native_preview_generated": False,
                                     "execution_package_ready": False,
                                     "reason": "%s: %s" % (type(exc).__name__, exc)}
            continue
        (case_dir / "native_preview.txt").write_text(native_text)
        (case_dir / "native_audit.json").write_text(json.dumps(native_audit, indent=2) + "\n")
        timing_revision = digest({"native_dt_s": native_audit["sample_period_s"],
                                  "speed_cap_rad_s": native_audit["speed_cap_rad_s"],
                                  "accel_cap_rad_s2": native_audit["accel_cap_rad_s2"]})
        candidate = make_candidate_manifest(
            plan=plan, selection=selected, scene_report=report,
            pointcloud_sha256=report["pointcloud_sha256"],
            actual_start_joints_rad=audit["joint_position_rad"],
            tool_id=audit["tool_id"],
            controller_tool_pose_mm_rad=audit["tool_data"]["pose_mm_rad"],
            planner_profile_revision=profile_revision,
            timing_profile_revision=timing_revision,
            native_trajectory_hash=native_audit["native_file_sha256"],
            native_duration_s=native_audit["duration_s"],
            native_sender_binary_sha256=sender_sha,
            expected_destination=destination,
            scene_captured_at_unix=captured)
        lease = make_execution_lease_draft(candidate)
        live = {key: candidate[key] for key in (
            "scene_snapshot_id", "scene_digest", "pointcloud_sha256",
            "T_body_camera_revision", "whole_robot_geometry_revision",
            "inactive_left_arm_revision", "tool_revision", "controller_tool_id",
            "controller_tool_pose_mm_rad", "execution_tool_envelope_revision",
            "planner_profile_revision", "trajectory_hash", "native_trajectory_hash",
            "timing_profile_revision", "native_sender_binary_sha256")}
        live.update(actual_start_joints_rad=audit["joint_position_rad"],
                    base_stationary=False, inactive_arm_known=False)
        preflight = kernel.preflight_execution_candidate(candidate, live, native_audit,
                                                         now=time.time())
        (case_dir / "candidate_manifest.json").write_text(json.dumps(candidate, indent=2) + "\n")
        (case_dir / "lease_draft.json").write_text(json.dumps(lease, indent=2) + "\n")
        (case_dir / "preflight.json").write_text(json.dumps(preflight, indent=2) + "\n")
        output["cases"][case] = {"native_preview_generated": True,
             "execution_package_ready": preflight["ready"],
             "candidate_id": candidate["candidate_id"],
             "trajectory_hash": candidate["trajectory_hash"],
             "native_duration_s": native_audit["duration_s"],
             "tracking_margin_to_sender_hard_gate_deg":
                 native_audit["predicted_margin_to_sender_hard_gate_deg"],
             "dry_run_blockers": preflight["blockers"]}
    (args.output / "decision.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
