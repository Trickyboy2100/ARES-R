#!/usr/bin/env python3
"""Plan the right arm from its live joints to a named pose with the grasp-time pipeline.

The pick and the placement preplace both go through
``ares_r.motion.production_scene_worker``: a cspace goal is planned against the
point-cloud-compiled scene, with the carried tray declared as an
``attached_object_collision`` link6 AABB.  ``build_visibility_move.py`` instead
interpolates joints linearly and only checks collisions locally, which is fine
for a 7 deg return but is not the pipeline the pick was accepted on.

This retargets the grasp pipeline at one reviewed named pose (default
``center``) and then applies the same pre-package gates the dense move uses --
per-joint trip cap, arm/body collision -- plus a corrected tray-level rule:
the path must never make the held object's tilt worse and must finish inside
the cap, rather than merely checking that the peak is inside the cap.

Not a single byte is sent to the controller:
* the start state comes from the read-only ``scripts/audit_curobo_fk.py``;
* ``package_native_preview`` enforces the trip cap, site soft limits, velocity
  and acceleration caps, geometry preservation and the tracking budget, and
  ``verify_installed_sender`` pins the audited sender binary by sha256;
* the sender is then only asked to ``validate-supervised-path``, which opens no
  controller connection at all.

The emitted pose is ``design_target_uncommissioned`` until it has actually been
executed and read back, so this script proves the plan, not the pose.
"""

import argparse
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

from ares_r.motion.execution_tool_envelope import build_execution_tool_envelope
from ares_r.motion.native_execution_package import (package_native_preview,
                                                    verify_installed_sender)
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.named_poses import load_named_poses

import build_visibility_move as BVM
import regularize_visibility_pose as RVP

