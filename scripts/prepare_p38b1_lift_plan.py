#!/usr/bin/env python3
"""Build a derived close/attach/vertical-lift request from a valid P3.8B1 contact plan."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from ares_r.manipulation.attached_collision import attach_scene_object,build_attached_collision
from ares_r.motion.execution_tool_envelope import build_execution_tool_envelope
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.world import PoseSE3,SceneObject,SceneObjectRole


def load(path):return json.loads(Path(path).read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def quat(rotation):
    from scipy.spatial.transform import Rotation
    x,y,z,w=Rotation.from_matrix(rotation).as_quat()
    return (float(w),float(x),float(y),float(z))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--plan",type=Path,required=True)
    ap.add_argument("--epoch",type=Path,required=True);ap.add_argument("--contact",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    request=load(a.plan/"planner_request.json");contact=load(a.contact/"contact_inflation_sweep.json")
    report=load(a.epoch/"live_scene/scene/scene_report.json")
    decomp=load(a.epoch/"live_scene/scene/support_decomposition.json")
    if not contact["GRASP_ENDPOINT_HARD_VALID"]:raise RuntimeError("contact plan is not hard-valid")
    q_grasp=np.asarray(contact["contact_points_rad"][-1],dtype=float)
    solver=RuntimeGoalIK(request["robot_yaml_urdf"],request["T_body_model"],request["T_link6_tcp"])
    T_body_tcp=solver.fk(q_grasp);goal_xyz=T_body_tcp[:3,3]+[0,0,.1]
    goal=solver.solve(goal_xyz,T_body_tcp[:3,:3],q_grasp)
    primitive_id=report["target_binding"]["primitive_id"]
    primitive=next(row for row in decomp["primitives"] if row["primitive_id"]==primitive_id)
    target=SceneObject("observed_"+primitive_id,SceneObjectRole.TARGET,"cuboid",
        PoseSE3("body",tuple(primitive["center_m"]),(1.,0.,0.,0.)),
        tuple(primitive["dims_m"]),0.,report["observation_id"])
    attached=attach_scene_object(target,T_body_tcp.tolist(),side="right",
        source_revision="p38b1-contact:"+contact["artifact_sha256"])
    attached_collision=build_attached_collision(attached,request["T_link6_tcp"],inflation_m=.004)
    target_id=target.object_id
    cuboids={k:v for k,v in request["compiled_scene"]["cuboids"].items() if k!=target_id}
    # This is a derived post-grasp world transition, not point-cloud deletion:
    # the same target geometry moves atomically from world to attached geometry.
    scene=dict(request["compiled_scene"],cuboids=cuboids,
        scene_transition="TARGET_WORLD_TO_ATTACHED",attached_object_revision=attached_collision["revision"])
    scene["scene_snapshot_id"]="SCENE_P38B1_ATTACHED_"+digest(scene)[:20]
    scene["digest"]=digest(scene)
    scene["planning_context_digest"]=digest({"scene":scene["digest"],"attached":attached_collision["revision"]})
    envelope=build_execution_tool_envelope(request["collision_model"],
        request["controller_tool_pose_mm_rad"],max_opening_percent=0,
        use_component_geometry=True,component_inflation_m=0.)
    result=dict(request,compiled_scene=scene,scene_snapshot_id=scene["scene_snapshot_id"],
        scene_digest=scene["digest"],start_rad=q_grasp.tolist(),goal_rad=list(goal.joints_rad),
        goal_candidates_rad=[list(goal.joints_rad)],goal_candidate_metadata=[{
            "kind":"VERTICAL_LIFT_100MM","position_body_m":goal_xyz.tolist()}],
        execution_tool_envelope=envelope,attached_object_collision=attached_collision,
        motion_constraints=dict(request.get("motion_constraints",{}),
            attached_object_revision=attached_collision["revision"],gripper_max_opening_percent=0,
            gripper_component_geometry=True,gripper_component_inflation_m=0.),
        runtime_motion_goal=None,orientation_lock={"policy":"P38B1_VERTICAL_LIFT_FIXED_ORIENTATION",
            "target_R_body_tcp":T_body_tcp[:3,:3].tolist(),"max_error_deg":3.0},
        motion_contract="TARGET_ATTACHED_VERTICAL_LIFT_PLANNING_ONLY_V1")
    (a.output/"lift_request.json").write_text(json.dumps(result,indent=2)+"\n")
    manifest={"schema_version":1,"planning_only":True,"hardware_io":False,
        "source_contact_artifact_sha256":contact["artifact_sha256"],
        "target_world_object_id":target_id,"world_target_removed_only_after_attach":True,
        "attached_object_collision":attached_collision,"gripper_component_revision":
            envelope["component_model"]["revision"],"grasp_joints_rad":q_grasp.tolist(),
        "lift_goal_joints_rad":list(goal.joints_rad),"lift_goal_body_m":goal_xyz.tolist(),
        "lift_distance_body_z_m":.1,"execution_allowed":False}
    manifest["manifest_sha256"]=digest(manifest)
    (a.output/"lift_transition_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"request":str(a.output/"lift_request.json"),
        "attached_revision":attached_collision["revision"],"lift_goal_body_m":goal_xyz.tolist()},indent=2))


if __name__=="__main__":main()
