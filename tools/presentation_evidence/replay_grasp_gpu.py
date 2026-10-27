#!/usr/bin/env python3
"""One actual GPU replay of the archived refined GRASP pregrasp request.

Unlike uniform-padding geometry A/B this preserves the complete original world,
contact scope and observed-geometry correction. It cannot certify contact/lift.
"""
import argparse, copy, json, sys, time, uuid
from pathlib import Path
import numpy as np
from replay_rasc import ROOT, load, save, sha, digest
sys.path.insert(0, str(ROOT/'src'))
from ares_r.motion.persistent_planner_service import PlannerSupervisor

def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--model',type=Path,required=True);a=p.parse_args()
    source=a.study/'refined55-stability/single25_1x4_graph/0.request.json'
    r=load(source);original=copy.deepcopy(r);yaml=a.model/'robot.yml';urdf=a.model/'jaka_minicobo_gripper.urdf'
    assert sha(urdf)==r['collision_model']['asset_sha256'][urdf.name]
    r['robot_yaml']=str(yaml.resolve());r['robot_yaml_urdf']=str(urdf.resolve());r['collision_model']['asset_root']=str(a.model.resolve())
    r.update(planning_only=True,execution_allowed=False,independent_distance_backend='NATIVE_CPU_V1')
    assert r['compiled_scene']==original['compiled_scene'] and r['start_rad']==original['start_rad'] and r['goal_rad']==original['goal_rad']
    a.private.mkdir(exist_ok=True,parents=True);request=a.private/'source_refined_request.json';output=a.private/'source_refined_planning.json';save(request,r)
    supervisor=PlannerSupervisor();at=time.monotonic()
    try:
        reply=supervisor.plan(dict(job_id=uuid.uuid4().hex,request=str(request.resolve()),output=str(output.resolve()),log=str((a.private/'source_refined_gpu.log').resolve()),deadline_monotonic=at+120))
    finally:supervisor.reap()
    plan=load(output) if output.exists() else {}
    result=dict(source_kind='FROZEN_REPLAY',scope='ARCHIVED_REFINED_PREGRASP_ONLY',source_request_sha256=sha(source),
                relocated_request_sha256=sha(request),urdf_sha256=sha(urdf),original_scene_unchanged=True,
                original_start_goal_unchanged=True,original_contact_scope_unchanged=True,
                elapsed_s=time.monotonic()-at,supervisor_reply=reply,observed_result=plan.get('observed_result'),
                timing_s=plan.get('timing_s'),effective_solver_config=plan.get('effective_solver_config'),
                gpu_memory_bytes=plan.get('gpu_memory_bytes'),independent_dense_validation=plan.get('independent_dense_validation'),
                orientation_validation=plan.get('orientation_validation'),trajectory_samples=len(plan.get('trajectory_points_rad',[])),
                runtime_model_derivation=load(a.model/'derivation.json'),
                limitation='Original archived refined world, not rebuilt uniform7 A/B world; pregrasp only. No physical movement; contact/lift IK remains a separate failed historical check.')
    if plan.get('trajectory_points_rad'):
        save(a.output/'runlogs/gpu_trajectory.json',dict(source_kind='FROZEN_REPLAY',trajectory_points_rad=plan['trajectory_points_rad'],tcp_path_body_m=plan.get('tcp_path_body_m'),source_plan_sha256=sha(output),native_retiming=False))
    save(a.output/'runlogs/grasp_gpu_replay.json',result);print(json.dumps({k:result[k] for k in ['observed_result','elapsed_s','trajectory_samples','supervisor_reply']},default=str))

if __name__=='__main__': main()
