"""Atomic whole-chain branch selection for two-finger pick/place tasks.

The capability selects one grasp symmetry and one compatible IK branch across
the task.  It deliberately does *not* create a trajectory across an AMR move:
place-side motion is rebound and replanned after the base settles and a new
SceneSnapshot exists.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ares_r.motion.tcp_orientation import (level_rotation,
                                           nearest_level_roll_branch,
                                           tcp_yaw_rad)
from .grasp_symmetry import two_finger_grasp_rotations


STAGES=("pregrasp","grasp","lift","center","rear_preplace","preplace")
FREE_SEGMENTS=(("current","pregrasp","PICK_SCENE"),
               ("lift","center","POST_PICK_SCENE"),
               ("center","rear_preplace","PLACE_SCENE_REBIND"),
               ("rear_preplace","preplace","PLACE_SCENE_REBIND"))


@dataclass(frozen=True)
class IKNode:
    stage: str
    joints_rad: tuple
    yaw_rad: float
    min_singular_value: float
    joint_limit_margin_rad: float
    position_error_m: float = 0.0
    orientation_error_deg: float = 0.0

    def as_dict(self):
        return {"stage":self.stage,"joints_rad":list(self.joints_rad),
            "yaw_rad":self.yaw_rad,"min_singular_value":self.min_singular_value,
            "joint_limit_margin_rad":self.joint_limit_margin_rad,
            "position_error_m":self.position_error_m,
            "orientation_error_deg":self.orientation_error_deg}


@dataclass(frozen=True)
class TransferChainRequest:
    observation_id: str
    scene_snapshot_id: str
    current_joints_rad: tuple
    grasp_position_body_m: tuple
    grasp_rotation_body: tuple
    approach_direction_body: tuple
    pregrasp_distance_m: float
    lift_distance_m: float
    center_position_body_m: tuple
    preplace_position_body_m: tuple
    rear_offset_body_m: tuple=(-.15,0.,0.)
    place_yaw_rad: float=0.0
    historical_center_joints_seed: tuple=()
    beam_width: int=4
    full_chain_candidates_per_symmetry: int=2

    def validate(self):
        if len(self.current_joints_rad)!=6:raise ValueError("six current joints required")
        if self.beam_width<1 or self.beam_width>8:raise ValueError("beam_width must be 1..8")
        if self.full_chain_candidates_per_symmetry not in (1,2,3):
            raise ValueError("retain only 1..3 full-chain candidates per symmetry")
        if not self.observation_id or not self.scene_snapshot_id:
            raise ValueError("fresh observation and SceneSnapshot bindings required")


def _edge_cost(left: IKNode, right: IKNode):
    delta=np.abs(np.asarray(right.joints_rad)-np.asarray(left.joints_rad))
    continuity=float(np.linalg.norm(delta)+.35*np.max(delta))
    singularity=.015/max(float(right.min_singular_value),1e-4)
    limit=.01/max(float(right.joint_limit_margin_rad),1e-3)
    return continuity+singularity+limit,{"l2_rad":float(np.linalg.norm(delta)),
        "max_joint_delta_rad":float(np.max(delta)),
        "singularity_penalty":singularity,"joint_limit_penalty":limit}


def _digest(value):
    return "sha256:"+hashlib.sha256(json.dumps(value,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()


class TransferChainPlanner:
    """Bounded multi-IK + dynamic-programming + persistent-cuRobo selector."""

    def __init__(self,ik_backend,segment_validator):
        self.ik=ik_backend;self.segment_validator=segment_validator

    def _targets(self,request,rotation,roll_branch):
        grasp=np.asarray(request.grasp_position_body_m,dtype=float)
        direction=np.asarray(request.approach_direction_body,dtype=float)
        pregrasp=grasp-float(request.pregrasp_distance_m)*direction
        lift=grasp+np.array([0,0,float(request.lift_distance_m)])
        preplace=np.asarray(request.preplace_position_body_m,dtype=float)
        rear=preplace+np.asarray(request.rear_offset_body_m,dtype=float)
        center_yaw=tcp_yaw_rad(rotation)
        yaw_offsets=(0.,math.radians(30),math.radians(-30),math.radians(60),
                     math.radians(-60),math.radians(90),math.radians(-90))
        return {
            "pregrasp":[(pregrasp,rotation,tcp_yaw_rad(rotation))],
            "grasp":[(grasp,rotation,tcp_yaw_rad(rotation))],
            "lift":[(lift,rotation,tcp_yaw_rad(rotation))],
            "center":[(np.asarray(request.center_position_body_m,dtype=float),
                       level_rotation(center_yaw+offset,roll_branch),center_yaw+offset)
                      for offset in yaw_offsets],
            "rear_preplace":[(rear,level_rotation(request.place_yaw_rad,roll_branch),
                               request.place_yaw_rad)],
            "preplace":[(preplace,level_rotation(request.place_yaw_rad,roll_branch),
                          request.place_yaw_rad)],
        }

    def _branch(self,request,symmetry_id,rotation):
        roll_branch=nearest_level_roll_branch(rotation)
        targets=self._targets(request,rotation,roll_branch)
        start=IKNode("current",tuple(request.current_joints_rad),
                     tcp_yaw_rad(rotation),1.0,1.0)
        beam=[(0.0,[start],[])]
        stage_counts={}
        for stage in STAGES:
            seeds=[path[-1].joints_rad for _,path,_ in beam]
            if stage=="center" and request.historical_center_joints_seed:
                seeds.append(request.historical_center_joints_seed)
            nodes=[]
            for position,target_rotation,yaw in targets[stage]:
                nodes.extend(self.ik.solve_candidates(stage,position,target_rotation,seeds,
                    max_solutions=request.beam_width))
            unique={tuple(round(v,5) for v in node.joints_rad):node for node in nodes}
            nodes=list(unique.values());stage_counts[stage]=len(nodes)
            next_beam=[]
            for score,path,edges in beam:
                for node in nodes:
                    edge_score,edge=_edge_cost(path[-1],node)
                    next_beam.append((score+edge_score,path+[node],edges+[edge]))
            next_beam.sort(key=lambda row:row[0])
            beam=next_beam[:request.beam_width]
            if not beam:break
        chains=[]
        for score,path,edges in beam[:request.full_chain_candidates_per_symmetry]:
            if len(path)!=len(STAGES)+1:continue
            chains.append({"branch_score":score,
                "nodes":[node.as_dict() for node in path],"edges":edges,
                "joint_continuity":{"sum_l2_rad":sum(x["l2_rad"] for x in edges),
                    "max_stage_joint_delta_rad":max(x["max_joint_delta_rad"] for x in edges)},
                "singularity_metrics":{"minimum_singular_value":min(
                    node.min_singular_value for node in path[1:]),
                    "per_stage":{node.stage:node.min_singular_value for node in path[1:]}},
                "stage_candidate_counts":stage_counts})
        return {"grasp_symmetry_id":symmetry_id,"roll_branch":roll_branch,
                "full_chain_candidates":chains}

    def plan(self,request: TransferChainRequest,artifact_path=None):
        request.validate();rotation=np.asarray(request.grasp_rotation_body,dtype=float)
        branches=[self._branch(request,name,value)
                  for name,value in two_finger_grasp_rotations(rotation)]
        validated=[]
        for branch in branches:
            for chain_index,chain in enumerate(branch["full_chain_candidates"]):
                by_stage={node["stage"]:node for node in chain["nodes"]}
                segment_results=[];hard_level=True;curobo_required=True
                for start_name,goal_name,boundary in FREE_SEGMENTS:
                    if boundary=="PLACE_SCENE_REBIND":
                        segment_results.append({"segment":start_name+"_to_"+goal_name,
                            "status":"PENDING_FRESH_PLACE_SCENE_REBIND",
                            "scene_boundary":boundary})
                        continue
                    start=(by_stage["current"] if start_name=="current" else by_stage[start_name])
                    result=dict(self.segment_validator.validate(
                        start_name+"_to_"+goal_name,start,by_stage[goal_name],
                        request.scene_snapshot_id,boundary,branch["grasp_symmetry_id"]))
                    result.update(segment=start_name+"_to_"+goal_name,
                                  scene_boundary=boundary)
                    segment_results.append(result)
                    curobo_required &= bool(result.get("curobo_pass"))
                    hard_level &= bool(result.get("hard_level_orientation_pass"))
                item=dict(chain);item.update({"grasp_symmetry_id":branch["grasp_symmetry_id"],
                    "roll_branch":branch["roll_branch"],"chain_index":chain_index,
                    "curobo_segment_results":segment_results,
                    "required_pre_rebind_curobo_pass":curobo_required,
                    "hard_level_orientation_validator_pass":hard_level})
                if curobo_required and hard_level:validated.append(item)
        validated.sort(key=lambda row:row["branch_score"])
        selected=validated[0] if validated else None
        artifact={"schema_version":1,"artifact_type":"TRANSFER_CHAIN_SELECTION",
            "immutable":True,"planning_only":True,"execution_allowed":False,
            "observation_id":request.observation_id,
            "scene_snapshot_id":request.scene_snapshot_id,
            "symmetry_scores":[{"grasp_symmetry_id":row["grasp_symmetry_id"],
                "roll_branch":row["roll_branch"],"full_chain_candidates":row["full_chain_candidates"]}
                for row in branches],
            "selected_grasp_symmetry_id":selected["grasp_symmetry_id"] if selected else None,
            "selected_center_ik":(next(node for node in selected["nodes"]
                if node["stage"]=="center") if selected else None),
            "selected_chain":selected,
            "scene_rebind_boundaries":[{"after":"center","event":"AMR_MOVE",
                "action":"INVALIDATE_SCENE_AND_TRAJECTORIES"},
                {"before":"center_to_rear_preplace","required":"FRESH_PLACE_SCENE"}],
            "WHOLE_CHAIN_BRANCH_SELECTED":"YES" if selected else "NO",
            "SELECTED_BRANCH_PREGRASP_CUROBO_PASS":"YES" if selected else "NO",
            "SELECTED_BRANCH_LIFT_TO_CENTER_CUROBO_PASS":"YES" if selected else "NO",
            "HARD_LEVEL_ORIENTATION_VALIDATOR_PASS":"YES" if selected else "NO",
            "TASK_RUNTIME_AUTONOMOUS_BRANCH_SELECTION_READY":"YES" if selected else "NO"}
        artifact["artifact_digest"]=_digest(artifact)
        if artifact_path:
            path=Path(artifact_path)
            if path.exists():raise FileExistsError("refusing to overwrite immutable artifact")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(artifact,indent=2)+"\n")
        return artifact


class RuntimeMultiIKBackend:
    """Deterministic bounded multi-IK backend over the pinned robot model."""

    def __init__(self,runtime_ik,*,random_seed=290929,max_attempts_per_target=28):
        self.ik=runtime_ik;self.random_seed=int(random_seed)
        self.max_attempts=int(max_attempts_per_target)
        if not 4<=self.max_attempts<=48:
            raise ValueError("bounded multi-IK attempts must be 4..48")

    def _singularity(self,q):
        from scipy.spatial.transform import Rotation
        q=np.asarray(q,dtype=float);base=self.ik.fk(q);epsilon=1e-5;columns=[]
        for index in range(6):
            shifted=q.copy();shifted[index]+=epsilon;pose=self.ik.fk(shifted)
            linear=(pose[:3,3]-base[:3,3])/epsilon
            angular=Rotation.from_matrix(base[:3,:3].T@pose[:3,:3]).as_rotvec()/epsilon
            columns.append(np.r_[linear,angular])
        return float(np.linalg.svd(np.column_stack(columns),compute_uv=False)[-1])

    def solve_candidates(self,stage,position,rotation,seeds,max_solutions):
        from scipy.optimize import least_squares
        from scipy.spatial.transform import Rotation
        position=np.asarray(position,dtype=float);rotation=np.asarray(rotation,dtype=float)
        supplied=[np.asarray(seed,dtype=float) for seed in seeds if len(seed)==6]
        if not supplied:supplied=[(self.ik.lower+self.ik.upper)/2]
        seed_value=(self.random_seed+sum(map(ord,stage))+
                    int(abs(position).sum()*10000))
        rng=np.random.default_rng(seed_value)
        starts=list(supplied)
        while len(starts)<self.max_attempts:
            reference=supplied[len(starts)%len(supplied)]
            scale=(.20,.45,.80,1.20)[len(starts)%4]
            starts.append(np.clip(reference+rng.normal(0,scale,6),
                                  self.ik.lower,self.ik.upper))
        answers=[]
        def residual(q):
            pose=self.ik.fk(q)
            angular=Rotation.from_matrix(rotation.T@pose[:3,:3]).as_rotvec()
            return np.r_[pose[:3,3]-position,.18*angular]
        for initial in starts[:self.max_attempts]:
            value=least_squares(residual,np.clip(initial,self.ik.lower,self.ik.upper),
                bounds=(self.ik.lower,self.ik.upper),max_nfev=140,
                xtol=1e-8,ftol=1e-8,gtol=1e-8)
            pose=self.ik.fk(value.x)
            pe=float(np.linalg.norm(pose[:3,3]-position))
            oe=float(np.linalg.norm(Rotation.from_matrix(
                rotation.T@pose[:3,:3]).as_rotvec()))
            if pe>.002 or oe>math.radians(.8):continue
            if any(np.linalg.norm(value.x-np.asarray(row.joints_rad))<.03 for row in answers):
                continue
            margin=float(np.min(np.minimum(value.x-self.ik.lower,
                                           self.ik.upper-value.x)))
            answers.append(IKNode(stage,tuple(float(v) for v in value.x),
                tcp_yaw_rad(rotation),self._singularity(value.x),margin,pe,
                math.degrees(oe)))
        answers.sort(key=lambda node:(-node.min_singular_value,
            -node.joint_limit_margin_rad,
            min(np.linalg.norm(np.asarray(node.joints_rad)-seed) for seed in supplied)))
        return answers[:int(max_solutions)]


class PersistentCuroboSegmentValidator:
    """Bounded FAST->FALLBACK adapter; never starts one worker per IK node."""

    def __init__(self,fast_planner,fallback_planner,request_builder,scene_resolver,
                 artifact_root):
        self.fast=fast_planner;self.fallback=fallback_planner
        self.request_builder=request_builder;self.scene_resolver=scene_resolver
        self.root=Path(artifact_root)

    def validate(self,name,start,goal,scene_snapshot_id,boundary,symmetry):
        scene=self.scene_resolver(scene_snapshot_id,boundary)
        if scene.get("scene_snapshot_id")!=scene_snapshot_id:
            raise RuntimeError("persistent cuRobo scene binding mismatch")
        motion=self.request_builder(name,start,goal,symmetry,boundary)
        attempts=[];result=None
        for profile,planner in (("FAST",self.fast),("FALLBACK",self.fallback)):
            output=self.root/(symmetry.lower()+"_"+name.lower()+"_"+profile.lower())
            if output.exists():
                raise FileExistsError("refusing to reuse cuRobo segment artifact")
            try:value=dict(planner(motion,scene,output))
            except Exception as exc:
                attempts.append({"profile":profile,"pass":False,
                                 "error":"%s: %s"%(type(exc).__name__,exc)})
                continue
            hard=bool((value.get("orientation_validation") or {}).get("passed"))
            passed=value.get("observed_result")=="SUCCESS" and hard
            trajectory_hash=value.get("trajectory_hash")
            if trajectory_hash is None and value.get("trajectory_points_rad"):
                trajectory_hash=_digest(value["trajectory_points_rad"])
            attempts.append({"profile":profile,"pass":passed,
                "trajectory_hash":trajectory_hash,
                "minimum_clearance_m":(value.get("clearance_m") or {}).get("planned_path"),
                "hard_level_orientation_pass":hard})
            if passed:result=value;break
        chosen=next((row for row in attempts if row["pass"]),None)
        return {"curobo_pass":chosen is not None,
            "hard_level_orientation_pass":bool(chosen and
                chosen["hard_level_orientation_pass"]),
            "profile":chosen["profile"] if chosen else None,
            "trajectory_hash":chosen.get("trajectory_hash") if chosen else None,
            "minimum_clearance_m":chosen.get("minimum_clearance_m") if chosen else None,
            "attempts":attempts,"persistent_planner":True,
            "maximum_curobo_solves":2}


class TransferChainSkillService:
    """TaskRuntime-facing owner of immutable transfer-chain selections."""

    def __init__(self,planner,artifact_root):
        self.planner=planner;self.artifact_root=Path(artifact_root)

    def prepare(self,payload):
        request=payload["binding"].get("transfer_chain_request")
        if not isinstance(request,TransferChainRequest):
            raise RuntimeError("transfer_chain_request binding required")
        return {"request":request,"planning_only":True}

    def bind(self,payload):
        request=payload["plan"]["request"]
        path=self.artifact_root/(request.observation_id+"_transfer_chain_selection.json")
        artifact=self.planner.plan(request,path)
        if artifact["WHOLE_CHAIN_BRANCH_SELECTED"]!="YES":
            raise RuntimeError("no full-chain branch passed cuRobo and hard-level gates")
        return {"artifact_id":artifact["artifact_digest"],"artifact_path":str(path),
                "selected_grasp_symmetry_id":artifact["selected_grasp_symmetry_id"],
                "center_tcp_position_solution":artifact["selected_center_ik"]}
