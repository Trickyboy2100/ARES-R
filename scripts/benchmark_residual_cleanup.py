#!/usr/bin/env python3
"""Compare conservative sparse-outlier filters on a canonical BODY cloud."""

import argparse,json,os
from pathlib import Path
import sys,time
import numpy as np

REPOSITORY=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPOSITORY/"src"))
from ares_r.perception.body_pointcloud import load_artifact
from ares_r.perception.residual_cloud import PROFILES,DEFAULT_PROFILE,clean_and_cluster
from ares_r.perception.robot_collision import load_geometry_snapshot,self_filter_body_cloud

ROI=[[0.22,-0.76,0.70],[1.30,0.76,1.40]]
BOX_BOUNDS=[[0.7787265,0.067291,0.8428555],[0.8625135,0.276417,1.0733705]]


def render(points,boxes,output,title):
    os.environ.setdefault("EGL_PLATFORM","surfaceless")
    import open3d as o3d
    renderer=o3d.visualization.rendering.OffscreenRenderer(1600,1000)
    renderer.scene.set_background([.035,.045,.06,1])
    cloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    cloud.paint_uniform_color([.72,.76,.82])
    pm=o3d.visualization.rendering.MaterialRecord();pm.shader="defaultUnlit";pm.point_size=3
    lm=o3d.visualization.rendering.MaterialRecord();lm.shader="unlitLine";lm.line_width=3
    renderer.scene.add_geometry("clean",cloud,pm)
    for i,box in enumerate(boxes):
        low=np.asarray(box["min_m"]);high=np.asarray(box["max_m"])
        lines=o3d.geometry.LineSet.create_from_axis_aligned_bounding_box(
            o3d.geometry.AxisAlignedBoundingBox(low,high));lines.paint_uniform_color([1,.35,.05])
        renderer.scene.add_geometry("box-%d"%i,lines,lm)
    axes=o3d.geometry.TriangleMesh.create_coordinate_frame(size=.25)
    renderer.scene.add_geometry("BODY",axes,pm)
    renderer.scene.camera.look_at([.78,0,1.0],[2.0,-2.2,1.7],[0,0,1])
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    o3d.io.write_image(str(output),renderer.render_to_image(),9)
    from PIL import Image,ImageDraw
    canvas=Image.open(output).convert("RGB");draw=ImageDraw.Draw(canvas)
    lines=[title,"BODY/m | orange=residual cluster AABB","clusters=%d clean voxels=%d"%(len(boxes),len(points))]
    draw.rectangle((12,12,700,28+18*len(lines)),fill=(0,0,0),outline=(220,220,220))
    for i,line in enumerate(lines):draw.text((24,22+18*i),line,fill=(245,245,245))
    canvas.save(output)


def main():
    p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("geometry")
    p.add_argument("--output-dir",required=True);a=p.parse_args();out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    cloud,meta=load_artifact(Path(a.manifest));snap=load_geometry_snapshot(Path(a.geometry))
    sf_started=time.perf_counter();keep,sf=self_filter_body_cloud(cloud.points_body_m,snap,.020)
    sf_elapsed=time.perf_counter()-sf_started;points=np.asarray(cloud.points_body_m)[keep]
    report={"schema_version":1,"manifest":str(Path(a.manifest).resolve()),
            "calibration_revision":cloud.transform_revision,"geometry_revision":snap.geometry_revision,
            "self_filter":sf,"self_filter_wall_s":sf_elapsed,"roi_body_m":ROI,"profiles":{}}
    selected=None
    for profile in PROFILES:
        clean,boxes,metrics=clean_and_cluster(points,ROI,profile,box_bounds=BOX_BOUNDS)
        report["profiles"][profile.name]=metrics
        if profile.name==DEFAULT_PROFILE:
            selected=(clean,boxes,metrics)
    clean,boxes,metrics=selected
    np.savez_compressed(out/"clean_residual_default.npz",points_body_m=clean)
    (out/"residual_aabbs_default.json").write_text(json.dumps(boxes,indent=2)+"\n")
    report["selected_default"]=DEFAULT_PROFILE
    (out/"cleanup_benchmark.json").write_text(json.dumps(report,indent=2)+"\n")
    render(clean,boxes,out/"clean_residual_default.png","P3 conservative residual cleanup: "+DEFAULT_PROFILE)
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
