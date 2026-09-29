#!/usr/bin/env python3
"""Build the PLACE-from-HOLD execution package for the tray-to-groove demo.

Chain:  HOLD  ->  PLACE_BASE_MOVE  ->  PLACE_DETECT  ->  MOVE_PREPLACE
               ->  PLACE_DESCEND  ->  RELEASE  ->  RETREAT

This file is hardware-free.  It derives the cuRobo preplace request, the bounded
descend/retreat Cartesian segments, the CONTACT_BYPASS_V1 validations and the
release command, then writes one immutable package.  Sending anything to the
controller stays in the audited supervised sender, after an operator phrase.

Geometry helpers are imported from ``build_first_pick_execution_package.py`` on
purpose: the place package must not grow a second, drifting copy of the link-box
and BODY-cuboid arithmetic that the pick package was audited with.

The carried object is *not* re-derived here.  It is the pick package's
``coarse_attached_object_collision`` revision, which is what the real HOLD state
actually contains.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ares_r.manipulation.contact_bypass import ContactBypassPolicy, validate_bypass_segment
from ares_r.manipulation.task_parameters import gripper_percent_to_raw, load_task_parameters
from ares_r.motion.grasp import approach_direction, rotation_matrix
from ares_r.motion.native_execution_package import NATIVE_MAX_EXCURSION_RAD
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK

import place_ik_probe


def _pick_builder():
    spec = importlib.util.spec_from_file_location(
        "ares_r_first_pick_builder", ROOT / "scripts/build_first_pick_execution_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BF = _pick_builder()
sha, body_box, arm_geometry, trajectory_hash = BF.sha, BF.body_box, BF.arm_geometry, BF.trajectory_hash

#: Registered BODY displacement between the pickup pose and the placement pose.
#: The base contract stores it as ``y_m=-0.40``; the carried object's expected
#: BODY position at the placement pose is this much back along BODY +Y, which is
#: how the still-parked tray slot is found in the placement scene.
BASE_DELTA_BODY_Y_M = 0.40


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jsonable(value):
    """Recursively strip numpy scalars and arrays so a package can be hashed.

    numpy scalars look like floats but stdlib json refuses them, and the failure
    only shows up at the very end when the package digest is computed.
    """
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def load_hold(path):
    joints = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "snapshot" and row.get("actual_rad"):
            joints = [float(v) for v in row["actual_rad"]]
    if joints is None:
        raise RuntimeError("no right-arm snapshot row in %s" % path)
    return joints


def nearest_candidates(world_boxes, expected_center_m, limit=6):
    """Rank world cuboids by distance to an expected BODY point.

    This is a *diagnostic* only.  The tray area of a real scene is dense with
    small structure blocks, so the nearest centre is not an identity: on the
    09-24 pre-pick placement epoch the nearest candidate to the expected carried
    slot was an 8x8x8 mm STRUCTURE block 29 mm away, not the object.
    """
    expected = np.asarray(expected_center_m, dtype=float)
    rows = [(geometry_id, float(np.linalg.norm(
        np.asarray(value["center_body_m"], dtype=float) - expected)))
        for geometry_id, value in world_boxes.items()]
    rows.sort(key=lambda row: row[1])
    return [{"geometry_id": name, "distance_m": distance} for name, distance in rows[:limit]]


def straight_segment(solver, start_xyz, end_xyz, rotation, seed, samples=26):
    points = []
    for xyz in np.linspace(np.asarray(start_xyz, dtype=float),
                           np.asarray(end_xyz, dtype=float), samples):
        solved = solver.solve(xyz, rotation, seed)
        seed = np.asarray(solved.joints_rad)
        points.append([float(v) for v in solved.joints_rad])
    return points


def samples_for(solver, request, joints):
    return [{"tcp_position_body_m": solver.fk(q)[:3, 3].tolist(), "joints_rad": list(q),
             "arm_links": arm_geometry(q, request)} for q in joints]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-epoch", type=Path, required=True,
                        help="fresh committed right-arm place observation epoch")
    parser.add_argument("--pick-package", type=Path, required=True,
                        help="first_pick_execution_package.json holding the carried geometry")
    parser.add_argument("--template-plan", type=Path, required=True,
                        help="directory with planner_request.json (robot/TCP/collision model)")
    parser.add_argument("--hold-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retreat-distance-m", type=float, default=None,
                        help="override config place.retreat.distance_m; still hard-checked "
                             "against the measured continuous headroom")
    parser.add_argument("--carried-cuboid-id", default=None,
                        help="world cuboid that must leave the scene because the arm carries "
                             "it; required when the epoch was captured before the grasp")
    parser.add_argument("--scene-is-post-pick", action="store_true",
                        help="assert the epoch was captured after the grasp, so the carried "
                             "object is genuinely absent and nothing may be retired")
    parser.add_argument("--preplace-planning", type=Path, default=None,
                        help="planning.json from the cuRobo worker for preplace_request.json")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    params = load_task_parameters(ROOT / "config/tray_to_groove_v2.json")
    observation = load(args.place_epoch / "manipulation_observation.json")
    if observation.get("transaction_state") != "COMMITTED":
        raise RuntimeError("a committed place observation is required")
    if observation.get("purpose") != "place" or observation.get("arm") != "right":
        raise RuntimeError("a committed right-arm place observation is required")
    pick_package = load(args.pick_package)
    report = load(args.place_epoch / "live_scene/scene/scene_report.json")
    template = load(args.template_plan / "planner_request.json")
    q_hold = load_hold(args.hold_snapshot)

    solver = RuntimeGoalIK(template["robot_yaml_urdf"], template["T_body_model"],
                           template["T_link6_tcp"])
    target = observation["target"]
    place_xyz = [float(v) for v in target["pose_m_rad"][:3]]
    rotation = rotation_matrix(*[float(v) for v in target["pose_m_rad"][3:]],
                               order=target["orientation_convention"])
    direction = approach_direction(rotation, target["approach_axis"])

    # 1. The carried object leaves the world and becomes attached geometry.  The
    #    tray slot is located by the registered base displacement, never by eye.
    carried = pick_package["coarse_attached_object_collision"]
    pick_target_body = [float(v) for v in pick_package["target_pose_body_m_rad"][:3]]
    expected_slot = [pick_target_body[0], pick_target_body[1] + BASE_DELTA_BODY_Y_M,
                     pick_target_body[2]]
    fresh_compiled = load(args.place_epoch / "live_scene/scene/compiled_scene.json")
    cuboids = dict(fresh_compiled.get("cuboids", {}))
    world = {k: body_box(k, v, np.asarray(template["T_body_model"]))
             for k, v in cuboids.items()}
    slot_id, slot_distance = args.carried_cuboid_id, None
    candidates = nearest_candidates(world, expected_slot)
    retired = {}
    if slot_id:
        if slot_id not in cuboids:
            raise RuntimeError("--carried-cuboid-id %r is not a cuboid in this scene" % slot_id)
        retired = {slot_id: cuboids.pop(slot_id)}
        world.pop(slot_id)
        slot_distance = next(row["distance_m"] for row in candidates
                             if row["geometry_id"] == slot_id)
    elif not args.scene_is_post_pick:
        raise RuntimeError(
            "the scene still looks pre-grasp: either name the carried cuboid with "
            "--carried-cuboid-id, or assert --scene-is-post-pick when the epoch was captured "
            "after the grasp.  Refusing to retire an obstacle by nearest-centre: the tray "
            "region is dense small structure, nearest candidate %s is %s at %.4f m"
            % (candidates[0]["geometry_id"] if candidates else None,
               "%.4f m from the expected slot" % candidates[0]["distance_m"] if candidates
               else "unknown",
               candidates[0]["distance_m"] if candidates else float("nan")))

    # 2. Preplace target: one preplace height back along the commissioned approach.
    preplace_xyz = [place_xyz[i] - float(params["place"]["preplace_height_m"]) * direction[i]
                    for i in range(3)]
    # Seed-following IK is not the same as minimal travel: on this pose the
    # seed-following branch needs 169.3 deg of J3 while a sibling branch needs
    # only 147.5 deg of J2.  The native sender caps per-joint travel, so the
    # branch is chosen here and the choice is recorded in the package.
    candidates = place_ik_probe.goal_candidates(solver, np.asarray(preplace_xyz), rotation,
                                                np.asarray(q_hold))
    if not candidates:
        raise RuntimeError("no IK solution found for the preplace pose %s"
                           % [round(v, 4) for v in preplace_xyz])
    excursions = [place_ik_probe.excursion_deg(q_hold, joints) for joints in candidates]
    cap_deg = math.degrees(NATIVE_MAX_EXCURSION_RAD)
    if excursions[0] > cap_deg:
        raise RuntimeError(
            "the cheapest preplace branch needs %.1f deg of per-joint travel, above the native "
            "%.0f deg trip cap (candidate excursions: %s). Split the free-space move into two "
            "legs, or re-examine the approach axis -- do not raise the cap without a sender "
            "audit." % (excursions[0], cap_deg, [round(v, 1) for v in excursions[:5]]))
    selected = candidates[:6]
    selected_excursions = excursions[:len(selected)]
    preplace_goal = selected[0]

    scene = dict(fresh_compiled, cuboids=cuboids,
                 scene_transition="CARRIED_SLOT_WORLD_TO_ATTACHED",
                 attached_object_revision=carried["revision"])
    scene["digest"] = sha({k: v for k, v in scene.items() if k != "digest"})
    # The rebuild changes the world, so the snapshot identity must change with
    # it; the worker rejects a request whose binding does not match its scene.
    scene["scene_snapshot_id"] = "SCENE_PLACE_ATTACHED_" + scene["digest"][:20]
    scene["planning_context_digest"] = sha({"scene": scene["digest"],
                                            "attached": carried["revision"]})

    preplace_request = dict(template, compiled_scene=scene,
                            scene_snapshot_id=scene["scene_snapshot_id"],
                            scene_digest=scene["digest"],
                            epoch_scene_snapshot_id=observation["scene_snapshot_id"],
                            epoch_scene_digest=observation["scene_digest"],
                            start_rad=list(q_hold),
                            goal_rad=[float(v) for v in preplace_goal],
                            goal_candidates_rad=[[float(v) for v in joints] for joints in selected],
                            goal_candidate_metadata=[
                                {"kind": "PLACE_PREPLACE",
                                 "position_body_m": preplace_xyz,
                                 "max_joint_excursion_deg": value}
                                for value in selected_excursions],
                            attached_object_collision=carried,
                            geometry_revision=report["geometry_revision"],
                            inactive_arm_revision=report["inactive_arm_revision"],
                            physical_state="LIVE_AUTHORIZED_PLACE_FROM_HOLD",
                            runtime_motion_goal=None)
    (args.output / "preplace_request.json").write_text(
        json.dumps(jsonable(preplace_request), indent=2) + "\n")

    # 3. Descend and retreat are bounded Cartesian segments, validated under the
    #    manipulation-only contact policy.
    q_descend = straight_segment(solver, preplace_xyz, place_xyz, rotation, q_hold)
    descend_policy = ContactBypassPolicy.for_manipulation_skill(
        "PLACE_DESCENT", observation["observation_id"])
    retreat_axis = [float(v) for v in params["retreat"]["axis_body"]]
    configured_distance = float(params["retreat"]["distance_m"])
    requested_distance = (configured_distance if args.retreat_distance_m is None
                          else float(args.retreat_distance_m))
    # Measure the real continuous headroom before promising a trajectory.  On
    # this placement pose the configured 100 mm vertical retreat is not
    # reachable at all: J2 first enters the site soft margin at about 65 mm, and
    # the IK contract itself stops being met at about 90 mm.
    site_limits = load(ROOT / "config/jaka_mini2_motion.site.json")
    headroom, _ = place_ik_probe.cartesian_headroom(
        solver, rotation, place_xyz, np.asarray(q_descend[-1]), retreat_axis,
        site_limits=site_limits, cap_m=max(0.20, requested_distance + 0.05))
    if requested_distance > headroom + 1e-9:
        raise RuntimeError(
            "requested retreat %.3f m along BODY axis %s exceeds the measured continuous "
            "headroom %.3f m from the placement pose (site soft joint margin %.4f rad and IK "
            "contract both checked); refusing to build an infeasible trajectory"
            % (requested_distance, retreat_axis, headroom,
               float(site_limits["soft_limit_margin_rad"])))
    retreat_goal = [place_xyz[i] + requested_distance * retreat_axis[i] for i in range(3)]
    q_retreat = straight_segment(
        solver, place_xyz, retreat_goal, rotation, np.asarray(q_descend[-1]))
    retreat_policy = ContactBypassPolicy.for_manipulation_skill(
        "PLACE_RETREAT", observation["observation_id"])
    descend_validation = validate_bypass_segment(
        samples_for(solver, template, q_descend), world, descend_policy,
        expected_direction_body=direction, joint_lower=solver.lower, joint_upper=solver.upper,
        expire_at_end=False)
    retreat_validation = validate_bypass_segment(
        samples_for(solver, template, q_retreat), world, retreat_policy,
        expected_direction_body=params["retreat"]["axis_body"],
        joint_lower=solver.lower, joint_upper=solver.upper, expire_at_end=True)

    stages = [
        {"index": 1, "action": "PLACE_BASE_MOVE", "contract": dict(params["base_contracts"]["PLACE_BASE_POSE_V1"])},
        {"index": 2, "action": "PLACE_DETECT", "observation_id": observation["observation_id"]},
        {"index": 3, "action": "MOVE_PREPLACE", "target_body_m": preplace_xyz,
         "attached_object_revision": carried["revision"]},
        {"index": 4, "action": "PLACE_DESCEND", "trajectory_hash": trajectory_hash(q_descend)},
        {"index": 5, "action": "RELEASE", "gripper_raw": gripper_percent_to_raw(
            params["gripper"]["release_percent"], params)},
        {"index": 6, "action": "RETREAT", "trajectory_hash": trajectory_hash(q_retreat),
         "axis_body": retreat_axis, "distance_m": requested_distance},
    ]
    preplace_plan = load(args.preplace_planning) if args.preplace_planning else None
    if preplace_plan is not None:
        if preplace_plan.get("observed_result") != "SUCCESS" \
                or preplace_plan.get("execution_allowed") is not False:
            raise RuntimeError("the bound preplace planning run did not succeed as planning-only")
        if preplace_plan.get("scene_digest") != scene["digest"]:
            raise RuntimeError("the bound preplace plan was not planned against this scene")
        preplace_plan = {"planner": preplace_plan["planner"],
                         "mode": preplace_plan["mode"],
                         "scene_snapshot_id": preplace_plan["scene_snapshot_id"],
                         "scene_digest": preplace_plan["scene_digest"],
                         "path_limiting_object_id": preplace_plan["path_limiting_object_id"],
                         "clearance_m": preplace_plan["clearance_m"],
                         "central_tcp_margin_m": preplace_plan["central_tcp_margin_m"],
                         "dense_post_validation_samples":
                             preplace_plan["dense_post_validation_samples"],
                         "independent_dense_validation":
                             preplace_plan["independent_dense_validation"],
                         "attached_object_collision_revision":
                             preplace_plan["attached_object_collision_revision"],
                         "trajectory_hash": trajectory_hash(preplace_plan["trajectory_points_rad"]),
                         "sample_count": len(preplace_plan["trajectory_points_rad"])}
        stages[2]["trajectory_hash"] = preplace_plan["trajectory_hash"]
        stages[2]["planned"] = True

    package = {
        "schema_version": 1, "package_type": "PLACE_FROM_HOLD_EXECUTION_PACKAGE",
        "immutable": True, "execution_allowed": False, "awaiting_user_authorization": True,
        "observation_id": observation["observation_id"],
        "scene_snapshot_id": observation["scene_snapshot_id"],
        "scene_digest": observation["scene_digest"],
        "planning_scene_snapshot_id": scene["scene_snapshot_id"],
        "planning_scene_digest": scene["digest"],
        "pointcloud_sha256": observation["pointcloud_sha256"],
        "detection_id": observation["detection_id"],
        "target_pose_body_m_rad": target["pose_m_rad"],
        "approach_axis": target["approach_axis"],
        "approach_direction_body": direction,
        "hold_joints_rad": q_hold,
        "preplace_body_m": preplace_xyz, "place_body_m": place_xyz,
        "preplace_goal_candidates": [{"max_joint_excursion_deg": value}
                                     for value in selected_excursions],
        "preplace_native_trip_cap_deg": cap_deg,
        "carried_object_revision": carried["revision"],
        "carried_object_retired_world_cuboid": slot_id,
        "carried_slot_match_distance_m": slot_distance,
        "scene_is_post_pick_asserted": bool(args.scene_is_post_pick),
        "expected_carried_slot_body_m": expected_slot,
        "nearest_world_cuboids_to_expected_slot": candidates,
        "base_contract": dict(params["base_contracts"]["PLACE_BASE_POSE_V1"]),
        "contact_bypass_policy": {"PLACE_DESCENT": descend_policy.as_dict(),
                                  "PLACE_RETREAT": retreat_policy.as_dict()},
        "descend_validation": descend_validation,
        "retreat_validation": retreat_validation,
        "retreat_distance_m": requested_distance,
        "retreat_distance_source": ("config" if args.retreat_distance_m is None
                                     else "explicit_override"),
        "configured_retreat_distance_m": configured_distance,
        "measured_retreat_headroom_m": headroom,
        "site_soft_limit_margin_rad": float(site_limits["soft_limit_margin_rad"]),
        "retreat_within_headroom": requested_distance <= headroom + 1e-9,
        "stages": stages,
        "trajectories": {"preplace_request": "preplace_request.json",
                         "descend": q_descend, "retreat": q_retreat},
        "preplace_curobo_plan": preplace_plan,
        "place_included": True,
        "PLACE_FROM_HOLD_PACKAGE_READY": preplace_plan is not None,
    }
    package = jsonable(package)
    package["package_sha256"] = sha(package)
    (args.output / "place_execution_package.json").write_text(json.dumps(package, indent=2) + "\n")
    (args.output / "place_retired_world_geometry.json").write_text(
        json.dumps(retired, indent=2) + "\n")
    print(json.dumps({
        "observation_id": observation["observation_id"],
        "approach_axis": target["approach_axis"], "approach_direction_body": direction,
        "preplace_body_m": [round(v, 5) for v in preplace_xyz],
        "place_body_m": [round(v, 5) for v in place_xyz],
        "carried_cuboid_retired": slot_id,
        "carried_slot_match_distance_m": None if slot_distance is None else round(slot_distance, 5),
        "release_raw": gripper_percent_to_raw(params["gripper"]["release_percent"], params),
        "retreat_distance_m": requested_distance,
        "retreat_distance_source": package["retreat_distance_source"],
        "measured_retreat_headroom_m": round(headroom, 5),
        "descend_segment_m": descend_validation["segment_length_m"],
        "retreat_segment_m": retreat_validation["segment_length_m"],
        "descend_samples": descend_validation["samples"],
        "retreat_samples": retreat_validation["samples"],
        "package_sha256": package["package_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
