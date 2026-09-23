#!/usr/bin/env python3
"""Fresh BODY cloud + live read-only state -> P3 SceneSnapshot/cuRobo world.

No hardware adapter is imported. Camera capture and JAKA state acquisition must
already have produced the explicit input artifacts.
"""

import argparse,hashlib,json,math,time
from pathlib import Path
import sys
import numpy as np

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.perception.body_pointcloud import load_artifact
from ares_r.perception.residual_cloud import PROFILES,DEFAULT_PROFILE,clean_and_cluster
from ares_r.perception.robot_collision import (arm_link_transforms,inactive_arm_obstacles,
    load_geometry_snapshot,self_filter_body_cloud,transform_xyz_rpy)
from ares_r.perception.robot_owned_filter import build_robot_owned_filter,filter_robot_owned
from ares_r.perception.support_decomposition import (decompose_support_objects,
    refine_robot_adjacent_primitives)
from ares_r.world import (CalibrationSet,PointCloudRef,PoseSE3,RobotState,SafetyConstraint,
    SceneObject,SceneObjectRole,WorldModel,compile_snapshot,snapshot_dict)

def deployment_prefilter(points, voxel_m, roi):
    """Conservative ROI + one-point-per-voxel reduction before geometry tests."""
    at=time.perf_counter();points=np.asarray(points)
    low,high=np.asarray(roi[0]),np.asarray(roi[1])
    mask=np.all((points>=low)&(points<=high),axis=1);cropped=points[mask]
    if voxel_m<=0:
        return cropped,{"enabled":False,"input_points":len(points),
                        "roi_points":len(cropped),"output_points":len(cropped),
                        "elapsed_s":time.perf_counter()-at}
    keys=np.floor((cropped-low)/voxel_m).astype(np.int32)
    _,indices=np.unique(keys,axis=0,return_index=True)
    reduced=cropped[np.sort(indices)]
    return reduced,{"enabled":True,"voxel_m":voxel_m,"input_points":len(points),
                    "roi_points":len(cropped),"output_points":len(reduced),
                    "elapsed_s":time.perf_counter()-at}


def load(path):return json.loads(Path(path).read_text(encoding="utf-8"))


def quaternion(matrix):
    m=np.asarray(matrix)[:3,:3];t=np.trace(m)
    if t>0:
        s=math.sqrt(t+1.0)*2; q=[.25*s,(m[2,1]-m[1,2])/s,(m[0,2]-m[2,0])/s,(m[1,0]-m[0,1])/s]
    else:
        i=int(np.argmax(np.diag(m)));j=(i+1)%3;k=(i+2)%3;s=math.sqrt(1+m[i,i]-m[j,j]-m[k,k])*2
        xyz=[0.,0.,0.];xyz[i]=.25*s;xyz[j]=(m[j,i]+m[i,j])/s;xyz[k]=(m[k,i]+m[i,k])/s
        q=[(m[k,j]-m[j,k])/s]+xyz
    q=np.asarray(q);return (q/np.linalg.norm(q)).tolist()


def obb_aabb(box):
    center=np.asarray(box["center_body_m"]);rotation=np.asarray(box["rotation_body"])
    half=np.asarray(box["half_extents_m"])
    corners=np.asarray([center+rotation@(half*np.asarray([x,y,z]))
                        for x in (-1,1) for y in (-1,1) for z in (-1,1)])
    low,high=corners.min(0),corners.max(0)
    return ((low+high)/2).tolist(),(high-low).tolist()


