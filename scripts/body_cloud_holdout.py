#!/usr/bin/env python3
"""Measure one deliberately placed box from two canonical BODY snapshots.

This is validation evidence only. It neither estimates camera extrinsics nor
implements the robot self-filter/planning obstacle pipeline.
"""

import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.body_pointcloud import load_artifact


def downsample(points, voxel_m):
    import open3d as o3d
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points.astype(float)))
    return cloud.voxel_down_sample(voxel_m)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_manifest")
    parser.add_argument("holdout_manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()
    import open3d as o3d
    baseline, _ = load_artifact(Path(args.baseline_manifest))
    holdout, _ = load_artifact(Path(args.holdout_manifest))
    roi = [[0.60, 1.10], [-0.25, 0.40], [0.80, 1.20]]
    def crop(points):
        return points[(points[:, 0] > roi[0][0]) & (points[:, 0] < roi[0][1]) &
                      (points[:, 1] > roi[1][0]) & (points[:, 1] < roi[1][1]) &
                      (points[:, 2] > roi[2][0]) & (points[:, 2] < roi[2][1])]
    before = downsample(crop(baseline.points_body_m), 0.003)
    after = downsample(crop(holdout.points_body_m), 0.003)
    distances = np.asarray(after.compute_point_cloud_distance(before))
    changed = np.asarray(after.points)[distances > 0.010]
    changed_cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(changed))
    labels = np.asarray(changed_cloud.cluster_dbscan(eps=0.009, min_points=10,
                                                     print_progress=False))
    clusters = [(int(np.sum(labels == label)), label) for label in set(labels) if label >= 0]
    if not clusters:
        raise RuntimeError("no hold-out cluster")
    _, selected = max(clusters)
    box = changed[labels == selected]
    minimum, maximum = box.min(axis=0), box.max(axis=0)
    extent = maximum - minimum; centre = (maximum + minimum) / 2.0
    expected = np.array([0.078, 0.205, 0.224])
    report = {
        "method": "3 mm voxel; current-to-baseline distance >10 mm; DBSCAN eps=9 mm min_points=10; largest cluster",
        "frame": "BODY", "unit": "m", "roi_body_m": roi,
        "baseline_manifest": str(Path(args.baseline_manifest).resolve()),
        "holdout_manifest": str(Path(args.holdout_manifest).resolve()),
        "cluster_points": int(len(box)), "aabb_min_body_m": minimum.tolist(),
        "aabb_max_body_m": maximum.tolist(), "aabb_center_body_m": centre.tolist(),
        "aabb_dimensions_xyz_m": extent.tolist(),
        "manual_dimensions_xyz_m": expected.tolist(),
        "dimension_error_xyz_mm": ((extent - expected) * 1000.0).tolist(),
        "manual_center_x_m": 0.835,
        "center_x_error_mm": float((centre[0] - 0.835) * 1000.0),
        "manual_y_check": "positive / left of BODY centerline",
        "observed_y_m": float(centre[1]),
        "extrinsic_refit": "NONE", "self_filter": "NOT_RUN", "curobo": "NOT_RUN",
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    os.environ.setdefault("EGL_PLATFORM", "surfaceless")
    renderer = o3d.visualization.rendering.OffscreenRenderer(1600, 1000)
    renderer.scene.set_background([0.04, 0.05, 0.07, 1.0])
    raw = downsample(holdout.points_body_m, 0.006)
    raw.paint_uniform_color([0.62, 0.65, 0.70])
    selected_cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(box))
    selected_cloud.paint_uniform_color([1.0, 0.15, 0.05])
    aabb = o3d.geometry.AxisAlignedBoundingBox(minimum, maximum)
    lines = o3d.geometry.LineSet.create_from_axis_aligned_bounding_box(aabb)
    lines.paint_uniform_color([0.1, 1.0, 0.1])
    axes = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.25)
    material = o3d.visualization.rendering.MaterialRecord()
    material.shader = "defaultUnlit"; material.point_size = 3.0
    line_material = o3d.visualization.rendering.MaterialRecord()
    line_material.shader = "unlitLine"; line_material.line_width = 4.0
    renderer.scene.add_geometry("BODY_CLOUD", raw, material)
    renderer.scene.add_geometry("HOLDOUT_CLUSTER", selected_cloud, material)
    renderer.scene.add_geometry("HOLDOUT_AABB", lines, line_material)
    renderer.scene.add_geometry("BODY_AXES", axes, material)
    renderer.scene.camera.look_at([0.82, 0.17, 0.96], [1.65, -1.2, 1.35], [0, 0, 1])
    image = renderer.render_to_image()
    snapshot = Path(args.snapshot); snapshot.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_image(str(snapshot), image, 9)
    from PIL import Image, ImageDraw
    canvas = Image.open(snapshot).convert("RGB"); draw = ImageDraw.Draw(canvas)
    text = ["P1-B known-box hold-out (BODY/m)",
            "red=changed cluster green=AABB X/Y/Z axes=RGB",
            "center=[%.4f, %.4f, %.4f]" % tuple(centre),
            "dims_mm=[%.1f, %.1f, %.1f]" % tuple(extent * 1000.0),
            "manual_mm=[78, 205, 224] X manual=0.835 m"]
    draw.rectangle((12, 12, 620, 120), fill=(0, 0, 0), outline=(220, 220, 220))
    for index, line in enumerate(text):
        draw.text((24, 22 + index * 18), line, fill=(245, 245, 245))
    canvas.save(snapshot)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
