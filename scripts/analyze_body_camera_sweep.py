#!/usr/bin/env python3
"""Validate table-edge yaw with translation-only AMR sweep captures."""

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d


def cloud(path):
    value=o3d.io.read_point_cloud(str(path));points=np.asarray(value.points,dtype=float)
    points=points[np.isfinite(points).all(1)&(np.abs(points).sum(1)>0)]/1000
    # Keep static scene range; very near camera housing/self returns are excluded.
    points=points[(np.linalg.norm(points,axis=1)>.35)&(np.linalg.norm(points,axis=1)<2.6)]
    result=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(.018)
    result.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.07,max_nn=30))
    return result


def angle_delta(a,b): return (a-b+math.pi)%(2*math.pi)-math.pi


def register(source,target):
    transform=np.eye(4);levels=[(.08,40),(.04,50),(.022,70)]
    for threshold,iterations in levels:
        result=o3d.pipelines.registration.registration_icp(source,target,threshold,transform,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=iterations))
        transform=result.transformation
    return transform,float(result.fitness),float(result.inlier_rmse)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("session",type=Path);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    session=json.loads((args.session/"session_manifest.json").read_text())
    priors=sorted(args.session.glob("table_edge*/operator_alignment_prior.json"))
    if not priors:raise RuntimeError("table-edge prior missing")
    prior=json.loads(priors[-1].read_text());R_level_camera=np.asarray(prior["R_body_camera_prior"])
    # Remove yaw from R_body_camera_prior to recover the LEVEL rotation used by
    # the support plane. R_level_camera = Rz(-yaw) R_body_camera.
    yaw_prior=float(prior["yaw_prior_rad"]);c,s=math.cos(-yaw_prior),math.sin(-yaw_prior)
    Rz=np.array([[c,-s,0],[s,c,0],[0,0,1]]);R_level_camera=Rz@R_level_camera
    origins=sorted((args.session/"captures"/"origin").glob("*/pointcloud.ply"))
    if not origins:raise RuntimeError("origin cloud missing")
    target=cloud(origins[-1]);position=np.zeros(2);records=[]
    capture_events={event["direction"]:event for event in session["events"] if event["event"]=="amr_visually_stopped_and_captured"}
    move_events=[event for event in session["events"] if event["event"]=="amr_translation_sent"]
    for event in move_events:
        direction=event["direction"]
        position+=np.array([event["x_m"],event["y_m"]])
        captured=capture_events.get(direction)
        if captured is None:continue
        source_path=Path(captured["manifest"]).parent/"pointcloud.ply"
        transform,fitness,rmse=register(cloud(source_path),target)
        translation_camera=transform[:3,3];translation_level=R_level_camera@translation_camera
        rotation_drift=math.degrees(math.acos(np.clip((np.trace(transform[:3,:3])-1)/2,-1,1)))
        record={"direction":direction,"expected_body_position_m":position.tolist(),
            "estimated_camera_translation_m":translation_camera.tolist(),
            "estimated_level_translation_m":translation_level.tolist(),
            "estimated_rotation_drift_deg":rotation_drift,"fitness":fitness,"rmse_m":rmse,
            "source_manifest":captured["manifest"]}
        if np.linalg.norm(position)>.03:
            expected_angle=math.atan2(position[1],position[0]);observed_angle=math.atan2(translation_level[1],translation_level[0])
            inferred=angle_delta(expected_angle,observed_angle)
            record["inferred_yaw_rad"]=inferred;record["inferred_yaw_deg"]=math.degrees(inferred)
            record["translation_scale"]=float(np.linalg.norm(translation_level[:2])/np.linalg.norm(position))
        else:
            record["return_translation_error_m"]=float(np.linalg.norm(translation_level[:2]))
        records.append(record)
    inferred=[item["inferred_yaw_rad"] for item in records if "inferred_yaw_rad" in item]
    if len(inferred)<2:raise RuntimeError("both x and y displaced captures are required")
    phasor=sum(np.exp(1j*value) for value in inferred);yaw_sweep=math.atan2(phasor.imag,phasor.real)
    prior_candidates=[yaw_prior,angle_delta(yaw_prior+math.pi,0)]
    selected_prior=min(prior_candidates,key=lambda value:abs(angle_delta(value,yaw_sweep)))
    disagreement=abs(math.degrees(angle_delta(yaw_sweep,selected_prior)))
    returns=[item["return_translation_error_m"] for item in records if "return_translation_error_m" in item]
    passed=(disagreement<=2 and all(item["fitness"]>=.55 and item["rmse_m"]<=.035 and
        item["estimated_rotation_drift_deg"]<=1.5 for item in records) and
        all(.65<=item.get("translation_scale",1)<=1.35 for item in records) and
        bool(returns) and max(returns)<=.03)
    result={"schema_version":1,"state":"SWEEP_VALIDATED" if passed else "SWEEP_INCONCLUSIVE",
        "planning_allowed":False,"execution_allowed":False,"operator_alignment_prior":str(priors[-1]),
        "api_axis_assumption":"AMR relative +x/+y are treated as BODY +X/+Y; physical arrow/response must be operator-observed",
        "yaw_prior_deg_selected_branch":math.degrees(selected_prior),"yaw_sweep_deg":math.degrees(yaw_sweep),
        "yaw_disagreement_deg":disagreement,"acceptance":{"max_yaw_disagreement_deg":2,"passed":passed},
        "pairs":records}
    (args.output/"base_sweep_yaw_validation.json").write_text(json.dumps(result,indent=2)+"\n")
    fig,ax=plt.subplots(figsize=(8,8));ax.axhline(0,color=".8");ax.axvline(0,color=".8")
    for item in records:
        e=np.asarray(item["expected_body_position_m"]);v=np.asarray(item["estimated_level_translation_m"][:2])
        ax.arrow(0,0,e[0],e[1],color="black",width=.001,length_includes_head=True)
        ax.arrow(0,0,v[0],v[1],color="tab:orange",width=.001,length_includes_head=True)
        ax.text(e[0],e[1],item["direction"])
    ax.set_aspect("equal");ax.set(xlabel="horizontal axis 1 (m)",ylabel="horizontal axis 2 (m)",title="Expected BODY translations (black) vs observed LEVEL (orange)")
    fig.tight_layout();fig.savefig(args.output/"base_sweep_vectors.png",dpi=180);plt.close(fig)
    print(json.dumps({"state":result["state"],"yaw_sweep_deg":result["yaw_sweep_deg"],"disagreement_deg":disagreement}))


if __name__=="__main__":main()
