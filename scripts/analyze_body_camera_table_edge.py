#!/usr/bin/env python3
"""Derive table roll/pitch/z and an operator-aligned yaw prior.

The result remains UNCOMMISSIONED.  Translation x/y is deliberately absent.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d
from scipy.spatial import ConvexHull

from ares_r.perception.body_registration import level_transform, plane_metrics


def load_cloud(path):
    cloud = o3d.io.read_point_cloud(str(path))
    points = np.asarray(cloud.points, dtype=float)
    return points[np.isfinite(points).all(1) & (np.abs(points).sum(1)>0)]/1000.0


def rz(angle):
    value=np.eye(4);c,s=math.cos(angle),math.sin(angle)
    value[:3,:3]=[[c,-s,0],[s,c,0],[0,0,1]]
    return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("capture",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--table-height",type=float,default=.75)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=args.capture/"pointcloud.ply";manifest=json.loads((args.capture/"manifest.json").read_text())
    points=load_cloud(source)
    voxel=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(.008)
    model,inliers=voxel.segment_plane(distance_threshold=.009,ransac_n=3,num_iterations=2500)
    plane_points=np.asarray(voxel.points)[inliers]
    metric=plane_metrics(plane_points,model[:3],model[3])
    normal=np.asarray(metric["normal_camera"],dtype=float);d=float(metric["plane_d_m"])
    # Orient the normal towards the camera-origin side, matching prior support evidence.
    if d>0: normal=-normal;d=-d
    level=level_transform(normal,d)
    level_plane=(np.c_[plane_points,np.ones(len(plane_points))]@level.T)[:,:3]
    xy=level_plane[:,:2]
    # Whole-plane PCA is biased by robot/scale occlusions.  The table's long
    # front/back edges survive as the longest convex-hull segment; the current
    # image provides the independent semantic check that it is the table edge.
    hull=ConvexHull(xy);segments=[]
    for first,second in zip(hull.vertices,np.roll(hull.vertices,-1)):
        vector=xy[second]-xy[first]
        length=float(np.linalg.norm(vector));angle=math.atan2(vector[1],vector[0])%math.pi
        segments.append((length,first,second,vector,angle))
    # A rectangle contributes two parallel edge families. Score orientation
    # support across all hull segments (modulo pi), rather than picking one
    # side segment or letting occlusions bias whole-plane PCA.
    tolerance=math.radians(15)
    candidates=[]
    for seed in segments:
        members=[item for item in segments if abs((item[4]-seed[4]+math.pi/2)%math.pi-math.pi/2)<=tolerance]
        score=sum(item[0] for item in members)
        phasor=sum(item[0]*np.exp(2j*item[4]) for item in members)
        mean_angle=(math.atan2(phasor.imag,phasor.real)/2)%math.pi
        candidates.append((score,mean_angle,members))
    orientation_support,edge_angle,candidate_segments=max(candidates,key=lambda item:item[0])
    camera_level_xy=level[:2,3]
    # Of the two parallel table boundaries, the one nearest the camera origin
    # is the visible front edge.
    edge_length,edge_first,edge_second,_,_=min(candidate_segments,
        key=lambda item:np.linalg.norm((xy[item[1]]+xy[item[2]])/2-camera_level_xy))
    edge=np.array([math.cos(edge_angle),math.sin(edge_angle)])
    # Hull direction is sign-ambiguous. Choose positive LEVEL X and preserve
    # the remaining 180-degree BODY sign ambiguity explicitly.
    if edge[0]<0: edge=-edge
    edge_angle=math.atan2(edge[1],edge[0]);yaw=math.pi/2-edge_angle
    rotation=rz(yaw)@level
    # With BODY table height known, plane-to-camera distance fixes camera z.
    camera_z=args.table_height+abs(d)
    result={
        "schema_version":1,"state":"OPERATOR_ALIGNED_UNCOMMISSIONED",
        "planning_allowed":False,"execution_allowed":False,
        "source":"OPERATOR_ALIGNMENT_PRIOR + current support plane + dominant convex-hull edge family",
        "frame_id":manifest["frame_id"],"pointcloud_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "table_height_body_m":args.table_height,"support_plane":metric,
        "camera_height_body_m":camera_z,
        "table_edge_direction_level":[float(edge[0]),float(edge[1]),0.0],
        "candidate_body_y_level":[float(edge[0]),float(edge[1]),0.0],
        "candidate_body_x_level":[float(edge[1]),float(-edge[0]),0.0],
        "yaw_prior_rad":yaw,"yaw_prior_deg":math.degrees(yaw),
        "R_body_camera_prior":[row[:3].tolist() for row in rotation[:3]],
        "ambiguity":"table edge has a 180 degree sign ambiguity; BODY +X sign requires visual/operator confirmation and base sweep",
        "edge_method":"dominant parallel support-plane convex-hull family; nearest parallel boundary selected as front; source grayscale visually reviewed",
        "confidence":{"support_inliers":len(plane_points),"hull_vertex_count":len(hull.vertices),
                      "selected_edge_length_m":edge_length,
                      "orientation_support_length_m":orientation_support,
                      "parallel_segment_count":len(candidate_segments),
                      "camera_origin_level_xy_m":camera_level_xy.tolist()},
    }
    (args.output/"operator_alignment_prior.json").write_text(json.dumps(result,indent=2)+"\n")
    fig,ax=plt.subplots(figsize=(11,8));sample=xy[::max(1,len(xy)//80000)]
    ax.scatter(sample[:,0],sample[:,1],s=.3,alpha=.3,color="0.4")
    hull_xy=xy[np.r_[hull.vertices,hull.vertices[0]]];ax.plot(hull_xy[:,0],hull_xy[:,1],color="tab:blue",lw=1,label="support-plane hull")
    endpoints=xy[[edge_first,edge_second]];ax.plot(endpoints[:,0],endpoints[:,1],color="green",lw=6,label="selected longest table edge")
    center=endpoints.mean(0);ax.quiver(*center,*edge,color="green",scale=.8,width=.007,label="candidate BODY +Y")
    normal2=np.array([edge[1],-edge[0]]);ax.quiver(*center,*normal2,color="red",scale=.8,width=.007,label="candidate BODY +X")
    ax.set_aspect("equal");ax.set(xlabel="LEVEL X (m)",ylabel="LEVEL Y (m)",title="OPERATOR_ALIGNMENT_PRIOR — table-plane dominant edge")
    ax.legend();fig.tight_layout();fig.savefig(args.output/"table_edge_yaw_prior.png",dpi=180);plt.close(fig)
    # Save a camera RGB view beside the geometric evidence for human review.
    image=args.capture/"image8bit.png"
    if image.exists():
        (args.output/"source_image8bit.png").write_bytes(image.read_bytes())
    print(json.dumps({"output":str(args.output),"yaw_prior_deg":math.degrees(yaw),"camera_z_m":camera_z,
                      "support_inliers":len(plane_points)}))


if __name__=="__main__":main()
