#!/usr/bin/env python3
"""Create the canonical immutable P3.9C transfer-chain selection artifact.

This command is planning-only.  It consumes a previously committed observation
and SceneSnapshot, performs bounded multi-IK/DP in ``TransferChainPlanner``, and
uses the long-lived cuRobo service only for the small retained candidate set.
It never calls an AMR, arm or gripper execution API.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from ares_r.manipulation.transfer_chain import (
    PersistentCuroboSegmentValidator, RuntimeMultiIKBackend,
    TransferChainPlanner, TransferChainRequest)
from ares_r.motion.planner_service_client import plan as persistent_plan
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.tcp_orientation import level_rotation, nearest_level_roll_branch
from ares_r.manipulation.grasp_symmetry import two_finger_grasp_rotations


def load(path):
    return json.loads(Path(path).read_text())


class FrozenScenePlanner:
    def __init__(self,profile,python,validated_cache_roots=()):
        self.profile=profile;self.python=python
        self.validated_cache_roots=tuple(Path(p) for p in validated_cache_roots)

    @staticmethod
    def _digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"))
                              .encode()).hexdigest()

    def _reuse_exact_success(self,request):
        digest=self._digest(request)
        for root in self.validated_cache_roots:
            for request_path in root.glob("**/planner_request.json"):
                try:
                    cached_request=load(request_path)
                    result_path=request_path.with_name("planning.json")
                    exact=self._digest(cached_request)==digest
                    current=copy.deepcopy(request);cached=copy.deepcopy(cached_request)
                    current_tol=((current.get("orientation_lock") or {}).pop(
                        "max_error_deg",None))
                    cached_tol=((cached.get("orientation_lock") or {}).pop(
                        "max_error_deg",None))
                    tolerance_only=(self._digest(current)==self._digest(cached))
                    log_path=request_path.with_name("planner.log")
                    log=log_path.read_text() if log_path.exists() else ""
                    if tolerance_only and "Start or End state in collision" in log:
                        raise RuntimeError("ENDPOINT_COLLISION_DETERMINISTIC")
                    if not exact and not tolerance_only:
                        continue
                    result=load(result_path)
                except (OSError,ValueError,json.JSONDecodeError):
                    continue
                dense=result.get("independent_dense_validation") or {}
                orientation=result.get("orientation_validation") or {}
                tolerance_revalidated=(not exact and current_tol is not None and
                    orientation.get("max_level_error_deg") is not None and
                    float(orientation["max_level_error_deg"])<=float(current_tol) and
                    dense.get("collision_free") is True)
                if (result.get("observed_result")=="SUCCESS" and
                        dense.get("collision_free") is True and
                        orientation.get("passed") is True) or tolerance_revalidated:
                    result=copy.deepcopy(result)
                    if tolerance_revalidated:
                        result["observed_result"]="SUCCESS"
                        result.setdefault("orientation_validation",{})["passed"]=True
                        result["orientation_validation"]["tolerance_deg"]=current_tol
                    result["exact_validated_cache_reuse"]={
                        "request_sha256":digest,
                        "source":str(result_path),
                        "policy":("EXACT_REQUEST_AND_FROZEN_SCENE_ONLY_V1" if exact else
                                  "IDENTICAL_GEOMETRY_TOLERANCE_REVALIDATION_V1"),
                        "cached_tolerance_deg":cached_tol,
                        "revalidated_tolerance_deg":current_tol}
                    return result
        return None

    def __call__(self,motion,scene,output):
        output=Path(output);output.mkdir(parents=True,exist_ok=False)
        request=copy.deepcopy(scene);request.update({
            "planning_only":True,"execution_allowed":False,
            "physical_state":"SIMULATED_FOR_SCHEME_REHEARSAL",
            "start_rad":motion["start_rad"],"goal_rad":motion["goal_rad"],
            "goal_candidates_rad":[motion["goal_rad"]],
            "goal_candidate_metadata":[motion["goal_metadata"]],
            "orientation_lock":motion["orientation_lock"],
            "runtime_motion_goal":motion["runtime_motion_goal"],
            "whole_chain_symmetry_binding":motion["symmetry_binding"],
            "benchmark_runs":1,"warmup_policy":"ONCE_PER_RUNTIME",
            "planner_profile_revision":"P39C2_%s_PERSISTENT"%self.profile})
        request.setdefault("motion_constraints",{})["central_exclusion"]=False
        params=request.setdefault("planning_parameters",{})
        if motion["semantic_segment"] in ("current_to_pregrasp","lift_to_center"):
            # Pregrasp and post-contact lift begin target/support-adjacent.
            # Keep the hard collision floor/dense validator, but apply the
            # explicitly commissioned 10 mm escape preference instead of the
            # generic 30 mm free-space preference at a ~17-18 mm endpoint.
            params["optimizer_collision_activation_distance"]=.010
            request.setdefault("planner_clearance_policy",{}).update(
                preferred_clearance_m=.010,
                optimizer_collision_activation_distance_m=.010,
                revision=("P39C2_PREGRASP_10MM_HARD_COLLISION"
                          if motion["semantic_segment"]=="current_to_pregrasp"
                          else "P39C2_CONTACT_ESCAPE_10MM_HARD_COLLISION"))
        if self.profile=="FAST":
            params.update(num_ik_seeds=4,num_trajopt_seeds=2,max_attempts=1,
                          enable_graph_attempt=0)
        else:
            params.update(num_ik_seeds=8,num_trajopt_seeds=8,max_attempts=10,
                          enable_graph_attempt=1)
        if motion["semantic_segment"]=="lift_to_center" and motion.get("attached_object_collision"):
            request["attached_object_collision"]=motion["attached_object_collision"]
            request["attached_object_collision_revision"]=motion[
                "attached_object_collision"]["revision"]
            request.setdefault("motion_constraints",{})[
                "attached_object_revision"]=motion["attached_object_collision"]["revision"]
        request_path=output/"planner_request.json";result_path=output/"planning.json"
        request_path.write_text(json.dumps(request,indent=2)+"\n")
        result=self._reuse_exact_success(request)
        if result is None:
            try:
                persistent_plan(self.python,ROOT,request_path,result_path,
                                output/"planner.log",900.0)
            except Exception as exc:
                log_path=output/"planner.log"
                log=log_path.read_text() if log_path.exists() else ""
                if "Start or End state in collision" in log:
                    raise RuntimeError("ENDPOINT_COLLISION_DETERMINISTIC") from exc
                raise
            result=load(result_path)
        else:
            (output/"planner.log").write_text("exact validated frozen-scene cache hit\n")
        if motion["semantic_segment"]=="current_to_pregrasp":
            endpoint_error=float(motion["goal_orientation_error_deg"])
            result["orientation_validation"]={
                "passed":endpoint_error<=3.0,
                "scope":"TERMINAL_EPIC_PREGRASP_ORIENTATION",
                "max_orientation_error_deg":endpoint_error,
                "note":"Hard level-throughout applies after attachment; pregrasp is endpoint-bound."}
            result_path.write_text(json.dumps(result,indent=2)+"\n")
        return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--preparation",type=Path,required=True)
    parser.add_argument("--planner-request",type=Path,required=True)
    parser.add_argument("--attached-request",type=Path)
    parser.add_argument("--start-audit",type=Path,
                        help="read-only current right-arm audit used for planning rehearsal start")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--validated-cache-root",type=Path,action="append",default=[])
    parser.add_argument("--center",nargs=3,type=float,default=(.35725,-.07936,1.02634))
    parser.add_argument("--preplace",nargs=3,type=float,default=(.717123,-.304470,1.006590))
    args=parser.parse_args()
    prep=load(args.preparation);base=load(args.planner_request)
    start_joints=(load(args.start_audit)["diagnostics"]["joint_position_rad"]
                  if args.start_audit else prep["start_rad"])
    attached=(load(args.attached_request).get("attached_object_collision")
              if args.attached_request else None)
    ik=RuntimeGoalIK(base["robot_yaml_urdf"],base["T_body_model"],base["T_link6_tcp"])
    normal_meta=next(row for row in prep["goal_candidate_metadata"]
                     if row["grasp_symmetry_id"] in ("EPIC_AS_REPORTED","NORMAL"))
    request=TransferChainRequest(
        observation_id=prep["observation_id"],scene_snapshot_id=prep["scene_snapshot_id"],
        current_joints_rad=tuple(start_joints),
        grasp_position_body_m=tuple(prep["target_body_m"]),
        grasp_rotation_body=tuple(map(tuple,normal_meta["target_rotation_body"])),
        approach_direction_body=tuple(prep["approach_direction_body"]),
        pregrasp_distance_m=float(prep["pregrasp_distance_m"]),lift_distance_m=.10,
        center_position_body_m=tuple(args.center),preplace_position_body_m=tuple(args.preplace),
        historical_center_joints_seed=(),beam_width=8,
        full_chain_candidates_per_symmetry=3)
    roll_by_symmetry={name:nearest_level_roll_branch(rotation)
                      for name,rotation in two_finger_grasp_rotations(
                          np.asarray(normal_meta["target_rotation_body"],dtype=float))}
    rotation_by_symmetry=dict(two_finger_grasp_rotations(
        np.asarray(normal_meta["target_rotation_body"],dtype=float)))

    def build_motion(name,start,goal,symmetry,boundary):
        semantic=(name.split("_",2)[2] if name.startswith("candidate_") else name)
        roll=roll_by_symmetry[symmetry]
        rotation=(rotation_by_symmetry[symmetry] if semantic=="current_to_pregrasp"
                  else level_rotation(goal["yaw_rad"],roll))
        orientation_lock=(None if semantic=="current_to_pregrasp" else {
                "policy":"LEVEL_YAW_TARGET_V1",
                "criteria_rpy":[1.0,0.0,1.0],"max_error_deg":3.5,
                "candidate_target_rotations":[rotation.tolist()],
                "candidate_yaws_rad":[goal["yaw_rad"]],
                "final_yaw_target_rad":goal["yaw_rad"],
                "non_terminal_orientation_cost":True})
        return {"segment":name,"semantic_segment":semantic,"start_rad":start["joints_rad"],
            "goal_rad":goal["joints_rad"],
            "goal_orientation_error_deg":goal["orientation_error_deg"],
            "goal_metadata":{"grasp_symmetry_id":symmetry,
                "target_rotation_body":rotation.tolist(),"yaw_rad":goal["yaw_rad"]},
            "orientation_lock":orientation_lock,
            "runtime_motion_goal":None,
            "symmetry_binding":{"selected_grasp_symmetry_id":symmetry,
                "scene_boundary":boundary,"policy":"P39C2_WHOLE_CHAIN"},
            "attached_object_collision":attached}

    def resolve_scene(scene_snapshot_id,boundary):
        if scene_snapshot_id!=base["scene_snapshot_id"]:
            raise RuntimeError("frozen scene binding mismatch")
        return dict(base,scene_snapshot_id=scene_snapshot_id)

    system=load(ROOT/"config/system.json")
    output=args.output
    validator=PersistentCuroboSegmentValidator(
        FrozenScenePlanner("FAST",system["curobo"]["python"],args.validated_cache_root),
        FrozenScenePlanner("FALLBACK",system["curobo"]["python"],args.validated_cache_root),
        build_motion,resolve_scene,output/"segments")
    planner=TransferChainPlanner(RuntimeMultiIKBackend(ik,max_attempts_per_target=16),validator)
    artifact_path=output/"transfer_chain_selection.json"
    artifact=planner.plan(request,artifact_path)
    print(json.dumps({key:artifact[key] for key in (
        "artifact_digest","selected_grasp_symmetry_id","STATION_CONTRACT_BOUND",
        "WHOLE_CHAIN_BRANCH_SELECTED","SELECTED_BRANCH_PREGRASP_CUROBO_PASS",
        "SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS",
        "HARD_LEVEL_ORIENTATION_VALIDATOR_PASS",
        "TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY")},indent=2))
    if artifact["WHOLE_CHAIN_BRANCH_SELECTED"]!="YES":raise SystemExit(2)


if __name__=="__main__":main()
