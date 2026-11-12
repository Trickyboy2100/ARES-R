#!/usr/bin/env python3
"""Render raw/overlay/filtered P2 evidence and quantify retained scene geometry."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.body_pointcloud import load_artifact
from ares_r.perception.robot_collision import (load_geometry_snapshot, self_filter_body_cloud,
                                                transform_xyz_rpy)


BOX_MIN = np.array([0.7787265, 0.067291, 0.8428555])
BOX_MAX = np.array([0.8625135, 0.276417, 1.0733705])


def region(points, low, high):
    return np.all((points >= low) & (points <= high), axis=1)


def bounds(points):
    if not len(points):
        return {"count": 0, "min_m": None, "max_m": None, "dims_m": None}
    low, high = points.min(0), points.max(0)
    return {"count": int(len(points)), "min_m": low.tolist(), "max_m": high.tolist(),
            "dims_m": (high-low).tolist()}


def line_box(o3d, box):
    obb = o3d.geometry.OrientedBoundingBox(np.asarray(box.center_body_m),
                                           np.asarray(box.rotation_body),
                                           2.0*np.asarray(box.half_extents_m))
    lines = o3d.geometry.LineSet.create_from_oriented_bounding_box(obb)
    colors = {"left_arm": [0.1, 0.8, 1.0], "right_arm": [1.0, 0.35, 0.05],
              "left_gripper_tool": [0.2, 1.0, 0.2], "right_gripper_tool": [1.0, 0.1, 0.8],
              "chassis": [0.95, 0.85, 0.15], "safety": [1.0, 0.0, 0.0]}
    lines.paint_uniform_color(colors.get(box.owner, [0.8, 0.8, 0.8]))
    return lines


def render(points, colors, snapshot, output, mode, margin=None):
    os.environ.setdefault("EGL_PLATFORM", "surfaceless")
    import open3d as o3d
    started = time.perf_counter()
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points[::3].astype(float)))
    cloud.colors = o3d.utility.Vector3dVector(colors[::3].astype(float))
    renderer = o3d.visualization.rendering.OffscreenRenderer(1600, 1000)
    renderer.scene.set_background([0.035, 0.045, 0.06, 1.0])
    point_mat = o3d.visualization.rendering.MaterialRecord(); point_mat.shader="defaultUnlit"; point_mat.point_size=2.0
    line_mat = o3d.visualization.rendering.MaterialRecord(); line_mat.shader="unlitLine"; line_mat.line_width=3.0
    renderer.scene.add_geometry("BODY_CLOUD", cloud, point_mat)
    axes=o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.3)
    renderer.scene.add_geometry("BODY_AXES", axes, point_mat)
    if mode == "overlay":
        world=json.loads((REPOSITORY/"config/robot_world.json").read_text(encoding="utf-8"))
        for side in ("left","right"):
            arm=world["arms"][side]
            frame=o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.18)
            frame.transform(transform_xyz_rpy(arm["base_xyz_m"],arm["base_rpy_rad"]))
            renderer.scene.add_geometry(side+"_BASE_FRAME",frame,point_mat)
        for index, box in enumerate(snapshot.boxes):
            renderer.scene.add_geometry("box-%03d" % index, line_box(o3d, box), line_mat)
    renderer.scene.camera.look_at([0.65,0.0,1.0],[2.15,-2.25,1.85],[0,0,1])
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    o3d.io.write_image(str(output), renderer.render_to_image(), 9)
    from PIL import Image,ImageDraw
    canvas=Image.open(output).convert("RGB"); draw=ImageDraw.Draw(canvas)
    legend=["P2 %s BODY collision evidence" % mode.upper(),
            "cloud=Pixel Pro/BODY/m | axes RGB = +X/+Y/+Z"]
    if mode=="overlay": legend += ["cyan=left arm orange=right arm", "green=left gripper magenta=right gripper",
                                    "yellow=chassis red=central exclusion",
                                    "geometry="+snapshot.geometry_revision[:30],
                                    "left q="+" ".join("%+.3f"%v for v in snapshot.joints_rad["left"]),
                                    "right q="+" ".join("%+.3f"%v for v in snapshot.joints_rad["right"])]
    if margin is not None: legend.append("self-filter margin=%d mm" % round(margin*1000))
    draw.rectangle((12,12,700,28+18*len(legend)),fill=(0,0,0),outline=(220,220,220))
    for i,line in enumerate(legend): draw.text((24,22+i*18),line,fill=(245,245,245))
    canvas.save(output)
    return time.perf_counter()-started


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("geometry")
    parser.add_argument("--output-dir",required=True)
    args=parser.parse_args(); out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    cloud,meta=load_artifact(Path(args.manifest)); snap=load_geometry_snapshot(Path(args.geometry))
    points=np.asarray(cloud.points_body_m); colors=np.asarray(cloud.colors_rgb)
    box_region=region(points,BOX_MIN,BOX_MAX)
    table_region=(np.abs(points[:,2]-0.75)<=0.012)&(points[:,0]>=0.3)&(points[:,0]<=1.35)&(np.abs(points[:,1])<=0.8)
    report={"schema_version":1,"frame":"BODY","cloud_manifest":str(Path(args.manifest).resolve()),
            "geometry_snapshot":str(Path(args.geometry).resolve()),"raw_points":int(len(points)),
            "raw_box":bounds(points[box_region]),"raw_table_points":int(table_region.sum()),
            "margins":{},"timings_s":{}}
    report["timings_s"]["raw_render"]=render(points,colors,snap,out/"raw_body_cloud.png","raw")
    report["timings_s"]["overlay_render"]=render(points,colors,snap,out/"robot_collision_overlay.png","overlay")
    for margin_mm in (10,20,30):
        margin=margin_mm/1000.0; keep,stats=self_filter_body_cloud(points,snap,margin)
        retained_box=box_region&keep; retained_table=table_region&keep
        raw_dims=np.asarray(report["raw_box"]["dims_m"]); after=bounds(points[retained_box])
        after_dims=np.asarray(after["dims_m"]) if after["dims_m"] is not None else np.full(3,np.nan)
        report["margins"][str(margin_mm)]={"filter":stats,"box_after":after,
            "box_retention_ratio":float(retained_box.sum()/max(1,box_region.sum())),
            "box_dimension_change_mm":((after_dims-raw_dims)*1000).tolist(),
            "table_retained_points":int(retained_table.sum()),
            "table_retention_ratio":float(retained_table.sum()/max(1,table_region.sum()))}
        if margin_mm==20:
            report["timings_s"]["filtered_render"]=render(points[keep],colors[keep],snap,out/"self_filtered_20mm.png","filtered",margin)
    report["total_elapsed_s"]=sum(report["timings_s"].values())+sum(v["filter"]["elapsed_s"] for v in report["margins"].values())
    (out/"self_filter_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__": main()