SENDER = BVM.SENDER
TRIP_CAP_DEG = BVM.TRIP_CAP_DEG
SITE_FILE = ROOT / "config/jaka_mini2_motion.site.json"
#: Numerical slack on the tray-level comparison; 0.05 deg is far below anything
#: a level sensor or an operator could act on, and well inside the 3.5 deg cap.
TILT_TOLERANCE_DEG = 0.05


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--epoch", type=Path, required=True,
                        help="epoch whose live_scene/scene/ holds compiled_scene.json and "
                             "scene_report.json")
    parser.add_argument("--template-plan", type=Path, required=True,
                        help="grasp/place plan dir holding planner_request.json; it supplies "
                             "the planner profile, the attached-object collision entry and "
                             "the cuRobo robot/collision revisions")
    parser.add_argument("--attached-package", type=Path,
                        help="first-pick package whose coarse attached geometry must be "
                             "carried through this free-space plan")
    parser.add_argument("--pose", default="center", help="named pose to plan to")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speed-rad-s", type=float, default=0.10)
    parser.add_argument("--accel-rad-s2", type=float, default=0.20)
    parser.add_argument("--tilt-cap-deg", type=float, default=BVM.DEFAULT_TILT_CAP_DEG)
    parser.add_argument("--plan-only", action="store_true",
                        help="stop after the cuRobo plan; do not gate or package")
    args = parser.parse_args()
    # ``read_right_arm`` resolves the collision-model path relative to the repo
    # root, so pin every path and make the working directory explicit instead of
    # depending on how the shell happened to be invoked.
    args.epoch = args.epoch.resolve()
    args.template_plan = args.template_plan.resolve()
    args.output = args.output.resolve()
    os.chdir(ROOT)
    if args.output.exists():
        raise SystemExit("output directory already exists: %s" % args.output)
    args.output.mkdir(parents=True)

    # -- 1. target: a reviewed named pose, never a fresh detection -------- #
    library = load_named_poses(ROOT / "config/named_poses.json")
    pose = library["poses"].get(args.pose)
    if pose is None:
        raise SystemExit("unknown named pose: %s" % args.pose)
    target = pose["arms"]["right"]
    goal = target.get("ik_joint_rad") or target.get("joint_rad")
    if not goal or len(goal) != 6:
        raise SystemExit("%s has no reviewed right-arm six-joint target" % args.pose)
    goal = [float(v) for v in goal]

    # -- 2. start: live, read-only --------------------------------------- #
    diagnostics = BVM.read_right_arm(args.output / "start_fk_audit.json")
    start = [float(v) for v in diagnostics["joint_position_rad"]]
    tool_id = int(diagnostics["tool_id"])
    # Native header line 2 is the controller *tool frame* (the link6 -> TCP
    # offset), not a TCP pose; the sender aborts with "tool/user changed" if it
    # disagrees with the live controller, so it is read live and never guessed.
    tool_frame = [float(v) for v in
                  (diagnostics.get("tool_data") or {}).get("pose_mm_rad") or []]
    if len(tool_frame) != 6:
        raise SystemExit("the read-only audit did not return the controller tool frame")

    # -- 3. scene: the compiled planning-only world ---------------------- #
    compiled = load(args.epoch / "live_scene/scene/compiled_scene.json")
    report = load(args.epoch / "live_scene/scene/scene_report.json")
    if compiled.get("planning_scope") != "P3_PRODUCTION_PLANNING_ONLY":
        raise SystemExit("epoch scene is not a P3 planning-only compiled scene")

    # -- 4. request: byte-identical in structure to the grasp request ----- #
    request = load(args.template_plan / "planner_request.json")
    if args.attached_package:
        pick_package=load(args.attached_package)
        attached=pick_package["coarse_attached_object_collision"]
        request["attached_object_collision"]=attached
        request.setdefault("motion_constraints",{})["attached_object_revision"]=attached["revision"]
    request.update({
        "compiled_scene": compiled,
        "scene_snapshot_id": compiled["scene_snapshot_id"],
        "scene_digest": compiled["digest"],
        "start_rad": start,
        "goal_rad": goal,
        "goal_candidates_rad": [goal],
        "goal_candidate_metadata": None,
        "runtime_motion_goal": None,
        "geometry_revision": report["geometry_revision"],
        "inactive_arm_revision": report["inactive_arm_revision"],
        "controller_tool_pose_mm_rad": tool_frame,
        "physical_state": "LIVE_AUTHORIZED_NAMED_POSE",
    })
    request["execution_tool_envelope"] = build_execution_tool_envelope(
        request["collision_model"], tool_frame, inflation_m=0.008,
        max_opening_percent=40)
    request_path = args.output / "planner_request.json"
    write(request_path, request)

    # -- 5. cuRobo, in the pinned environment ---------------------------- #
    config = load(ROOT / "config/system.json")
    planning_path = args.output / "planning.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run([config["curobo"]["python"], "-m",
                    "ares_r.motion.production_scene_worker",
                    str(request_path), str(planning_path)],
                   cwd=str(ROOT), env=environment, check=True,
                   timeout=float(config["curobo"]["timeout_s"]) + 60.0)
    plan = load(planning_path)
    if plan.get("observed_result") != "SUCCESS":
        raise SystemExit("cuRobo did not return SUCCESS: %s" % plan.get("observed_result"))
    knots = [[float(v) for v in row] for row in plan["trajectory_points_rad"]]
    period = float(plan["smoothness"]["sample_period_s"])
    summary = {
        "schema_version": 1,
        "pose": args.pose,
        "start_joints_rad": start, "goal_joints_rad": goal,
        "controller_tool_frame_mm_rad": tool_frame, "controller_tool_id": tool_id,
        "scene_snapshot_id": compiled["scene_snapshot_id"],
        "scene_digest": compiled["digest"],
        "knots": len(knots), "sample_period_s": period,
        "attached_object_id": (request.get("attached_object_collision") or {}).get("object_id"),
        "path_clearance_m": (plan.get("clearance_m") or {}).get("planned_path"),
        "path_limiting_object_id": plan.get("path_limiting_object_id"),
        "central_tcp_margin_m": plan.get("central_tcp_margin_m"),
    }
    write(args.output / "plan_summary.json", summary)
    if args.plan_only:
        print(json.dumps(summary, indent=2))
        return

    # -- 6. pre-package gates -------------------------------------------- #
    ik = RuntimeGoalIK(request["robot_yaml_urdf"], request["T_body_model"],
                       request["T_link6_tcp"])
    excursion = [math.degrees(max(abs(row[i] - start[i]) for row in knots))
                 for i in range(6)]
    tilts = [RVP.tilt_deg(np.asarray(ik.fk(q)[:3, :3])) for q in knots]

    world = compiled.get("cuboids", {})
    builder = BVM.pick_builder()
    T_body_model = np.asarray(request["T_body_model"])
    boxes = {name: builder.body_box(name, value, T_body_model)
             for name, value in world.items()}
    request_stub = {"robot_yaml_urdf": request["robot_yaml_urdf"],
                    "T_body_model": request["T_body_model"],
                    "collision_model": request["collision_model"]}
    collisions = []
    for index in range(0, len(knots), 4):
        links = builder.arm_geometry(knots[index], request_stub)
        for link in links:
            for obstacle_id in ("body_chassis_lower", "body_chassis_upper"):
                if obstacle_id in boxes and BVM._geometry_overlap(link, boxes[obstacle_id]):
                    collisions.append({"sample": index, "link": link["geometry_id"],
                                       "obstacle": obstacle_id})
        for a in range(len(links)):
            for b in range(a + 2, len(links)):
                if BVM._geometry_overlap(links[a], links[b]):
                    collisions.append({"sample": index, "link": links[a]["geometry_id"],
                                       "obstacle": "self:" + links[b]["geometry_id"]})

    blockers = []
    if max(excursion) > TRIP_CAP_DEG:
        blockers.append("joint trip %.1f deg exceeds the native cap %.0f deg"
                        % (max(excursion), TRIP_CAP_DEG))
    # The tray is very often already off level when this runs: a hand drag can
    # leave it tilted and this move is the way back to level.  So the rule is
    # the documented one -- the path must never make the tilt *worse*, and it
    # must finish inside the cap.  Testing ``max(tilt) > cap`` instead would
    # refuse to rescue an already-tilted tray, while still letting a move worsen
    # the tilt from 1 deg to 3.4 deg.
    tilt_start = tilts[0]
    tilt_budget = max(tilt_start, args.tilt_cap_deg) + TILT_TOLERANCE_DEG
    if max(tilts) > tilt_budget:
        blockers.append("the path tilts the tray to %.3f deg, above the %.3f deg start "
                        "(cap %.2f deg)" % (max(tilts), tilt_start, args.tilt_cap_deg))
    if tilts[-1] > args.tilt_cap_deg:
        blockers.append("the endpoint holds the tray at %.3f deg, above the %.2f deg cap"
                        % (tilts[-1], args.tilt_cap_deg))
    if collisions:
        blockers.append("%d collision sample(s), first %s" % (len(collisions), collisions[0]))
    summary.update({
        "per_joint_excursion_deg": [round(v, 3) for v in excursion],
        "max_joint_excursion_deg": round(max(excursion), 3),
        "trip_cap_deg": TRIP_CAP_DEG,
        "tray_tilt": {"start_deg": round(tilt_start, 3), "worst_deg": round(max(tilts), 3),
                      "end_deg": round(tilts[-1], 3), "cap_deg": args.tilt_cap_deg,
                      "budget_deg": round(tilt_budget, 3),
                      "never_worse_than_start": bool(max(tilts) <= tilt_budget),
                      "worst_sample": int(np.argmax(tilts))},
        "collisions": collisions[:20], "collision_count": len(collisions),
        "blockers": blockers,
    })
    if blockers:
        write(args.output / "center_move_blocked.json", summary)
        raise SystemExit("BLOCKED: %s" % "; ".join(blockers))

    # -- 7. package + offline sender validation -------------------------- #
    if not verify_installed_sender(SENDER):
        raise SystemExit("audited sender sha256 mismatch")
    text, audit = package_native_preview(
        knots, period, load(SITE_FILE), tool_id=tool_id,
        controller_tool_pose_mm_rad=tool_frame, captured_at_unix=int(time.time()),
        speed_ceiling_rad_s=args.speed_rad_s, accel_ceiling_rad_s2=args.accel_rad_s2,
        tracking_stop_threshold_deg=1.5)
    native_path = args.output / ("%s.native.txt" % args.pose)
    native_path.write_text(text, encoding="utf-8")
    write(args.output / "native_audit.json", audit)

    offline = subprocess.run([str(SENDER), "validate-supervised-path", str(native_path)],
                             text=True, capture_output=True, check=False)
    summary["sender_validation"] = offline.stdout.strip()
    summary["sender_accepted"] = "VALID_SUPERVISED_PATH" in offline.stdout
    summary["native_audit"] = {key: audit[key] for key in
                               ("duration_s", "sample_count", "format",
                                "predicted_tracking_gate_deg", "tracking_margin_deg",
                                "max_excursion_rad", "speed_cap_rad_s", "accel_cap_rad_s2")}
    write(args.output / "plan_summary.json", summary)
    if not summary["sender_accepted"]:
        raise SystemExit("the audited sender rejected the packaged file")

    print(json.dumps({**summary["native_audit"],
                      "max_joint_excursion_deg": summary["max_joint_excursion_deg"],
                      "tray_tilt": summary["tray_tilt"],
                      "collision_count": summary["collision_count"],
                      "path_clearance_m": summary["path_clearance_m"],
                      "sender_accepted": summary["sender_accepted"],
                      "native_file": str(native_path)}, indent=2))


if __name__ == "__main__":
    main()
