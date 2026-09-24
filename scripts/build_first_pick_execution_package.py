#!/usr/bin/env python3
"""Build immutable P3.8B1A first-pick package; never sends hardware commands."""

import argparse,hashlib,json,math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from ares_r.manipulation.attached_collision import attach_scene_object,build_attached_collision
from ares_r.manipulation.contact_bypass import ContactBypassPolicy,validate_bypass_segment
from ares_r.manipulation.first_pick_package import verify_first_pick_package
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.world import PoseSE3,SceneObject,SceneObjectRole


def load(p):return json.loads(Path(p).read_text())
def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def qrot(q):
    w,x,y,z=map(float,q);return np.asarray([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def body_box(name,value,T):
    r=T[:3,:3]@qrot(value["pose"][3:]);c=T[:3,:3]@np.asarray(value["pose"][:3])+T[:3,3]
    return {"geometry_id":name,"center_body_m":c.tolist(),"rotation_body":r.tolist(),
            "dims_m":list(value["dims"]),"half_extents_m":(np.asarray(value["dims"])/2).tolist()}
def arm_geometry(q,request):
    frames=arm_link_transforms(Path(request["robot_yaml_urdf"]),q);T=np.asarray(request["T_body_model"])
    rows=[]
    for name in ("link1","link2","link3","link4","link5","link6"):
        local=request["collision_model"]["arm_link_boxes"][name];pose=T@frames[name]
        c=(pose@np.r_[local["center_m"],1.])[:3]
        rows.append({"geometry_id":name,"center_body_m":c.tolist(),"rotation_body":pose[:3,:3].tolist(),
            "half_extents_m":list(local["half_extents_m"]),
            "dims_m":(2*np.asarray(local["half_extents_m"])).tolist()})
    return rows
def trajectory_hash(points):return sha([[round(float(v),12) for v in row] for row in points])


def main():
    p=argparse.ArgumentParser();p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--epoch",type=Path,required=True);p.add_argument("--contact",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    request=load(a.plan/"planner_request.json");planning=load(a.plan/"planning.json")
    observation=load(a.epoch/"manipulation_observation.json");report=load(a.epoch/"live_scene/scene/scene_report.json")
    decomp=load(a.epoch/"live_scene/scene/support_decomposition.json");contact=load(a.contact/"contact_inflation_sweep.json")
    solver=RuntimeGoalIK(request["robot_yaml_urdf"],request["T_body_model"],request["T_link6_tcp"])
    q_contact=[list(map(float,row)) for row in contact["contact_points_rad"]]
    grasp_T=solver.fk(q_contact[-1]);world={k:body_box(k,v,np.asarray(request["T_body_model"]))
        for k,v in request["compiled_scene"]["cuboids"].items()}
    policy=ContactBypassPolicy.for_manipulation_skill("PICK_CONTACT_ESCAPE",observation["observation_id"])
    direction=np.asarray(contact["approach_direction_body"],dtype=float)
    approach_samples=[{"tcp_position_body_m":solver.fk(q)[:3,3].tolist(),"joints_rad":q,
                       "arm_links":arm_geometry(q,request)} for q in q_contact]
    approach_validation=validate_bypass_segment(approach_samples,world,policy,
        expected_direction_body=direction,joint_lower=solver.lower,joint_upper=solver.upper,
        expire_at_end=False)
    q_lift=[];seed=np.asarray(q_contact[-1]);start=grasp_T[:3,3]
    for z in np.linspace(0,.1,51):
        solved=solver.solve(start+[0,0,z],grasp_T[:3,:3],seed);seed=np.asarray(solved.joints_rad)
        q_lift.append(list(solved.joints_rad))
    lift_samples=[{"tcp_position_body_m":solver.fk(q)[:3,3].tolist(),"joints_rad":q,
                   "arm_links":arm_geometry(q,request)} for q in q_lift]
    lift_validation=validate_bypass_segment(lift_samples,world,policy,
        expected_direction_body=(0,0,1),joint_lower=solver.lower,joint_upper=solver.upper,
        expire_at_end=True)
    primitive_id=report["target_binding"]["primitive_id"]
    primitive=next(row for row in decomp["primitives"] if row["primitive_id"]==primitive_id)
    target=SceneObject("observed_"+primitive_id,SceneObjectRole.TARGET,"cuboid",
        PoseSE3("body",tuple(primitive["center_m"]),(1.,0.,0.,0.)),tuple(primitive["dims_m"]),
        0.,report["observation_id"])
    attached=attach_scene_object(target,grasp_T.tolist(),side="right",source_revision=policy.revision)
    attached_collision=build_attached_collision(attached,request["T_link6_tcp"],inflation_m=.004)
    params=load(ROOT/"config/tray_to_groove_v2.json")
    stages=[
      {"index":1,"action":"FRESH_ATOMIC_RIGHT_PICK_OBSERVATION","state":"BOUND"},
      {"index":2,"action":"CUROBO_MOVE_TO_50MM_PREGRASP","trajectory_hash":trajectory_hash(planning["trajectory_points_rad"])},
      {"index":3,"action":"GRIPPER_TO_40_PERCENT"},
      {"index":4,"action":"CONTACT_BYPASS_STRAIGHT_APPROACH","trajectory_hash":trajectory_hash(q_contact)},
      {"index":5,"action":"CLOSE_GRIPPER"},
      {"index":6,"action":"DELAYED_READBACK_AND_LOCAL_SCENE_DELTA","radius_m":params["grasp_verification"]["local_tcp_radius_m"]},
      {"index":7,"action":"IF_VERIFIED_BODY_Z_LIFT_100MM","trajectory_hash":trajectory_hash(q_lift)},
      {"index":8,"action":"EXPIRE_CONTACT_BYPASS_V1"},
      {"index":9,"action":"ACTIVATE_COARSE_ATTACHED_OBJECT","revision":attached_collision["revision"]},
      {"index":10,"action":"HOLD_STOP"}]
    package={"schema_version":1,"package_type":"FIRST_PICK_EXECUTION_PACKAGE",
      "immutable":True,"execution_allowed":False,"awaiting_user_authorization":True,
      "observation_id":observation["observation_id"],"scene_snapshot_id":observation["scene_snapshot_id"],
      "scene_digest":observation["scene_digest"],"pointcloud_sha256":observation["pointcloud_sha256"],
      "detection_id":observation["detection_id"],"target_pose_body_m_rad":observation["target"]["pose_m_rad"],
      "target_primitive_id":target.object_id,"pregrasp_distance_m":.05,
      "contact_bypass_policy":policy.as_dict(),"approach_validation":approach_validation,
      "lift_validation":lift_validation,"coarse_attached_object_collision":attached_collision,
      "controller_tool_pose_mm_rad":request["controller_tool_pose_mm_rad"],
      "tool_revision":report["tool_revision"],"geometry_revision":report["geometry_revision"],
      "inactive_arm_revision":report["inactive_arm_revision"],"gripper_commands":{
          "pregrasp_percent":40,"close_raw":params["gripper"]["raw_closed"]},
      "grasp_verification":params["grasp_verification"],"stages":stages,
      "trajectories":{"pregrasp":planning["trajectory_points_rad"],"contact":q_contact,"lift":q_lift},
      "FIRST_PICK_EXECUTION_PACKAGE_READY":True,"place_included":False}
    package["package_sha256"]=sha(package)
    verify_first_pick_package(package)
    (a.output/"first_pick_execution_package.json").write_text(json.dumps(package,indent=2)+"\n")
    summary={"CONTACT_BYPASS_V1_READY":True,"GENERIC_FREE_SPACE_STILL_FULL_COLLISION":True,
      "PREGRASP_TO_GRASP_BYPASS_PLAN_READY":True,"GRASP_VERIFICATION_READY":True,
      "INITIAL_100MM_BYPASS_LIFT_READY":True,"COARSE_ATTACHED_OBJECT_READY":True,
      "FIRST_PICK_EXECUTION_PACKAGE_READY":True,"package_sha256":package["package_sha256"],
      "package_path":str(a.output/"first_pick_execution_package.json")}
    (a.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
