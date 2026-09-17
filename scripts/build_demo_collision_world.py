#!/usr/bin/env python3
"""Build an OFFLINE_ONLY BODY-candidate collision world from a real Pixel Pro frame."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d

from ares_r.world import (
    CalibrationSet, PointCloudRef, PoseSE3, RobotState, SafetyConstraint,
    SceneObject, SceneObjectRole, WorldModel, compile_snapshot,
)


def rigid(xyz, rpy):
    r, p, y = rpy; cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    value = np.eye(4); value[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
        [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr+cy*sr], [-sp, cp*sr, cp*cr]]; value[:3, 3] = xyz
    return value


def transform_points(points, matrix):
    return (np.c_[points, np.ones(len(points))] @ np.asarray(matrix).T)[:, :3]


def capsule(a, b, radius, spacing=.045, source="proxy"):
    a, b = np.asarray(a), np.asarray(b); length = float(np.linalg.norm(b-a)); count = max(2, int(math.ceil(length/spacing))+1)
    return [{"center_body_m": (a+(b-a)*value).tolist(), "radius_m": radius,
             "proxy": True, "source": source} for value in np.linspace(0, 1, count)]


def plot(points, path, title, boxes=(), robot=(), table=None, watermark=True):
    sample = points[::max(1, len(points)//70000)] if len(points) else points
    figure = plt.figure(figsize=(14, 10)); axis = figure.add_subplot(111, projection="3d")
    if len(sample): axis.scatter(sample[:, 0], sample[:, 1], sample[:, 2], s=.35, alpha=.3, color="0.35")
    for sphere in robot:
        center = sphere["center_body_m"]; axis.scatter(*center, s=max(4, sphere["radius_m"]*280), color="tab:orange", alpha=.7)
    for box in boxes:
        low, high = np.asarray(box["min_m"]), np.asarray(box["max_m"])
        for z in (low[2], high[2]): axis.plot([low[0],high[0],high[0],low[0],low[0]], [low[1],low[1],high[1],high[1],low[1]], [z]*5, "r-", lw=.7)
        for x in (low[0],high[0]):
            for y in (low[1],high[1]): axis.plot([x,x],[y,y],[low[2],high[2]],"r-",lw=.7)
    if table:
        low, high = np.asarray(table["min_m"]), np.asarray(table["max_m"])
        xx, yy = np.meshgrid([low[0], high[0]], [low[1], high[1]])
        axis.plot_surface(xx, yy, np.full_like(xx, high[2]), color="tab:blue", alpha=.18)
    xx, zz = np.meshgrid(np.linspace(-.62,.9,2), np.linspace(.43,1.97,2))
    for y in (-.07,.07): axis.plot_surface(xx,np.full_like(xx,y),zz,color="red",alpha=.07)
    axis.quiver(0,0,0,.2,0,0,color="r");axis.quiver(0,0,0,0,.2,0,color="g");axis.quiver(0,0,0,0,0,.2,color="b")
    axis.set(xlabel="BODY +X forward (m)",ylabel="BODY +Y left (m)",zlabel="BODY +Z up (m)",title=title)
    if watermark: figure.text(.5,.96,"DEMO_ONLY / NOT FOR EXECUTION",ha="center",color="crimson",fontsize=15,weight="bold")
    figure.tight_layout();figure.savefig(path,dpi=160);plt.close(figure)


def timed(records, name, before, after, started, **parameters):
    records.append({"stage":name,"point_count_before":int(before),"point_count_after":int(after),
                    "runtime_ms":(time.perf_counter()-started)*1000,"frame":"body_demo_candidate","parameters":parameters})


def main():
    parser=argparse.ArgumentParser();parser.add_argument("capture");parser.add_argument("--calibration",required=True)
    parser.add_argument("--support",required=True);parser.add_argument("--robot-geometry",required=True)
    parser.add_argument("--robot-state",required=True);parser.add_argument("--robot-world",required=True)
    parser.add_argument("--tools",required=True);parser.add_argument("--pointcloud-config",required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--voxel",type=float,default=.01)
    args=parser.parse_args();capture,output=Path(args.capture),Path(args.output);output.mkdir(parents=True,exist_ok=False)
    calibration=json.loads(Path(args.calibration).read_text());support=json.loads(Path(args.support).read_text())
    geometry=json.loads(Path(args.robot_geometry).read_text());state=json.loads(Path(args.robot_state).read_text());state=state.get("arms",state)
    world=json.loads(Path(args.robot_world).read_text());tools=json.loads(Path(args.tools).read_text());pcfg=json.loads(Path(args.pointcloud_config).read_text())
    if calibration["state"]!="DEMO_ONLY_UNCOMMISSIONED" or calibration["execution_allowed"] is not False: raise RuntimeError("demo-only calibration required")
    source=capture/"pointcloud.ply";source_sha=hashlib.sha256(source.read_bytes()).hexdigest();manifest=json.loads((capture/"manifest.json").read_text())
    calibration_revision="DEMO_ONLY:"+hashlib.sha256(Path(args.calibration).read_bytes()).hexdigest()
    records=[];cloud=o3d.io.read_point_cloud(str(source));raw=np.asarray(cloud.points,dtype=float)
    started=time.perf_counter();valid=raw[np.isfinite(raw).all(1)&(np.abs(raw).sum(1)>0)]/1000.;body=transform_points(valid,calibration["T_body_camera"])
    timed(records,"valid_mm_to_m_camera_to_demo_body",len(raw),len(body),started,calibration_revision=calibration_revision)
    plot(body,output/"01_camera_raw.png","01 real Pixel Pro cloud transformed for demo")
    table_z=float(calibration["support_height_body_m"]);plot(body,output/"02_level_table.png","02 support plane horizontal in DEMO BODY",table={"min_m":[-.62,-1.1,table_z-.03],"max_m":[.9,.99,table_z]})

    right_spheres=list(geometry["spheres"]);right_centers=np.asarray([s["center_body_m"] for s in right_spheres])
    body_right=rigid(world["arms"]["right"]["base_xyz_m"],world["arms"]["right"]["base_rpy_rad"])
    right_tcp=(body_right@(np.r_[state["right"]["tcp_position_mm_rad"][:3],1.0]/np.array([1000,1000,1000,1])))[:3]
    anchor=right_centers[np.argmin(np.linalg.norm(right_centers-right_tcp,axis=1))]
    tool_proxy=capsule(anchor,right_tcp,.055,source="right flange-to-live-TCP conservative proxy")
    body_left=rigid(world["arms"]["left"]["base_xyz_m"],world["arms"]["left"]["base_rpy_rad"])
    left_tcp=(body_left@(np.r_[state["left"]["tcp_position_mm_rad"][:3],1.0]/np.array([1000,1000,1000,1])))[:3]
    left_proxy=capsule(world["arms"]["left"]["base_xyz_m"],left_tcp,.11,source="inactive-left base-to-TCP conservative capsule")
    filter_spheres=right_spheres+tool_proxy+left_proxy
    plot(body,output/"03_demo_body_overlay.png","03 BODY overlay",robot=filter_spheres,table={"min_m":[-.62,-1.1,table_z-.02],"max_m":[.9,.99,table_z+.01]})

    roi=pcfg["roi_candidates"]["global"];low,high=np.asarray(roi["min_m"]),np.asarray(roi["max_m"])
    started=time.perf_counter();before=len(body);mask=np.all((body>=low)&(body<=high),axis=1);roi_points=body[mask]
    timed(records,"body_manipulation_roi",before,len(roi_points),started,bounds_m=[low.tolist(),high.tolist()])
    plot(roi_points,output/"04_body_roi.png","04 manipulation ROI")
    before_filter=roi_points.copy();started=time.perf_counter();keep=np.ones(len(roi_points),dtype=bool);margin=.025
    removed_dist=[]
    for sphere in filter_spheres:
        distance=np.linalg.norm(roi_points-np.asarray(sphere["center_body_m"]),axis=1)-float(sphere["radius_m"])
        removed_dist.extend(distance[distance<=margin].tolist());keep&=distance>margin
    filtered=roi_points[keep];timed(records,"robot_tool_self_filter",len(roi_points),len(filtered),started,
        sphere_count=len(filter_spheres),margin_m=margin,right_model_proxy=False,tool_proxy=True,inactive_left_proxy=True)
    # one figure, two panels represented by colour in a common BODY view
    figure=plt.figure(figsize=(14,10));axis=figure.add_subplot(111,projection="3d");a=before_filter[::max(1,len(before_filter)//50000)];b=filtered[::max(1,len(filtered)//50000)]
    axis.scatter(a[:,0],a[:,1],a[:,2],s=.3,alpha=.12,color="red",label="before");axis.scatter(b[:,0],b[:,1],b[:,2],s=.3,alpha=.4,color="green",label="after")
    axis.set(xlabel="BODY X",ylabel="BODY Y",zlabel="BODY Z",title="05 self-filter before(red)/after(green)");axis.legend();figure.text(.5,.96,"DEMO_ONLY / NOT FOR EXECUTION",ha="center",color="crimson",weight="bold");figure.tight_layout();figure.savefig(output/"05_self_filter_before_after.png",dpi=160);plt.close(figure)
    plot(filtered,output/"06_known_support_plus_robot.png","06 known support plus robot",robot=filter_spheres,table={"min_m":[low[0],low[1],table_z-.05],"max_m":[high[0],high[1],table_z]})

    started=time.perf_counter();before=len(filtered);residual=filtered[np.abs(filtered[:,2]-table_z)>.035]
    timed(records,"known_support_remove",before,len(residual),started,support_height_m=table_z,half_band_m=.035)
    started=time.perf_counter();vcloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(residual)).voxel_down_sample(args.voxel);voxel=np.asarray(vcloud.points)
    timed(records,"voxel",len(residual),len(voxel),started,voxel_m=args.voxel)
    started=time.perf_counter();labels=np.asarray(vcloud.cluster_dbscan(eps=.035,min_points=10,print_progress=False));boxes=[];inflation=.025
    for label in sorted(set(labels.tolist())-{-1}):
        points=voxel[labels==label]
        if len(points)<18:continue
        lo,hi=points.min(0)-inflation,points.max(0)+inflation
        # Ignore broad floor/background remnants; ROI/table are handled separately.
        if np.prod(np.maximum(hi-lo,.001))>1.0:continue
        boxes.append({"id":"unknown_%03d"%label,"role":"UNKNOWN_RESIDUAL","point_count":len(points),"min_m":lo.tolist(),"max_m":hi.tolist(),"center_m":((lo+hi)/2).tolist(),"dims_m":(hi-lo).tolist(),"inflation_m":inflation})
    timed(records,"cluster_aabb",len(voxel),sum(b["point_count"] for b in boxes),started,eps_m=.035,min_points=10,inflation_m=inflation,aabb_count=len(boxes))
    plot(voxel,output/"07_unknown_residual_clusters.png","07 unknown residual clusters",boxes=boxes)
    # The fitted plane is the physical support *top*, not the centre of a
    # symmetric slab.  Extending the cuboid above it invents occupied space.
    table={"id":"known_support_table","role":"KNOWN_SUPPORT","min_m":[low[0],low[1],table_z-.05],"max_m":[high[0],high[1],table_z]}
    plot(voxel,output/"08_final_collision_world.png","08 final demo collision world",boxes=boxes,robot=filter_spheres,table=table)

    runtime="DEMO_"+hashlib.sha256((manifest["frame_id"]+calibration_revision).encode()).hexdigest()[:16];now_wall,now_mono=time.time_ns(),time.monotonic_ns()
    model=WorldModel(runtime_id=runtime,snapshot_ttl_s=3600,environment_ttl_s=3600)
    robot_state=RobotState(now_wall,now_mono,runtime,left_joints_rad=tuple(state["left"]["joint_position_rad"]),right_joints_rad=tuple(state["right"]["joint_position_rad"]),source_revisions=(("scope","DEMO_OFFLINE_ONLY"),("state_source",str(args.robot_state))))
    model.update_robot_state(robot_state);obs=model.begin_observation("OBS_"+manifest["frame_id"].split("_")[0],now_wall,now_mono);pc=PointCloudRef(manifest["frame_id"],source_sha,"body_demo_candidate");model.register_pointcloud(obs,pc)
    objects=[]
    table_center=(np.asarray(table["min_m"])+np.asarray(table["max_m"]))/2;table_dims=np.asarray(table["max_m"])-np.asarray(table["min_m"])
    objects.append(SceneObject(table["id"],SceneObjectRole.FIXED,"cuboid",PoseSE3("body",tuple(table_center),(1,0,0,0)),tuple(table_dims),0.,obs))
    for box in boxes:objects.append(SceneObject(box["id"],SceneObjectRole.OBSTACLE,"cuboid",PoseSE3("body",tuple(box["center_m"]),(1,0,0,0)),tuple(box["dims_m"]),box["inflation_m"],obs))
    model.register_obstacles(obs,objects,pc.pointcloud_id,pc.sha256);model.register_calibration(obs,CalibrationSet((("T_body_camera",calibration_revision),("planning_scope","DEMO_OFFLINE_ONLY"))))
    model.commit_observation(obs);snapshot=model.freeze_snapshot(geometry["robot_model_sha256"],tools["arms"]["right"]["revision"],constraints=(SafetyConstraint("central_slab","body_y_forbidden",(("half_width_m",.07),)),),artifact_dir=output/"snapshots")
    compiled=compile_snapshot(snapshot,"right",geometry["T_body_model"]);(output/"compiled_scene.json").write_text(json.dumps(compiled,indent=2)+"\n")
    result={"schema_version":1,"state":"DEMO_OFFLINE_ONLY","execution_allowed":False,"planning_ready":False,"frame_id":manifest["frame_id"],"source_ply_sha256":source_sha,"calibration_candidate_revision":calibration_revision,"pipeline_records":records,"self_filter":{"before":len(before_filter),"after":len(filtered),"removed":len(before_filter)-len(filtered),"removed_distance_summary_m":{"min":min(removed_dist) if removed_dist else None,"median":float(np.median(removed_dist)) if removed_dist else None,"max":max(removed_dist) if removed_dist else None},"tool_proxy":True,"inactive_left_proxy":True},"known_support":table,"unknown_residual_aabbs":boxes,"scene_snapshot_id":snapshot.snapshot_id,"planning_context_digest":snapshot.planning_context_digest,"compiled_scene_digest":compiled["digest"]}
    (output/"pipeline.json").write_text(json.dumps(result,indent=2)+"\n");(output/"collision_world.json").write_text(json.dumps({"state":"DEMO_OFFLINE_ONLY","execution_allowed":False,"known_support":table,"unknown_residual_aabbs":boxes,"compiled_scene":compiled},indent=2)+"\n")
    print(json.dumps({"output":str(output),"frame_id":manifest["frame_id"],"roi":len(roi_points),"self_filtered":len(filtered),"voxel":len(voxel),"aabbs":len(boxes),"snapshot_id":snapshot.snapshot_id,"scene_digest":compiled["digest"]}))


if __name__=="__main__":main()