def targets(active,audit,world,model,existing=None,goal_delta_rad=None):
    start=np.asarray(audit["diagnostics"]["joint_position_rad"],dtype=float)
    if existing:
        value=load(existing)
        if value["active_arm"]!=active or np.max(np.abs(start-np.asarray(value["start_rad"])))>1e-4:
            raise RuntimeError("live start differs from CLEAR target contract; no stale A/B reuse")
        return value
    delta=np.asarray(goal_delta_rad if goal_delta_rad is not None else [0.0,0.40,0.0,0.0,0.0,0.0],dtype=float)
    if delta.shape != (6,) or not np.isfinite(delta).all():
        raise ValueError("goal delta must contain six finite joint radians")
    goal=start+delta
    root=Path(model["asset_root"])/model["urdf"]
    correction=np.asarray(audit["T_controller_model"])
    arm=world["arms"][active]
    body_model=transform_xyz_rpy(arm["base_xyz_m"],arm["base_rpy_rad"])@correction
    tool=audit["diagnostics"]["tool_data"]["pose_mm_rad"]
    link_tcp=transform_xyz_rpy(np.asarray(tool[:3])*.001,tool[3:])
    def matrix(q):return body_model@arm_link_transforms(root,q)["link6"]@link_tcp
    A,B=matrix(start),matrix(goal)
    return {"schema_version":1,"contract":"P3_AB_BODY_EXPLICIT","active_arm":active,
            "orientation_contract":"explicit quaternion_wxyz from full-SE3 FK; no Euler default",
            "A":{"frame":"BODY","xyz_m":A[:3,3].tolist(),"quaternion_wxyz":quaternion(A)},
            "B":{"frame":"BODY","xyz_m":B[:3,3].tolist(),"quaternion_wxyz":quaternion(B)},
            "start_rad":start.tolist(),"goal_rad":goal.tolist(),
            "goal_delta_rad":delta.tolist(),
            "construction":"audited live start plus explicit planning-only joint delta; BODY A/B are full-SE3 FK",
            "execution_allowed":False}


def add(objects,observation,identifier,role,center,dims,inflation,source):
    objects.append(SceneObject(identifier,role,"cuboid",PoseSE3("body",tuple(center),(1,0,0,0)),
                               tuple(max(.001,float(x)) for x in dims),float(inflation),observation,
                               confidence=1.0))
    return {"id":identifier,"source":source,"center_m":center,"dims_m":dims,"inflation_m":inflation}


