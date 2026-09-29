#!/usr/bin/env python3
"""Build a supervised move from the current right-arm pose back to a taught pose.

The taught pose is a joint-space target (that is what a drag teaches), so the
trajectory is a dense joint-space interpolation.  Three gates are applied to
every sample before anything is packaged:

* per-joint trip cap and site soft limits (delegated to ``package_native_preview``);
* **tray level**: the held object's up-axis is ``tool Y`` (see
  ``regularize_visibility_pose`` for why), so the tilt is the angle between the
  tool's Y axis and BODY +Z.  A move with the object held must never increase
  that tilt -- spilling is not recoverable;
* **collision**: arm link boxes against the recorded world cuboids, plus
  non-adjacent arm self-collision, sampled densely.  This is deliberately *not*
  cuRobo: it is a hard local check on a short return move, and a failure means
  "re-plan with cuRobo", not "lower the gate".

Nothing here talks to the controller except the read-only joint audit and the
sender's own offline ``validate-supervised-path``.
"""

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ares_r.manipulation.contact_motion import _geometry_overlap
from ares_r.motion.native_execution_package import (package_native_preview,
                                                    verify_installed_sender)
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK

import regularize_visibility_pose as RVP

SENDER = Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick")
TRIP_CAP_DEG = 150.0
DEFAULT_TILT_CAP_DEG = 3.5
DEFAULT_SAMPLES = 401


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pick_builder():
    spec = importlib.util.spec_from_file_location(
        "ares_r_first_pick_builder", ROOT / "scripts/build_first_pick_execution_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_right_arm(destination):
    config = load(ROOT / "config/system.json")
    model = load(Path(config["robot_collision"]["model"]))
    urdf = Path(model["asset_root"]) / model["urdf"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run([sys.executable, str(ROOT / "scripts/audit_curobo_fk.py"),
                    str(urdf), str(destination), "--side", "right"],
                   cwd=str(ROOT), env=environment, check=True)
    return load(destination)["diagnostics"]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=Path, required=True,
                        help="teach record (visibility_clear_pose.json) or regularised target")
    parser.add_argument("--use", choices=("taught", "regularised"), default="taught")
    parser.add_argument("--scene", type=Path, required=True,
                        help="epoch whose live_scene/scene/compiled_scene.json is the world")
    parser.add_argument("--template-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--speed-rad-s", type=float, default=0.10)
    parser.add_argument("--accel-rad-s2", type=float, default=0.20)
    parser.add_argument("--tilt-cap-deg", type=float, default=DEFAULT_TILT_CAP_DEG,
                        help="hard cap on the held object's tilt at any sample")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output directory already exists: %s" % args.output)
    args.output.mkdir(parents=True)

    if args.target.is_dir():
        target_path = args.target / ("visibility_clear_target.json"
                                     if args.use == "regularised"
                                     else "visibility_clear_pose.json")
    else:
        target_path = args.target
    target = load(target_path)
    goal = (np.asarray(target["ik"]["goal_joints_rad"], dtype=float)
            if args.use == "regularised"
            else np.asarray(target["joints_rad"], dtype=float))

    diagnostics = read_right_arm(args.output / "start_fk_audit.json")
    start = np.asarray([float(v) for v in diagnostics["joint_position_rad"]])
    start_tcp = [float(v) for v in diagnostics["tcp_position_mm_rad"]]
    # Native header line 2 is the *controller tool frame* (the link6 -> TCP offset),
    # NOT a TCP pose.  The sender compares it against the live controller tool and
    # aborts with "tool/user changed" if it disagrees.  Read it from the controller.
    tool_offset = [float(v) for v in
                   (diagnostics.get("tool_data") or {}).get("pose_mm_rad") or []]
    if len(tool_offset) != 6:
        raise SystemExit("the read-only audit did not return the controller tool frame")
    recorded_tool = target.get("controller_tool_pose_mm_rad")
    if recorded_tool is not None and list(recorded_tool) != tool_offset:
        print("note: target record's controller_tool_pose_mm_rad is not the tool frame "
              "(it holds a TCP pose); using the live controller tool frame",
              file=sys.stderr)

    template = load(args.template_plan / "planner_request.json")
    ik = RuntimeGoalIK(template["robot_yaml_urdf"], template["T_body_model"],
                       template["T_link6_tcp"])
    site = load(ROOT / "config/jaka_mini2_motion.site.json")

    # Dense joint-space interpolation.  Sample spacing is irrelevant to the
    # packaged timing; it only has to be dense enough to catch a bad sample.
    fractions = np.linspace(0.0, 1.0, args.samples)
    points = [list(map(float, start + fraction * (goal - start))) for fraction in fractions]

    excursion = [math.degrees(float(v)) for v in np.abs(goal - start)]
    tilts = [RVP.tilt_deg(np.asarray(ik.fk(q)[:3, :3])) for q in points]
    worst_tilt = max(tilts)
    start_tilt = tilts[0]

    world = load(args.scene / "live_scene/scene/compiled_scene.json").get("cuboids", {})
    builder = pick_builder()
    T_body_model = np.asarray(template["T_body_model"])
    boxes = {name: builder.body_box(name, value, T_body_model)
             for name, value in world.items()}
    request_stub = {"robot_yaml_urdf": template["robot_yaml_urdf"],
                    "T_body_model": template["T_body_model"],
                    "collision_model": template["collision_model"]}
    collisions = []
    for index in range(0, args.samples, 4):
        links = builder.arm_geometry(points[index], request_stub)
        for link in links:
            for obstacle_id in ("body_chassis_lower", "body_chassis_upper"):
                if obstacle_id in boxes and _geometry_overlap(link, boxes[obstacle_id]):
                    collisions.append({"sample": index, "link": link["geometry_id"],
                                       "obstacle": obstacle_id})
        for a in range(len(links)):
            for b in range(a + 2, len(links)):
                if _geometry_overlap(links[a], links[b]):
                    collisions.append({"sample": index, "link": links[a]["geometry_id"],
                                       "obstacle": "self:" + links[b]["geometry_id"]})

    blockers = []
    if max(excursion) > TRIP_CAP_DEG:
        blockers.append("joint trip %.1f deg exceeds the native cap %.0f deg"
                        % (max(excursion), TRIP_CAP_DEG))
    if worst_tilt > args.tilt_cap_deg:
        blockers.append("tray tilt reaches %.3f deg, above the %.2f deg cap"
                        % (worst_tilt, args.tilt_cap_deg))
    if collisions:
        blockers.append("%d collision sample(s), first %s"
                        % (len(collisions), collisions[0]))

    summary = {
        "schema_version": 1,
        "target_source": str(target_path), "target_used": args.use,
        "start_joints_rad": start.tolist(), "start_tcp_pose_mm_rad": start_tcp,
        "controller_tool_offset_mm_rad": tool_offset,
        "goal_joints_rad": goal.tolist(),
        "per_joint_travel_deg": [round(v, 3) for v in excursion],
        "max_joint_travel_deg": round(max(excursion), 3),
        "trip_cap_deg": TRIP_CAP_DEG,
        "tray_tilt": {"start_deg": start_tilt, "worst_deg": worst_tilt,
                      "end_deg": tilts[-1], "cap_deg": args.tilt_cap_deg,
                      "worst_sample": int(np.argmax(tilts))},
        "collisions": collisions[:20], "collision_count": len(collisions),
        "blockers": blockers,
        "trajectory_sha256": "sha256:" + __import__("hashlib").sha256(
            json.dumps([[round(v, 12) for v in row] for row in points],
                       separators=(",", ":")).encode()).hexdigest(),
    }

    if blockers:
        (args.output / "visibility_move_blocked.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: summary[k] for k in
                          ("per_joint_travel_deg", "max_joint_travel_deg",
                           "tray_tilt", "collision_count", "blockers")}, indent=2))
        raise SystemExit("BLOCKED: %s" % "; ".join(blockers))

    assert verify_installed_sender(SENDER)
    text, audit = package_native_preview(
        points, 0.02, site, tool_id=1,
        controller_tool_pose_mm_rad=tool_offset,
        captured_at_unix=int(time.time()), speed_ceiling_rad_s=args.speed_rad_s,
        accel_ceiling_rad_s2=args.accel_rad_s2, tracking_stop_threshold_deg=1.5)
    native_path = args.output / "visibility_return.native.txt"
    native_path.write_text(text, encoding="utf-8")
    (args.output / "native_audit.json").write_text(json.dumps(audit, indent=2) + "\n",
                                                   encoding="utf-8")

    offline = subprocess.run([str(SENDER), "validate-supervised-path", str(native_path)],
                             text=True, capture_output=True, check=False)
    summary["sender_validation"] = offline.stdout.strip()
    summary["sender_accepted"] = "VALID_SUPERVISED_PATH" in offline.stdout
    summary["native_audit"] = {key: audit[key] for key in
                               ("duration_s", "sample_count", "format",
                                "predicted_tracking_gate_deg", "tracking_margin_deg",
                                "speed_cap_rad_s", "accel_cap_rad_s2")}
    (args.output / "visibility_move.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not summary["sender_accepted"]:
        raise SystemExit("the audited sender rejected the packaged file")

    print(json.dumps({**summary["native_audit"],
                      "per_joint_travel_deg": summary["per_joint_travel_deg"],
                      "max_joint_travel_deg": summary["max_joint_travel_deg"],
                      "tray_tilt": summary["tray_tilt"],
                      "collision_count": summary["collision_count"],
                      "sender_accepted": summary["sender_accepted"],
                      "native_file": str(native_path)}, indent=2))


if __name__ == "__main__":
    main()
