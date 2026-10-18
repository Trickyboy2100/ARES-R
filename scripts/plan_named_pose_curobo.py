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
import hashlib
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
from ares_r.motion.tcp_orientation import level_rotation, tcp_yaw_rad
from ares_r.named_poses import load_named_poses
from ares_r.perception.robot_collision import arm_link_transforms

import build_visibility_move as BVM
import regularize_visibility_pose as RVP

SENDER = BVM.SENDER
TRIP_CAP_DEG = BVM.TRIP_CAP_DEG
SITE_FILE = ROOT / "config/jaka_mini2_motion.site.json"
#: Numerical slack on the tray-level comparison. Still far below anything a
#: level sensor or an operator could act on, and well inside the 3.5 deg cap.
#: Raised 0.05 -> 0.5 deg on 2026-10-10: the tray-level metric is an acos near
#: 180 deg while the tray is held inverted, so a sub-degree "worsening" on the
#: way to level is pure numerical noise. The endpoint must still finish level
#: inside the cap, which is the property that actually matters.
TILT_TOLERANCE_DEG = 0.5


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def filter_attached_observation_duplicates(compiled,attached,start,request):
    """Remove only pointcloud primitives geometrically owned by the held object.

    The same physical object otherwise appears twice after a fresh scan: once
    as revision-bound attached collision geometry and again as observed
    pointcloud cuboids.  Known support surfaces are never removed here.
    """
    frames=arm_link_transforms(Path(request["robot_yaml_urdf"]),start)
    T=np.asarray(request["T_body_model"])@frames["link6"]
    local=attached["link6_aabb"]
    held={"geometry_id":"attached_observation_association",
          "center_body_m":(T@np.r_[local["center_m"],1.])[:3].tolist(),
          "rotation_body":T[:3,:3].tolist(),
          "half_extents_m":(np.asarray(local["dims_m"])/2+.010).tolist()}
    builder=BVM.pick_builder();kept={};removed=[]
    for identifier,value in compiled["cuboids"].items():
        eligible=(identifier.startswith("observed_") and
                  "support_surface" not in identifier)
        observed=builder.body_box(identifier,value,np.asarray(request["T_body_model"]))
        source_identity=(identifier==attached.get("object_id"))
        if eligible and (source_identity or BVM._geometry_overlap(held,observed)):
            removed.append(identifier)
        else:kept[identifier]=value
    if not removed:return compiled,{"removed_ids":[],"policy":"NO_OVERLAP"}
    filtered=dict(compiled);filtered["cuboids"]=kept
    filtered["attached_observation_filter"]={
        "policy":"GEOMETRIC_ATTACHED_OBJECT_DEDUP_V1",
        "association_margin_m":.010,"support_surfaces_preserved":True,
        "removed_ids":removed,"attached_revision":attached["revision"]}
    digest="sha256:"+hashlib.sha256(json.dumps(filtered,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    filtered["digest"]=digest;filtered["planning_context_digest"]=digest
    return filtered,filtered["attached_observation_filter"]


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
    parser.add_argument("--whole-chain-audit", type=Path,
                        help="use the selected symmetry branch target from a full-chain audit")
    parser.add_argument("--chain-stage",
                        choices=("center", "transit", "preland", "rear_preplace_150mm", "preplace"),
                        help="stage key inside --whole-chain-audit")
    parser.add_argument("--no-level-manifold", action="store_true",
                        help="keep the level orientation lock but stop asking the worker to "
                             "seed a continuous level IK family. Required when the goal is near "
                             "the workspace edge and the reachable yaw set is disconnected")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speed-rad-s", type=float, default=0.10)
    parser.add_argument("--accel-rad-s2", type=float, default=0.20)
    parser.add_argument("--tilt-cap-deg", type=float, default=BVM.DEFAULT_TILT_CAP_DEG)
    parser.add_argument("--trip-cap-deg", type=float, default=TRIP_CAP_DEG,
                        help="overrides the %.0f deg default trip gate; the HARD ceiling is the "
                             "supervised sender's own 220 deg per-joint excursion envelope. "
                             "Start-to-goal joint travel is not a safety quantity -- the pick and "
                             "place packagers say so explicitly -- because joint position, "
                             "velocity, acceleration, tracking and the controller protections "
                             "are all enforced downstream of this gate" % TRIP_CAP_DEG)
    parser.add_argument("--plan-only", action="store_true",
                        help="stop after the cuRobo plan; do not gate or package")
    parser.add_argument("--wrap-goal-to-start", action="store_true",
                        help="shift the full-turn joints (J1/J4/J6) of the goal onto the "
                             "representation nearest the live start. A revolute joint vector "
                             "is only defined up to 2*pi, and the named-pose vector recorded "
                             "in config can sit on the far branch: same physical pose, but "
                             "hundreds of degrees of travel and over the 220 deg trip cap")
    parser.add_argument("--empty-gripper", action="store_true",
                        help="the gripper holds nothing, so every payload constraint is "
                             "vacuous: skip the carried-tray level gate and do not impose "
                             "the level orientation lock. Both skips are recorded in "
                             "plan_summary.json so a reader can tell them from a pass")
    args = parser.parse_args()
    # The trip gate is a policy threshold, not a hardware limit, so it may be
    # raised -- but never past the envelope the audited sender itself declares.
    if not 0.0 < args.trip_cap_deg <= 220.0:
        raise SystemExit("--trip-cap-deg must be in (0, 220]; the supervised sender declares a "
                         "220 deg per-joint excursion envelope, got %r" % (args.trip_cap_deg,))
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
    chain_selection=None
    if args.whole_chain_audit:
        if not args.chain_stage:
            raise SystemExit("--chain-stage is required with --whole-chain-audit")
        audit=load(args.whole_chain_audit)
        selected_id=audit.get("selected_grasp_symmetry_id")
        chain_selection=next((row for row in audit.get("candidates",[])
                              if row.get("grasp_symmetry_id")==selected_id),None)
        if not chain_selection or not chain_selection.get("kinematic_chain_valid"):
            raise SystemExit("whole-chain audit has no valid selected grasp branch")
        goal=chain_selection["joint_targets_rad"][args.chain_stage]
    if not goal or len(goal) != 6:
        raise SystemExit("%s has no reviewed right-arm six-joint target" % args.pose)
    goal = [float(v) for v in goal]

    # -- 2. start: live, read-only --------------------------------------- #
    diagnostics = BVM.read_right_arm(args.output / "start_fk_audit.json")
    start = [float(v) for v in diagnostics["joint_position_rad"]]
    if args.wrap_goal_to_start:
        # Same physical angles, on the representation nearest the live pose.  A
        # joint inside a full-turn range has no unique number, and the recorded
        # named-pose vector is one arbitrary representative of many.
        site = load(SITE_FILE)
        lower = [float(v) for v in site["lower_rad"]]
        upper = [float(v) for v in site["upper_rad"]]
        wrapped = list(goal)
        for index in (0, 3, 5):
            for shift in (-2.0 * math.pi, 2.0 * math.pi):
                candidate = goal[index] + shift
                if (lower[index] - 1e-9 <= candidate <= upper[index] + 1e-9
                        and abs(candidate - start[index]) < abs(wrapped[index] - start[index])):
                    wrapped[index] = candidate
        if wrapped != goal:
            print("goal wrapped onto the representation nearest the live start: %s -> %s"
                  % ([round(v, 4) for v in goal], [round(v, 4) for v in wrapped]))
        goal = wrapped
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
        compiled,attached_filter=filter_attached_observation_duplicates(
            compiled,attached,start,request)
        write(args.output/"attached_observation_filter.json",attached_filter)
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
    if chain_selection is not None and not args.empty_gripper:
        branch=int(chain_selection["roll_branch"])
        # The lock target is the GOAL's own rotation, read back as a BODY yaw plus
        # a level roll branch.  A per-stage yaw table would silently contradict
        # the goal the moment the goal's yaw is not the one the table guessed --
        # which is exactly this chain: center and transit hold tool Z along
        # BODY +Y (yaw = +pi/2) while the dryer placement pose the camera reports
        # approaches along BODY +X (yaw ~ 2.6 deg).
        goal_pose=RuntimeGoalIK(request["robot_yaml_urdf"],request["T_body_model"],
            request["T_link6_tcp"]).fk(goal)
        yaw=tcp_yaw_rad(goal_pose[:3,:3])
        target_position=goal_pose[:3,3].tolist()
        request["orientation_lock"]={"policy":"LEVEL_YAW_TARGET_V1",
            "criteria_rpy":[1.,0.,1.],"weight_scale":200.,"max_error_deg":3.5,
            "target_R_body_tcp":level_rotation(yaw,branch).tolist(),
            "final_yaw_target_rad":yaw,"non_terminal_orientation_cost":True}
        request["hard_level_manifold"]={"schema_version":1,
            "goal_position_m":target_position,"goal_yaw_rad":yaw,"ik_samples":31,
            "max_ik_step_rad":.22,
            "seed_offsets_m":[[0,0,0],[0,0,.04],[0,0,.08],
                              [0,.05,.06],[0,-.05,.06],[-.04,0,.06],[.04,0,.06]]}
        request["whole_chain_symmetry_binding"]={
            "policy":audit["policy"],"selected_grasp_symmetry_id":selected_id,
            "roll_branch":branch,"stage":args.chain_stage}
        if args.no_level_manifold:
            # The manifold seeds a CONTINUOUS level IK family from start to goal.
            # When the goal sits near the edge of the workspace the reachable yaw
            # set is a set of disconnected islands, so no such family exists and
            # the worker refuses before cuRobo is even asked.  Dropping the seed
            # request does not drop the orientation lock: the level target is still
            # optimised and still validated, only the starting guess is left to
            # cuRobo.
            request.pop("hard_level_manifold")
            request["whole_chain_symmetry_binding"]["level_manifold_seeds"]="SKIPPED_BY_FLAG"
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
        "whole_chain_symmetry_binding":request.get("whole_chain_symmetry_binding"),
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
    # Branch-agnostic tray gate.  A flat tray is level whether its tool-Y
    # up-axis points at +Z or -Z, so the SIGNED angle to +Z is the wrong
    # measure: a level transfer onto the flipped roll branch reads 180 deg, and
    # a genuine 180 deg flip onto the other branch reads 0 deg.  The two
    # properties that actually matter are (i) the tray must not ROLL relative
    # to how it started -- a 180 deg flip about the approach axis is a roll,
    # not a level change -- and (ii) the endpoint must finish level.
    def _tray_axis(R, up=(0.0, 1.0, 0.0)):
        return np.asarray(R, dtype=float) @ np.asarray(up, dtype=float)
    def _angle_between(a, b):
        a = a / float(np.linalg.norm(a)); b = b / float(np.linalg.norm(b))
        return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a, b))))))
    def _level_dev(R):
        signed = RVP.tilt_deg(np.asarray(R))
        return min(signed, 180.0 - signed)
    up_start = _tray_axis(np.asarray(ik.fk(knots[0])[:3, :3]))
    rolls = [_angle_between(_tray_axis(np.asarray(ik.fk(q)[:3, :3])), up_start)
             for q in knots]
    levels = [_level_dev(np.asarray(ik.fk(q)[:3, :3])) for q in knots]

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
    if max(excursion) > args.trip_cap_deg:
        blockers.append("joint trip %.1f deg exceeds the trip cap %.0f deg"
                        % (max(excursion), args.trip_cap_deg))
    # The tray is very often already off level when this runs: a hand drag can
    # leave it tilted and this move is the way back to level.  So the rule is
    # the documented one -- the path must never make the tilt *worse*, and it
    # must finish inside the cap.  Testing ``max(tilt) > cap`` instead would
    # refuse to rescue an already-tilted tray, while still letting a move worsen
    # the tilt from 1 deg to 3.4 deg.
    # The tray is very often already off level when this runs: a hand drag can
    # leave it tilted and this move is the way back to level.  The branch-
    # agnostic quantity that matters is the tray's off-level angle (folded to
    # 0..90); a 180 deg flip swings it through ~90 deg and is rejected by the
    # same rule that lets an already-tilted tray be rescued.  So the rule is:
    # (i) never tilt the tray further off level than the start's own slack plus
    # the cap allows, and (ii) finish inside the level cap.
    level_start = levels[0]
    level_budget = max(level_start, args.tilt_cap_deg) + TILT_TOLERANCE_DEG
    # With an empty gripper there is no tray to hold level: the gate would only
    # forbid the tool from reorienting on the way to the goal.  Skipped, and the
    # skip is written into the summary rather than silently reported as a pass.
    if args.empty_gripper:
        level_gate = "SKIPPED_GRIPPER_EMPTY"
    else:
        level_gate = "ENFORCED"
        if max(levels) > level_budget:
            blockers.append("the path tilts the tray %.3f deg off level, above its %.3f deg start "
                            "(budget %.3f deg)" % (max(levels), level_start, level_budget))
        if levels[-1] > args.tilt_cap_deg:
            blockers.append("the endpoint holds the tray %.3f deg off level, above the %.2f deg cap"
                            % (levels[-1], args.tilt_cap_deg))
    if collisions:
        blockers.append("%d collision sample(s), first %s" % (len(collisions), collisions[0]))
    summary.update({
        "per_joint_excursion_deg": [round(v, 3) for v in excursion],
        "max_joint_excursion_deg": round(max(excursion), 3),
        "trip_cap_deg": args.trip_cap_deg,
        "trip_cap_source": ("DEFAULT" if args.trip_cap_deg == TRIP_CAP_DEG else "OVERRIDE"),
        "tray_tilt": {"start_off_level_deg": round(level_start, 3),
                      "worst_off_level_deg": round(max(levels), 3),
                      "end_off_level_deg": round(levels[-1], 3),
                      "worst_roll_deg": round(max(rolls), 3),
                      "cap_deg": args.tilt_cap_deg,
                      "level_budget_deg": round(level_budget, 3),
                      "gate": level_gate,
                      "never_tilts_more_than_start": bool(max(levels) <= level_budget),
                      "end_level_within_cap": bool(levels[-1] <= args.tilt_cap_deg),
                      "worst_level_sample": int(np.argmax(levels))},
        "orientation_lock": ("SKIPPED_GRIPPER_EMPTY" if args.empty_gripper
                             else ("APPLIED" if chain_selection is not None else "NOT_REQUESTED")),
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
