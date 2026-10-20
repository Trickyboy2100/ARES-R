#!/usr/bin/env python3
"""Prepare a fresh, observation-bound first-pick request and contact package.

This helper is deliberately hardware-free.  It derives all targets from one
committed manipulation observation and leaves actual sending to the audited
supervised executor.
"""

import argparse
import json
import math
import re
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ares_r.motion.grasp import approach_direction, rotation_matrix
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.execution_tool_envelope import build_execution_tool_envelope
from ares_r.manipulation.task_parameters import load_task_parameters
from ares_r.manipulation.grasp_symmetry import two_finger_grasp_rotations


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=Path, required=True)
    parser.add_argument("--template-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--component-gripper", action="store_true",
                        help="use the pinned 40%% opening component model; legacy default is unchanged")
    parser.add_argument("--early-contact-lift-precheck", action="store_true")
    parser.add_argument("--contact-observed-narrowphase",action="store_true",
                        help="contact-only raw occupancy refinement; no obstacle deletion")
    parser.add_argument('--task-tcp-offset-m-rad',default='[0,0,0,0,0,0]')
    parser.add_argument('--demo-tcp-orientation-compensation',default='{}')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    observation = load(args.epoch / "manipulation_observation.json")
    if observation["transaction_state"] != "COMMITTED":
        raise RuntimeError("fresh committed manipulation observation required")
    report = load(args.epoch / "live_scene/scene/scene_report.json")
    compiled = load(args.epoch / "live_scene/scene/compiled_scene.json")
    request = load(args.template_plan / "planner_request.json")
    # The template is the frozen 2026-09-24 pre-P3.9B request, where the central
    # slab was still enabled.  The site owns that switch now -- it is also what
    # ``build_first_pick_execution_package`` reads for its contact-bypass policy
    # -- so a stale template ``true`` must not silently re-enable a constraint
    # the site has since turned off.  The pick station sits 400 mm off the
    # centreline; the slab only ever produced "Start or End state in collision",
    # at the residual 16.8 mm the tool envelope reached into it.  Only the
    # boolean is taken from the site; every other motion constraint is left as
    # the template wrote it.
    motion_policy = load(ROOT / "config/scene_aware_motion.json")
    central_policy = motion_policy["central_exclusion"]
    central_enabled = bool(central_policy["enabled"])
    central_revision = str(central_policy.get("revision", ""))
    constraints = request.setdefault("motion_constraints", {})
    if bool(constraints.get("central_exclusion", True)) != central_enabled:
        print("central_exclusion: template %r -> site config %r (%s)"
              % (constraints.get("central_exclusion"), central_enabled,
                 central_revision))
    constraints["central_exclusion"] = central_enabled
    # The object being grasped is not a free-space obstacle.  The pregrasp is
    # DEFINED 50 mm away from it along the approach, and the decomposition AABB
    # around it is deliberately coarse -- the 2026-10-10 scan put the same kind
    # of tray at 145x161x50 mm and the pregrasp cleared it by 1.7 mm, while the
    # 2026-10-14 scan returned 230x212x113 mm for the same tray and the
    # identical pregrasp landed 18.1 mm inside it, so cuRobo refused with
    # "Start or End state in collision".  Declaring it here keeps the free-space
    # plan from depending on cluster-box luck; the grab itself is the straight
    # contact segment, validated separately under CONTACT_BYPASS_V1, and the
    # execution package still keeps the target in its own world for its
    # arm-link check.
    target_primitive = str(
        (report.get("target_binding") or {}).get("primitive_id") or "")
    if not target_primitive:
        raise RuntimeError("fresh scene report has no target_binding.primitive_id")
    # A primitive whose inflated AABB reaches the planning geometry is split into
    # ``<id>_refined_NNN`` children (support_decomposition), and target_binding
    # then names whichever ONE of them the detection bound to.  Ignoring just
    # that child leaves the other hundreds of boxes of the very same object in
    # the free-space world: the 2026-10-14 14:03 scan refined the target into 347
    # children, the ignore list covered 1 of them, and the planner squeezed the
    # gripper 9.5 mm past ..._refined_074 -- a sibling of the target it is
    # supposed to be approaching.  Strip the suffix and ignore the whole
    # component.  The count is reported so this stays auditable.
    target_component = re.sub(r"_refined_\d+$", "", target_primitive)
    prefix = "observed_" + target_component
    ignored_ids = sorted(
        key for key in compiled["cuboids"]
        if key == prefix or key.startswith(prefix + "_refined_"))
    if not ignored_ids:
        raise RuntimeError("target object %s is not in the compiled scene" % prefix)
    constraints["ignore_cuboid_ids"] = ignored_ids
    print("collision world: ignoring %d box(es) of the target object %s for the "
          "free-space plan (the pregrasp is defined relative to it; "
          "target_binding named %s)"
          % (len(ignored_ids), prefix, target_primitive))

    target = observation["target"]
    xyz = np.asarray(target["pose_m_rad"][:3], dtype=float)
    rotation = np.asarray(rotation_matrix(*target["pose_m_rad"][3:],
                                          target["orientation_convention"]), dtype=float)
    from ares_r.manipulation.task_tcp_offset import apply_task_pose,offset_revision,validate_offset
    task_offset=validate_offset(json.loads(args.task_tcp_offset_m_rad))
    xyz,rotation=apply_task_pose(xyz,rotation,task_offset)
    from ares_r.manipulation.task_tcp_offset import demo_local_rotation
    compensation=json.loads(args.demo_tcp_orientation_compensation)
    rotation=demo_local_rotation(rotation,{'demo_tcp_orientation_compensation':compensation})
    request['demo_tcp_orientation_compensation']=compensation
    request['task_tcp_offset_m_rad']=task_offset
    request['task_tcp_offset_revision']=offset_revision(task_offset)
    from scipy.spatial.transform import Rotation
    request['task_target_pose_body_m_rad']=xyz.tolist()+Rotation.from_matrix(rotation).as_euler('xyz').tolist()
    direction = np.asarray(approach_direction(rotation, target["approach_axis"]), dtype=float)
    task=load_task_parameters(ROOT/"config/tray_to_groove_v2.json")
    pregrasp_distance=float(task["contact"].get("selected_pregrasp_distance_m",.05))
    pregrasp_xyz = xyz - pregrasp_distance * direction
    start = observation["robot_state_after"]["right"]["diagnostics"]["joint_position_rad"]
    solver = RuntimeGoalIK(request["robot_yaml_urdf"], request["T_body_model"],
                           request["T_link6_tcp"])
    # The live current joints are far from the grasp branch.  Seed IK from the
    # last independently validated pregrasp solution; this is only a numerical
    # seed and all target/provenance fields still come from the fresh epoch.
    goals=[];metadata=[]
    if args.early_contact_lift_precheck:
        from ares_r.manipulation.contact_lift_precheck import precheck_contact_lift
        site=load(ROOT/"config/jaka_mini2_motion.site.json")
        margin=float(site["soft_limit_margin_rad"])
        solver.lower=np.maximum(solver.lower,np.asarray(site["lower_rad"])+margin)
        solver.upper=np.minimum(solver.upper,np.asarray(site["upper_rad"])-margin)
        def physical_reference_fk(q):
            pose=solver.fk(q).copy()
            pose[:3,:3]=demo_local_rotation(pose[:3,:3],{'demo_tcp_orientation_compensation':compensation},inverse=True)
            return pose
        precheck=precheck_contact_lift(solver,xyz,rotation,direction,
            [request["goal_rad"],start],contact_m=pregrasp_distance,level_fk=physical_reference_fk)
        (args.output/"contact_lift_precheck.json").write_text(json.dumps(precheck,indent=2)+"\n")
        if not precheck['passed']:
            raise RuntimeError(precheck['failure_code']+": see contact_lift_precheck.json; no QUALITY retry")
        for candidate in precheck['accepted']:
            goals.append(list(candidate['goal_rad']))
            metadata.append({k:v for k,v in candidate.items() if k!='goal_rad'})
        request['early_contact_lift_precheck']={
            'passed':True,'contact_m':pregrasp_distance,'lift_m':.1,
            'observation_id':observation['observation_id']}
    else:
        for symmetry_id,candidate_rotation in two_finger_grasp_rotations(rotation):
            try:
                goal=solver.solve(pregrasp_xyz,candidate_rotation,request["goal_rad"])
            except ValueError:
                continue
            goals.append(list(goal.joints_rad))
            metadata.append({"grasp_symmetry_id":symmetry_id,
                "target_rotation_body":candidate_rotation.tolist(),
                "approach_direction_body":direction.tolist(),
                "ik_position_error_m":goal.position_error_m,
                "ik_orientation_error_deg":float(np.degrees(goal.orientation_error_rad))})
    if not goals:
        raise RuntimeError("neither two-finger grasp symmetry is reachable")

    # A joint with a full-turn mechanical range has no unique number, and the IK
    # is seeded from the template's recorded vector, so the branch that comes
    # back can sit hundreds of degrees from the live start while being the very
    # same physical posture -- FK is periodic in J1/J4/J6.  cuRobo plans in joint
    # space, so it then drives 289 deg of J1 to a goal that is 71 deg away, and
    # ``package_first_pick_native`` rejects the trajectory with "native
    # 220-degree per-joint excursion cap".  Re-express those three joints on the
    # representation nearest the live start.  No physical pose changes: only the
    # number, and the representative must still fit the site limits.
    site = load(ROOT / "config/jaka_mini2_motion.site.json")
    lower = [float(v) for v in site["lower_rad"]]
    upper = [float(v) for v in site["upper_rad"]]
    for goal in goals:
        for index in (0, 3, 5):
            for shift in (-2.0 * math.pi, 2.0 * math.pi):
                candidate = goal[index] + shift
                if (lower[index] - 1e-9 <= candidate <= upper[index] + 1e-9
                        and abs(candidate - start[index])
                        < abs(goal[index] - start[index])):
                    goal[index] = candidate
    if args.early_contact_lift_precheck:
        from ares_r.manipulation.roundtrip_demo import digest
        for goal,item in zip(goals,metadata):
            paths=item['prechecked_paths']
            shift=np.asarray(goal)-np.asarray(paths['contact'][0])
            for name,rows in paths.items():paths[name]=(np.asarray(rows)+shift).tolist()
            item['observation_id']=observation['observation_id']
            item.pop('branch_sha256',None)
            item['branch_sha256']=digest(item)
    excursion = [abs(goals[0][index] - start[index]) for index in range(6)]
    print("goal on the branch nearest the live start: %s"
          % [round(math.degrees(v), 2) for v in goals[0]])
    print("worst per-joint excursion %.2f deg (native cap 220)"
          % math.degrees(max(excursion)))

    request.update({
        "compiled_scene": compiled,
        "scene_snapshot_id": observation["scene_snapshot_id"],
        "scene_digest": observation["scene_digest"],
        "start_rad": list(map(float, start)),
        "goal_rad": goals[0],
        "goal_candidates_rad": goals,
        "goal_candidate_metadata": metadata,
        "geometry_revision": report["geometry_revision"],
        "inactive_arm_revision": report["inactive_arm_revision"],
        "tool_revision": report["tool_revision"],
        "physical_state": "LIVE_AUTHORIZED_FIRST_PICK",
        "runtime_motion_goal": None,
    })
    request['manipulation_contact_scope']={
        'schema_version':1,'observation_id':observation['observation_id'],
        'scene_snapshot_id':observation['scene_snapshot_id'],
        'scene_digest':observation['scene_digest'],
        'pointcloud_sha256':observation['pointcloud_sha256'],
        'geometry_revision':report['geometry_revision'],'tool_revision':report['tool_revision'],
        'target_object_ids':ignored_ids,
        'source':'FRESH_DETECTION_BOUND_TARGET_COMPONENT',
        'allowed_stages':['contact','lift'],
        'maximum_initial_lift_m':.100,'remaining_lift_uses_full_scene':True}
    request.setdefault("planning_parameters",{})[
        "optimizer_collision_activation_distance"]=.010
    request.setdefault("planner_clearance_policy",{}).update({
        "preferred_clearance_m":.010,
        "optimizer_collision_activation_distance_m":.010,
        "revision":"P39C_PICK_PREGRASP_10MM_HARD_COLLISION"})
    request["execution_tool_envelope"] = build_execution_tool_envelope(
        request["collision_model"], request["controller_tool_pose_mm_rad"],
        inflation_m=0.008, max_opening_percent=40,
        use_component_geometry=args.component_gripper or args.contact_observed_narrowphase,
        component_inflation_m=0.0)
    if args.contact_observed_narrowphase:
        # Seal after the same final provenance normalisation written below.
        request['compiled_scene']['scene_snapshot_id']=observation['scene_snapshot_id']
        request['compiled_scene']['planning_context_digest']=observation['scene_digest']
        from ares_r.manipulation.observed_contact_geometry import build_observed_contact_geometry
        request['contact_observed_geometry']=build_observed_contact_geometry(args.epoch,request)
    # Fresh scene owns these values; do not retain stale template provenance.
    request["compiled_scene"]["scene_snapshot_id"] = observation["scene_snapshot_id"]
    request["compiled_scene"]["planning_context_digest"] = observation["scene_digest"]
    (args.output / "planner_request.json").write_text(json.dumps(request, indent=2) + "\n")
    summary = {
        "observation_id": observation["observation_id"],
        "scene_snapshot_id": observation["scene_snapshot_id"],
        "target_body_m": xyz.tolist(), "approach_direction_body": direction.tolist(),
        "pregrasp_body_m": pregrasp_xyz.tolist(), "pregrasp_distance_m":pregrasp_distance,
        "task_parameter_revision":task["revision"], "start_rad": start,
        "gripper_collision_representation": request["execution_tool_envelope"][
            "active_collision_representation"],
        "goal_candidates_rad": goals,"goal_candidate_metadata":metadata,
        "grasp_symmetry_policy":"TWO_FINGER_ROLL_180_DISCRETE_PRECONTACT_V1",
        "central_exclusion_enabled": central_enabled,
        "central_exclusion_revision": central_revision,
        "ignored_cuboid_ids": constraints["ignore_cuboid_ids"],
        "ignored_cuboid_count": len(constraints["ignore_cuboid_ids"]),
        "goal_excursion_from_start_deg": [round(math.degrees(v), 3)
                                          for v in excursion],
        "worst_goal_excursion_deg": round(math.degrees(max(excursion)), 3),
    }
    (args.output / "preparation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