def main():
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=("LIVE","CLEAR","AVOID","BLOCK"),required=True)
    p.add_argument("--manifest",required=True);p.add_argument("--geometry",required=True)
    p.add_argument("--left-audit",required=True);p.add_argument("--right-audit",required=True)
    p.add_argument("--model",default="config/robot_collision_model.json");p.add_argument("--world",default="config/robot_world.json")
    p.add_argument("--targets");p.add_argument("--active",choices=("left","right"),default="right")
    p.add_argument("--goal-delta-rad",type=float,nargs=6,
                   help="planning-only joint delta used when creating a new A/B contract")
    p.add_argument("--self-filter-margin-m",type=float,default=.030,
                   help="canonical robot-geometry self-filter margin (default: 30 mm)")
    p.add_argument("--gripper-self-filter-margin-m",type=float,default=.020,
                   help="gripper-only observed-point ownership margin (default: 20 mm)")
    p.add_argument("--capture-pointer",
                   help="optional capture pointer with camera capture and end-to-end timings")
    p.add_argument("--obstacle-pipeline",choices=("single_aabb","multi_primitive"),
                   default="single_aabb",
                   help="retain P3 fail-closed baseline or use P3.1 support decomposition")
    p.add_argument("--deployment-voxel-m",type=float,default=0.0,
                   help="early conservative BODY ROI voxelization; 0 keeps legacy path")
    p.add_argument("--output",required=True);a=p.parse_args();started=time.perf_counter()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    cloud,meta=load_artifact(Path(a.manifest));geometry=load_geometry_snapshot(Path(a.geometry))
    audits={"left":load(a.left_audit),"right":load(a.right_audit)};model,world=load(a.model),load(a.world)
    scene_profile=load(REPOSITORY/"config/ab_demo_deployment_profile.json")["scene"]
    roi=scene_profile["body_roi_m"]
    if a.targets and a.goal_delta_rad is not None:
        raise ValueError("--targets and --goal-delta-rad are mutually exclusive")
    contract=targets(a.active,audits[a.active],world,model,a.targets,a.goal_delta_rad)
    (out/"targets.json").write_text(json.dumps(contract,indent=2)+"\n")
    if not 0.0 <= a.self_filter_margin_m <= 0.05:
        raise ValueError("self-filter margin must be between 0 and 50 mm")
    if a.deployment_voxel_m not in (0.0,.005,.0075,.010):
        raise ValueError("deployment voxel must be 0, 5, 7.5, or 10 mm")
    prefiltered,prefilter=deployment_prefilter(cloud.points_body_m,a.deployment_voxel_m,roi)
    sf_at=time.perf_counter();robot_owned=None
    if a.obstacle_pipeline=="multi_primitive":
        robot_owned=build_robot_owned_filter(geometry,planning_sphere_cell_m=.035,
                                             obb_sensor_margin_m=.020,
                                             gripper_sensor_margin_m=a.gripper_self_filter_margin_m,
                                             sphere_sensor_margin_m=.003)
        keep,sf=filter_robot_owned(prefiltered,robot_owned)
    else:
        keep,sf=self_filter_body_cloud(prefiltered,geometry,a.self_filter_margin_m)
    sf_s=time.perf_counter()-sf_at
    profile=next(x for x in PROFILES if x.name==DEFAULT_PROFILE)
    cleanup_at=time.perf_counter();clean,boxes,cleanup=clean_and_cluster(prefiltered[keep],roi,profile)
    cleanup_s=time.perf_counter()-cleanup_at;np.savez_compressed(out/"clean_residual.npz",points_body_m=clean)
    decomposition=None;decomposition_s=0.0
    planning_boxes=boxes
    if a.obstacle_pipeline=="multi_primitive":
        decomposition_at=time.perf_counter()
        decomposition=decompose_support_objects(clean,boxes)
        decomposition=refine_robot_adjacent_primitives(clean,decomposition,robot_owned)
        decomposition_s=time.perf_counter()-decomposition_at
        planning_boxes=decomposition["primitives"]
        (out/"support_decomposition.json").write_text(json.dumps(decomposition,indent=2)+"\n")
    runtime="p3-%s-%d"%(a.mode.lower(),time.time_ns());noww,nowm=time.time_ns(),time.monotonic_ns()
    wm=WorldModel(runtime_id=runtime,snapshot_ttl_s=3600,environment_ttl_s=3600)
    wm.update_robot_state(RobotState(noww,nowm,runtime,left_joints_rad=tuple(geometry.joints_rad["left"]),
        right_joints_rad=tuple(geometry.joints_rad["right"]),source_revisions=(("geometry_scene",geometry.scene_revision),)))
    obs=wm.begin_observation("OBS_P3_%s_%d"%(a.mode,time.time_ns()),noww,nowm)
    cloud_ref=PointCloudRef(Path(a.manifest).parent.name,cloud.source_sha256,"body")
    wm.register_pointcloud(obs,cloud_ref);objects=[];provenance=[]
    table=meta["table_validation"];lo,hi=table["xy_bounds_m"]
    provenance.append(add(objects,obs,"known_support_table",SceneObjectRole.FIXED,
        [(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,table["median_z_m"]-.020],
        [hi[0]-lo[0],hi[1]-lo[1],.040],0.0,"P1 table validation"))
    for box in planning_boxes:
        if a.obstacle_pipeline=="multi_primitive":
            identifier="observed_"+box["primitive_id"]
            source="P3.1 %s from observed points"%box["semantic"]
            inflation=box["inflation_m"]
        else:
            identifier=box["object_id"];source="clean Pixel Pro residual";inflation=.015
        provenance.append(add(objects,obs,identifier,SceneObjectRole.OBSTACLE,
                              box["center_m"],box["dims_m"],inflation,source))
    inactive=inactive_arm_obstacles(geometry,a.active)
    for box in inactive["boxes"]:
        if box["kind"]=="central_exclusion":
            provenance.append({"id":"central_body_exclusion","source":"SceneSnapshot SafetyConstraint",
                               "center_m":box["center_body_m"],
                               "dims_m":(2*np.asarray(box["half_extents_m"])).tolist(),
                               "inflation_m":0.0,"used_as":"TCP trajectory gate; not whole-arm cuboid"})
            continue
        center,dims=obb_aabb(box)
        provenance.append(add(objects,obs,"inactive_"+box["geometry_id"].replace("/","_"),
            SceneObjectRole.OBSTACLE,center,dims,.010 if box["kind"]!="central_exclusion" else 0.0,
            "P2 inactive-arm canonical geometry"))
    for box in geometry.boxes:
        if box.owner!="chassis":continue
        center,dims=obb_aabb(box.as_dict())
        low=np.asarray(center)-np.asarray(dims)/2;high=np.asarray(center)+np.asarray(dims)/2
        # The P2 full-height proxy overlaps the physical arm mounting volume by
        # design.  Collision-check the lower chassis, while the arm bases and
        # central exclusion account for the upper mounting region.
        high[2]=min(high[2],1.0);center=((low+high)/2).tolist();dims=(high-low).tolist()
        provenance.append(add(objects,obs,"body_chassis_lower",SceneObjectRole.FIXED,center,dims,0.0,
                              "P2 chassis XY envelope clipped at BODY z=1.0 below arm mounts"))
    if a.mode=="BLOCK":
        provenance.append(add(objects,obs,"synthetic_block_goal",SceneObjectRole.OBSTACLE,
                              contract["B"]["xyz_m"],[.24,.24,.24],.010,
                              "P3 explicitly labelled synthetic goal enclosure"))
    wm.register_obstacles(obs,objects,cloud_ref.pointcloud_id,cloud_ref.sha256)
    filter_revision=(robot_owned.revision if robot_owned else "P2_OBB_MARGIN_%.3f"%a.self_filter_margin_m)
    decomposition_revision=("sha256:"+hashlib.sha256(json.dumps(decomposition,sort_keys=True,
        separators=(",",":")).encode()).hexdigest() if decomposition else "single_aabb")
    wm.register_calibration(obs,CalibrationSet((("T_body_camera",cloud.transform_revision),
        ("T_body_camera_validation",cloud.validation_revision),("robot_geometry",geometry.geometry_revision),
        ("robot_joint_snapshot",geometry.joint_snapshot_revision),("residual_cleanup",DEFAULT_PROFILE),
        ("robot_owned_filter",filter_revision),("obstacle_decomposition",decomposition_revision))))
    wm.commit_observation(obs)
    snapshot=wm.freeze_snapshot(geometry.geometry_revision,geometry.tool_revision,
        constraints=(SafetyConstraint("central_body_exclusion","body_y_forbidden",(("half_width_m",.07),)),))
    compile_at=time.perf_counter();arm=world["arms"][a.active]
    T_body_model=transform_xyz_rpy(arm["base_xyz_m"],arm["base_rpy_rad"])@np.asarray(audits[a.active]["T_controller_model"])
    compiled=compile_snapshot(snapshot,a.active,T_body_model,planning_scope="P3_PRODUCTION_PLANNING_ONLY")
    compile_s=time.perf_counter()-compile_at
    (out/"snapshot.json").write_text(json.dumps(snapshot_dict(snapshot),indent=2)+"\n")
    (out/"compiled_scene.json").write_text(json.dumps(compiled,indent=2)+"\n")
    capture_pointer=load(a.capture_pointer) if a.capture_pointer else {}
    report={"schema_version":1,"mode":a.mode,"planning_only":True,"execution_allowed":False,
        "fresh_manifest":str(Path(a.manifest).resolve()),"pointcloud_sha256":cloud.source_sha256,
        "snapshot_id":snapshot.snapshot_id,"planning_context_digest":snapshot.planning_context_digest,
        "compiled_scene_digest":compiled["digest"],"calibration_revision":cloud.transform_revision,
        "geometry_revision":geometry.geometry_revision,"joint_snapshot_revision":geometry.joint_snapshot_revision,
        "tool_revision":geometry.tool_revision,"inactive_arm_revision":inactive["revision"],
        "obstacle_pipeline":a.obstacle_pipeline,"deployment_prefilter":prefilter,
        "generic_scene_profile":scene_profile,
        "self_filter":sf,"cleanup":cleanup,
        "robot_owned_filter":robot_owned.as_dict() if robot_owned else None,
        "support_decomposition":decomposition,"old_single_aabb_obstacles":boxes,
        "objects":provenance,"T_body_model":T_body_model.tolist(),
        "timing_s":{"camera_capture":capture_pointer.get("camera_capture_elapsed_s"),
                    "capture_body_total":capture_pointer.get("capture_body_total_s"),
                    "camera_to_body":cloud.timings_s.get("unit_and_rigid_transform"),
                    "early_roi_voxel":prefilter["elapsed_s"],
                    "self_filter":sf_s,"outlier_voxel_cluster_aabb":cleanup_s,
                    "support_decomposition_primitive_generation":decomposition_s,
                    "scene_snapshot_compiler":compile_s,"total_post_capture":time.perf_counter()-started}}
    (out/"scene_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"mode":a.mode,"snapshot_id":snapshot.snapshot_id,"objects":len(objects),
                      "residual_boxes":len(boxes),"planning_primitives":len(planning_boxes),
                      "obstacle_pipeline":a.obstacle_pipeline,"target_A":contract["A"]["xyz_m"],
                      "target_B":contract["B"]["xyz_m"],"timing_s":report["timing_s"]},indent=2))


if __name__=="__main__":main()
