#!/usr/bin/env python3
"""Offline pointcloud pipeline; BODY stages are impossible without traced T_body_camera."""

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


def record(records, name, before, points, started, parameters, source_frame, output_frame):
    records.append({
        "stage": name, "point_count_before": int(before), "point_count_after": int(len(points)),
        "bounds_min_m": points.min(axis=0).tolist() if len(points) else None,
        "bounds_max_m": points.max(axis=0).tolist() if len(points) else None,
        "runtime_s": time.perf_counter() - started, "parameters": parameters,
        "source_frame": source_frame, "output_frame": output_frame,
    })


def load_transform(path):
    if not path:
        return None, "UNAVAILABLE"
    raw = json.loads(Path(path).read_text())
    matrix = np.asarray(raw["T_body_camera"], dtype=float).reshape(4, 4)
    if raw.get("state") != "COMMISSIONED":
        return None, "UNCOMMISSIONED"
    return matrix, str(raw["revision"])


def plot(points, boxes, path, title):
    sample = points[::max(1, len(points) // 80000)]
    figure = plt.figure(figsize=(12, 9))
    axis = figure.add_subplot(111, projection="3d")
    if len(sample): axis.scatter(sample[:, 0], sample[:, 1], sample[:, 2], s=.25, alpha=.45)
    for box in boxes:
        low, high = np.asarray(box["min_m"]), np.asarray(box["max_m"])
        for x in (low[0], high[0]):
            for y in (low[1], high[1]): axis.plot([x, x], [y, y], [low[2], high[2]], "r-", lw=.7)
        for z in (low[2], high[2]):
            axis.plot([low[0], high[0], high[0], low[0], low[0]],
                      [low[1], low[1], high[1], high[1], low[1]], [z] * 5, "r-", lw=.7)
    axis.set(xlabel="X m", ylabel="Y m", zlabel="Z m", title=title)
    figure.tight_layout(); figure.savefig(path, dpi=170); plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    parser.add_argument("--output", required=True)
    parser.add_argument("--calibration")
    parser.add_argument("--voxel", type=float, default=.01)
    parser.add_argument("--roi", nargs=6, type=float, default=[-.62, .90, -1.10, .99, .43, 1.97])
    parser.add_argument("--self-spheres", help="JSON BODY spheres from actual planner model/live joints")
    parser.add_argument("--inflation", type=float, default=.02)
    args = parser.parse_args()
    capture, output = Path(args.capture), Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    source = capture / "pointcloud.ply"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    cloud = o3d.io.read_point_cloud(str(source))
    points = np.asarray(cloud.points, dtype=float)
    records = []
    started = time.perf_counter(); before = len(points)
    valid = np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)
    points = points[valid] / 1000.0
    record(records, "invalid_zero_remove_mm_to_m", before, points, started,
           {"source_unit": "mm", "scale": .001}, "camera", "camera")
    plot(points, [], output / "01_raw_valid_camera.png", "Raw valid cloud — CAMERA frame")

    transform, calibration_revision = load_transform(args.calibration)
    blocked = transform is None
    frame = "camera"
    if not blocked:
        started = time.perf_counter(); before = len(points)
        points = (np.c_[points, np.ones(len(points))] @ transform.T)[:, :3]
        frame = "body"
        record(records, "camera_to_body", before, points, started,
               {"calibration_revision": calibration_revision}, "camera", "body")
        plot(points, [], output / "02_body_transformed.png", "BODY transformed cloud")
        started = time.perf_counter(); before = len(points)
        xmin, xmax, ymin, ymax, zmin, zmax = args.roi
        mask = ((points[:, 0] >= xmin) & (points[:, 0] <= xmax) &
                (points[:, 1] >= ymin) & (points[:, 1] <= ymax) &
                (points[:, 2] >= zmin) & (points[:, 2] <= zmax))
        points = points[mask]
        record(records, "body_roi", before, points, started, {"bounds_m": args.roi}, "body", "body")
        plot(points, [], output / "03_body_roi.png", "BODY manipulation ROI")
        if not args.self_spheres:
            blocked = True
            records.append({"stage": "self_filter", "status": "BLOCKED_MISSING_REAL_COLLISION_SPHERES"})
        else:
            started = time.perf_counter(); before = len(points)
            spheres = json.loads(Path(args.self_spheres).read_text())["spheres"]
            keep = np.ones(len(points), dtype=bool)
            for sphere in spheres:
                center = np.asarray(sphere["center_body_m"], dtype=float)
                radius = float(sphere["radius_m"])
                keep &= np.linalg.norm(points - center, axis=1) > radius
            points = points[keep]
            record(records, "robot_self_filter", before, points, started,
                   {"sphere_count": len(spheres)}, "body", "body")
            plot(points, [], output / "04_self_filtered.png", "BODY ROI after robot self-filter")
    else:
        records.append({"stage": "camera_to_body", "status": "BODY_TRANSFORM_BLOCKED",
                        "reason": "no commissioned, traceable T_body_camera"})
        records.append({"stage": "body_roi", "status": "BLOCKED_BY_BODY_TRANSFORM"})
        records.append({"stage": "self_filter", "status": "BLOCKED_BY_BODY_TRANSFORM"})

    started = time.perf_counter(); before = len(points)
    voxel_cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    voxel_cloud = voxel_cloud.voxel_down_sample(args.voxel)
    points = np.asarray(voxel_cloud.points)
    record(records, "voxel", before, points, started, {"voxel_m": args.voxel}, frame, frame)
    labels = np.asarray(voxel_cloud.cluster_dbscan(eps=max(.025, args.voxel * 2.5),
                                                   min_points=8, print_progress=False))
    boxes = []
    for label in sorted(set(labels.tolist()) - {-1}):
        cluster = points[labels == label]
        low, high = cluster.min(axis=0) - args.inflation, cluster.max(axis=0) + args.inflation
        boxes.append({"id": "cluster_%03d" % label, "count": int(len(cluster)),
                      "min_m": low.tolist(), "max_m": high.tolist(),
                      "center_m": ((low + high) / 2).tolist(), "dims_m": (high - low).tolist(),
                      "inflation_m": args.inflation, "frame": frame})
    plot(points, boxes, output / "05_voxel_clusters_aabb.png",
         "Voxel + conservative AABB — %s frame" % frame.upper())
    result = {"schema_version": 1, "source_ply": str(source), "source_sha256": source_hash,
              "calibration_revision": calibration_revision, "output_frame": frame,
              "body_transform_blocked": transform is None, "planning_ready": False,
              "records": records, "aabbs": boxes,
              "warning": "Algorithm evidence only; never load directly into cuRobo. Commit through ObservationEpoch/SceneSnapshot."}
    (output / "pipeline.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "frame": frame, "points": len(points),
                      "aabbs": len(boxes), "body_transform_blocked": transform is None}))


if __name__ == "__main__":
    main()
