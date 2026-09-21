#!/usr/bin/env python3
"""Render comparable BODY-view P3 planning-only evidence."""

import argparse,json,os
from pathlib import Path
import sys
import numpy as np

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.perception.robot_collision import load_geometry_snapshot


def load(path):return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    p=argparse.ArgumentParser();p.add_argument("scene_dir",type=Path);p.add_argument("geometry")
    p.add_argument("planning");p.add_argument("output");a=p.parse_args();os.environ.setdefault("EGL_PLATFORM","surfaceless")
    import open3d as o3d
    report=load(a.scene_dir/"scene_report.json");target=load(a.scene_dir/"targets.json");plan=load(a.planning)
    points=np.load(a.scene_dir/"clean_residual.npz")["points_body_m"];geometry=load_geometry_snapshot(Path(a.geometry))
    renderer=o3d.visualization.rendering.OffscreenRenderer(1800,1050);renderer.scene.set_background([.035,.045,.06,1])
    pm=o3d.visualization.rendering.MaterialRecord();pm.shader="defaultUnlit";pm.point_size=3
    lm=o3d.visualization.rendering.MaterialRecord();lm.shader="unlitLine";lm.line_width=4
    cloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points));cloud.paint_uniform_color([.72,.76,.82])
    renderer.scene.add_geometry("clean_cloud",cloud,pm)
    active=target["active_arm"]
    for i,box in enumerate(geometry.boxes):
        obb=o3d.geometry.OrientedBoundingBox(np.asarray(box.center_body_m),np.asarray(box.rotation_body),2*np.asarray(box.half_extents_m))
        lines=o3d.geometry.LineSet.create_from_oriented_bounding_box(obb)
        if box.owner.startswith(active):color=[.1,.8,1.] # active cyan
        elif box.owner.startswith("left") or box.owner.startswith("right"):color=[1.,.45,.05] # inactive orange
        elif box.owner=="chassis":color=[.95,.85,.15]
        else:color=[1.,0.,0.]
        lines.paint_uniform_color(color);renderer.scene.add_geometry("robot-%d"%i,lines,lm)
    for i,item in enumerate(report["objects"]):
        c=np.asarray(item["center_m"]);d=np.asarray(item["dims_m"])+2*float(item["inflation_m"])
        lines=o3d.geometry.LineSet.create_from_axis_aligned_bounding_box(o3d.geometry.AxisAlignedBoundingBox(c-d/2,c+d/2))
        source=item.get("source","")
        if "PROTRUDING_OBSTACLE" in source:world_color=[1.,.12,.12]
        elif "SUPPORT_SURFACE" in source:world_color=[.25,1.,.3]
        elif "STRUCTURE" in source:world_color=[.15,.55,1.]
        elif "UNKNOWN_OCCUPIED" in source or item["id"].startswith("residual"):world_color=[.7,.15,1.]
        else:world_color=[.25,1.,.3]
        lines.paint_uniform_color(world_color)
        renderer.scene.add_geometry("world-%d"%i,lines,lm)
    for label,color in (("A",[.1,1.,.1]),("B",[.15,.45,1.])):
        sphere=o3d.geometry.TriangleMesh.create_sphere(radius=.025);sphere.translate(target[label]["xyz_m"]);sphere.paint_uniform_color(color)
        renderer.scene.add_geometry("target-"+label,sphere,pm)
    path=np.asarray(plan.get("tcp_path_body_m",[]),dtype=float)
    if len(path)>1:
        lines=o3d.geometry.LineSet();lines.points=o3d.utility.Vector3dVector(path)
        lines.lines=o3d.utility.Vector2iVector(np.column_stack((np.arange(len(path)-1),np.arange(1,len(path)))))
        lines.colors=o3d.utility.Vector3dVector(np.tile([[1.,.05,.05]],(len(path)-1,1)))
        renderer.scene.add_geometry("planned_tcp",lines,lm)
    axes=o3d.geometry.TriangleMesh.create_coordinate_frame(size=.25);renderer.scene.add_geometry("BODY",axes,pm)
    renderer.scene.camera.look_at([.70,-.15,1.0],[2.0,-2.25,1.75],[0,0,1])
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);o3d.io.write_image(str(output),renderer.render_to_image(),9)
    from PIL import Image,ImageDraw
    canvas=Image.open(output).convert("RGB");draw=ImageDraw.Draw(canvas)
    lines=["P3.1 %s planning-only | execution BLOCKED"%report["mode"],
        "cyan=active robot orange=inactive robot red=TCP path",
        "red=protrusion blue=structure purple=unknown green=support/fixed",
        "snapshot="+report["snapshot_id"],"calibration="+report["calibration_revision"][:36],
        "geometry="+report["geometry_revision"][:36],
        "pipeline=%s primitives=%d"%(report.get("obstacle_pipeline","single_aabb"),len(report["objects"])),
        "robot-owned-filter="+str(report.get("self_filter",{}).get("revision","P2 baseline"))[:32],
        "result=%s min-clearance=%s m"%(plan["observed_result"],plan["clearance_m"]["planned_path"])]
    draw.rectangle((12,12,850,28+18*len(lines)),fill=(0,0,0),outline=(220,220,220))
    for i,line in enumerate(lines):draw.text((24,22+18*i),line,fill=(245,245,245))
    canvas.save(output);print(output)


if __name__=="__main__":main()
