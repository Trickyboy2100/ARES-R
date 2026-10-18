#!/usr/bin/env python3
"""Kinematic full-chain audit for the two equivalent two-finger grasps.

This is a planning prefilter, not an executor.  It selects no branch from the
pick leg alone: both grasp symmetries are propagated through contact, lift,
center, rear-preplace and preplace before a branch is ranked.  Every free-space
leg still requires a fresh SceneSnapshot and cuRobo collision plan at runtime.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.tcp_orientation import (level_rotation,
                                           nearest_level_roll_branch,
                                           tcp_yaw_rad)


def multistart(ik, xyz, rotation, reference, rng):
    xyz=np.asarray(xyz,dtype=float);rotation=np.asarray(rotation,dtype=float)
    reference=np.asarray(reference,dtype=float)
    def residual(q):
        pose=ik.fk(q)
        error=Rotation.from_matrix(rotation.T@pose[:3,:3]).as_rotvec()
        return np.r_[pose[:3,3]-xyz,.18*error,.0001*(q-reference)]
    seeds=[reference]
    seeds += [np.clip(reference+rng.normal(0,scale,6),ik.lower,ik.upper)
              for scale in (.35,.7,1.2) for _ in range(18)]
    seeds += [rng.uniform(ik.lower,ik.upper) for _ in range(48)]
    valid=[]
    for seed in seeds:
        result=least_squares(residual,seed,bounds=(ik.lower,ik.upper),max_nfev=220,
                             xtol=1e-9,ftol=1e-9,gtol=1e-9)
        pose=ik.fk(result.x)
        pe=float(np.linalg.norm(pose[:3,3]-xyz))
        oe=float(np.linalg.norm(Rotation.from_matrix(
            rotation.T@pose[:3,:3]).as_rotvec()))
        if pe<=.002 and oe<=math.radians(.8):
            valid.append((float(np.linalg.norm(result.x-reference)),result.x,pe,oe))
    if not valid:
        raise ValueError("no multistart IK solution")
    return min(valid,key=lambda row:row[0])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("preparation")
    parser.add_argument("planner_request")
    parser.add_argument("output")
    parser.add_argument("--bound-request",type=Path,
                        help="write a copy with the whole-chain-selected grasp candidate first")
    parser.add_argument("--fallback-profile",action="store_true",
                        help="use the existing 8/8 graph-enabled fallback profile")
    parser.add_argument("--center",nargs=3,type=float,default=(.35725,-.07936,1.02634))
    parser.add_argument("--preplace",nargs=3,type=float,default=(.717123,-.304470,1.006590))
    args=parser.parse_args()
    prep=json.loads(Path(args.preparation).read_text())
    request=json.loads(Path(args.planner_request).read_text())
    ik=RuntimeGoalIK(request["robot_yaml_urdf"],request["T_body_model"],
                     request["T_link6_tcp"])
    grasp=np.asarray(prep["target_body_m"],dtype=float)
    rear=np.asarray(args.preplace,dtype=float)+np.array([-.15,0,0])
    rows=[]
    for index,(goal,meta) in enumerate(zip(prep["goal_candidates_rad"],
                                           prep["goal_candidate_metadata"])):
        rng=np.random.default_rng(2900+index)
        rotation=np.asarray(meta["target_rotation_body"],dtype=float)
        branch=nearest_level_roll_branch(rotation)
        q=np.asarray(goal,dtype=float);targets={"pregrasp":q.tolist()}
        valid=True;reason=None
        try:
            _,q,_,_=multistart(ik,grasp,rotation,q,rng);targets["grasp"]=q.tolist()
            lift=grasp+np.array([0,0,.10])
            _,q,_,_=multistart(ik,lift,rotation,q,rng);targets["lift100"]=q.tolist()
            # Center stays horizontal and uses the same 180-degree roll branch.
            _,q,_,_=multistart(ik,args.center,level_rotation(math.pi/2,branch),q,rng)
            targets["center"]=q.tolist()
            _,q,_,_=multistart(ik,rear,level_rotation(0,branch),q,rng)
            targets["rear_preplace_150mm"]=q.tolist()
            _,q,_,_=multistart(ik,args.preplace,level_rotation(0,branch),q,rng)
            targets["preplace"]=q.tolist()
        except ValueError as exc:
            valid=False;reason=str(exc)
        joint_rows=np.asarray(list(targets.values()),dtype=float)
        changes=np.linalg.norm(np.diff(joint_rows,axis=0),axis=1) if len(joint_rows)>1 else []
        rows.append({"grasp_symmetry_id":meta["grasp_symmetry_id"],
            "roll_branch":branch,"kinematic_chain_valid":valid,"failure":reason,
            "joint_targets_rad":targets,
            "joint_path_cost":float(np.sum(changes)),
            "max_stage_joint_distance_rad":float(np.max(changes)) if len(changes) else None,
            "requires_fresh_scene_curobo_per_free_space_leg":True})
    valid=[row for row in rows if row["kinematic_chain_valid"]]
    selected=min(valid,key=lambda row:(row["max_stage_joint_distance_rad"],
                                        row["joint_path_cost"])) if valid else None
    payload={"schema_version":1,
        "policy":"WHOLE_CHAIN_TWO_FINGER_SYMMETRY_PREFILTER_V1",
        "stages":["pregrasp","grasp","lift100","center",
                  "rear_preplace_150mm","preplace"],
        "candidates":rows,
        "selected_grasp_symmetry_id":selected["grasp_symmetry_id"] if selected else None,
        "selected_roll_branch":selected["roll_branch"] if selected else None,
        "planning_only":True,"execution_allowed":False}
    Path(args.output).write_text(json.dumps(payload,indent=2)+"\n")
    if args.bound_request and selected is not None:
        paired=list(zip(request["goal_candidates_rad"],
                        request["goal_candidate_metadata"]))
        paired.sort(key=lambda row:row[1].get("grasp_symmetry_id") !=
                    selected["grasp_symmetry_id"])
        request["goal_candidates_rad"]=[row[0] for row in paired]
        request["goal_candidate_metadata"]=[row[1] for row in paired]
        request["goal_rad"]=request["goal_candidates_rad"][0]
        request["whole_chain_symmetry_binding"]={
            "policy":payload["policy"],
            "selected_grasp_symmetry_id":selected["grasp_symmetry_id"],
            "roll_branch":selected["roll_branch"]}
        if args.fallback_profile:
            request["planning_parameters"].update(num_ik_seeds=8,
                num_trajopt_seeds=8,max_attempts=10,enable_graph_attempt=1)
            request["planner_profile_revision"]="FALLBACK_8_8_GRAPH_WHOLE_CHAIN_SYMMETRY"
        args.bound_request.write_text(json.dumps(request,indent=2)+"\n")
    print(json.dumps(payload,indent=2))
    if selected is None:raise SystemExit(2)


if __name__=="__main__":main()
