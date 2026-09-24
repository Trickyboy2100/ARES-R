#!/usr/bin/env python3
"""P3.8B1 frozen-scene component inflation/contact diagnostic (no hardware IO)."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ares_r.manipulation.contact_motion import TargetContactPolicy, validate_contact_approach
from ares_r.manipulation.gripper_component_collision import (
    build_gripper_component_model, component_boxes_body)
from ares_r.motion.execution_tool_envelope import build_execution_tool_envelope
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.perception.robot_collision import arm_link_transforms


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quat_rotation(q):
    w, x, y, z = map(float, q)
    return np.asarray([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                       [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                       [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def box_body(name, value, T_body_model):
    center_model = np.asarray(value["pose"][:3], dtype=float)
    rotation_model = quat_rotation(value["pose"][3:])
    return {"geometry_id": name,
            "center_body_m": (T_body_model[:3, :3] @ center_model + T_body_model[:3, 3]).tolist(),
            "rotation_body": (T_body_model[:3, :3] @ rotation_model).tolist(),
            "dims_m": list(value["dims"]),
            "half_extents_m": (np.asarray(value["dims"], dtype=float)/2).tolist()}


def arm_boxes_body(q, request):
    transforms = arm_link_transforms(Path(request["robot_yaml_urdf"]), q)
    body = np.asarray(request["T_body_model"], dtype=float)
    rows=[]
    for link, local in request["collision_model"]["arm_link_boxes"].items():
        pose=body @ transforms[link]
        center=(pose @ np.r_[local["center_m"],1.0])[:3]
        rows.append({"geometry_id":link,"center_body_m":center.tolist(),
                     "rotation_body":pose[:3,:3].tolist(),
                     "half_extents_m":list(local["half_extents_m"]),
                     "dims_m":(2*np.asarray(local["half_extents_m"])).tolist()})
    return rows, body @ transforms["link6"]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--epoch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    request=load(args.plan/"planner_request.json")
    planning=load(args.plan/"planning.json")
    observation=load(args.epoch/"manipulation_observation.json")
    report=load(args.epoch/"live_scene/scene/scene_report.json")
    target_xyz=np.asarray(observation["target"]["pose_m_rad"][:3],dtype=float)
    q_pre=np.asarray(planning["trajectory_points_rad"][-1],dtype=float)
    solver=RuntimeGoalIK(request["robot_yaml_urdf"],request["T_body_model"],request["T_link6_tcp"])
    pre_pose=solver.fk(q_pre); displacement=target_xyz-pre_pose[:3,3]
    length=float(np.linalg.norm(displacement)); direction=displacement/length
    if not .047 <= length <= .053: raise RuntimeError("frozen endpoint is not the 50mm pregrasp")
    qs=[]; ik=[]; seed=q_pre
    for progress in np.linspace(0,length,int(math.ceil(length/.002))+1):
        xyz=pre_pose[:3,3]+direction*progress
        solved=solver.solve(xyz,pre_pose[:3,:3],seed)
        seed=np.asarray(solved.joints_rad);qs.append(seed.tolist())
        ik.append({"progress_m":float(progress),"position_error_m":solved.position_error_m,
                   "orientation_error_deg":math.degrees(solved.orientation_error_rad)})
    target_id="observed_"+report["target_binding"]["primitive_id"]
    T=np.asarray(request["T_body_model"],dtype=float)
    world={name:box_body(name,value,T) for name,value in request["compiled_scene"]["cuboids"].items()}
    if target_id not in world: raise RuntimeError("epoch target primitive missing from frozen scene")
    target=world[target_id];obstacles={k:v for k,v in world.items() if k!=target_id}
    trials=[];selected=None
    for inflation in (.004,.002,0.0):
        component=build_gripper_component_model(request["collision_model"],40,inflation_m=inflation)
        envelope=build_execution_tool_envelope(request["collision_model"],
            request["controller_tool_pose_mm_rad"],max_opening_percent=40,
            use_component_geometry=True,component_inflation_m=inflation)
        trial_request=dict(request,execution_tool_envelope=envelope,
            compiled_scene=dict(request["compiled_scene"],cuboids={
                k:v for k,v in request["compiled_scene"]["cuboids"].items() if k!=target_id}))
        dense=validate_dense_world(qs,trial_request,subdivisions=4)
        samples=[]
        for q in qs:
            arms,link6=arm_boxes_body(q,request)
            samples.append({"tcp_position_body_m":solver.fk(q)[:3,3].tolist(),
                "components":{"arm_links":arms,"tool":[],"gripper":
                    component_boxes_body(component,request["collision_model"],link6)}})
        policy=TargetContactPolicy("p38b1-contact-v1",target_id,tuple(direction),length,.012,.002)
        try:
            contact=validate_contact_approach(samples,target,obstacles,policy,
                expected_component_revision=component["revision"])
            contact_error=None
        except Exception as exc:
            contact=None;contact_error=str(exc)
        row={"component_inflation_m":inflation,"component_revision":component["revision"],
             "non_target_dense_validation":dense,"contact_validation":contact,
             "contact_error":contact_error,"hard_valid":dense["collision_free"] and contact is not None}
        trials.append(row)
        if row["hard_valid"] and selected is None:
            selected=row
            break
    payload={"schema_version":1,"planning_only":True,"hardware_io":False,
        "source_scene_snapshot_id":request["scene_snapshot_id"],
        "source_scene_digest":request["scene_digest"],
        "pointcloud_sha256":report["pointcloud_sha256"],"target_id":target_id,
        "target_body_m":target_xyz.tolist(),"pregrasp_body_m":pre_pose[:3,3].tolist(),
        "approach_direction_body":direction.tolist(),"approach_length_m":length,
        "contact_points_rad":qs,"continuous_ik":ik,"trials":trials,
        "selected_component_inflation_m":None if selected is None else selected["component_inflation_m"],
        "selected_component_revision":None if selected is None else selected["component_revision"],
        "GRASP_ENDPOINT_HARD_VALID":bool(selected),
        "PREGRASP_TO_GRASP_CONTACT_PLAN_READY":bool(selected),
        "execution_allowed":False}
    core=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    payload["artifact_sha256"]=hashlib.sha256(core).hexdigest()
    write(args.output/"contact_inflation_sweep.json",payload)
    print(json.dumps({k:payload[k] for k in ("target_id","approach_length_m",
        "selected_component_inflation_m","selected_component_revision",
        "GRASP_ENDPOINT_HARD_VALID","PREGRASP_TO_GRASP_CONTACT_PLAN_READY")},indent=2))
    if selected is None:return 2
    return 0


if __name__=="__main__": raise SystemExit(main())
