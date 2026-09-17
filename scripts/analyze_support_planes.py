#!/usr/bin/env python3
"""Replayable multi-frame support-plane and LEVEL-frame analysis.

No hardware imports and no motion path.  The output is evidence, never a
commissioned CAMERA-to-BODY calibration.
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

from ares_r.perception.body_registration import (
    choose_support_tracks, level_transform, plane_metrics,
)


def load_cloud(path: Path):
    cloud = o3d.io.read_point_cloud(str(path))
    points = np.asarray(cloud.points, dtype=float)
    valid = np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)
    return points[valid] / 1000.0


def extract_planes(points, voxel_m, plane_count, threshold_m, iterations):
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    cloud = cloud.voxel_down_sample(voxel_m)
    total = len(cloud.points)
    remainder = cloud
    planes = []
    for index in range(plane_count):
        if len(remainder.points) < 100:
            break
        model, inliers = remainder.segment_plane(
            distance_threshold=threshold_m, ransac_n=3, num_iterations=iterations)
        values = np.asarray(remainder.points)[inliers]
        metric = dict(plane_metrics(values, model[:3], model[3]))
        metric.update({
            "plane_id": "plane_%02d" % index,
            "inlier_ratio_of_voxel_cloud": len(values) / total,
            "ransac_threshold_m": threshold_m,
        })
        planes.append(metric)
        remainder = remainder.select_by_index(inliers, invert=True)
    return np.asarray(cloud.points), planes


def plot_planes(points, planes, path, title):
    sample = points[::max(1, len(points) // 60000)]
    figure = plt.figure(figsize=(14, 10))
    axis = figure.add_subplot(111, projection="3d")
    axis.scatter(sample[:, 0], sample[:, 1], sample[:, 2], c="0.75", s=.3, alpha=.25)
    colors = plt.cm.tab10(np.linspace(0, 1, max(1, len(planes))))
    for color, plane in zip(colors, planes):
        center = np.asarray(plane["centroid_camera_m"])
        axis.scatter(*center, color=color, s=45, label="%s n=%d" % (plane["plane_id"], plane["inlier_count"]))
        normal = np.asarray(plane["normal_camera"])
        axis.quiver(*center, *normal, length=.18, color=color)
    axis.set(xlabel="CAMERA X (m)", ylabel="CAMERA Y (m)", zlabel="CAMERA Z (m)", title=title)
    axis.legend(fontsize=8)
    figure.tight_layout(); figure.savefig(path, dpi=170); plt.close(figure)


def plot_level(points, transform, path, title):
    sample = points[::max(1, len(points) // 80000)]
    level = (np.c_[sample, np.ones(len(sample))] @ transform.T)[:, :3]
    figure = plt.figure(figsize=(14, 10))
    axis = figure.add_subplot(111, projection="3d")
    axis.scatter(level[:, 0], level[:, 1], level[:, 2], s=.3, alpha=.35)
    axis.quiver(0, 0, 0, .25, 0, 0, color="r", label="LEVEL X (yaw arbitrary)")
    axis.quiver(0, 0, 0, 0, .25, 0, color="g", label="LEVEL Y (yaw arbitrary)")
    axis.quiver(0, 0, 0, 0, 0, .25, color="b", label="LEVEL +Z")
    axis.set(xlabel="LEVEL X (m)", ylabel="LEVEL Y (m)", zlabel="height above support (m)", title=title)
    axis.legend()
    figure.tight_layout(); figure.savefig(path, dpi=170); plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("captures", nargs="+", help="capture directories containing pointcloud.ply")
    parser.add_argument("--output", required=True)
    parser.add_argument("--voxel", type=float, default=.01)
    parser.add_argument("--planes", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=.012)
    parser.add_argument("--iterations", type=int, default=1500)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    frames, clouds = [], []
    for index, item in enumerate(args.captures):
        capture = Path(item)
        source = capture / "pointcloud.ply"
        manifest = json.loads((capture / "manifest.json").read_text())
        points = load_cloud(source)
        voxel, planes = extract_planes(points, args.voxel, args.planes, args.threshold, args.iterations)
        for plane in planes:
            plane["plane_id"] = "frame_%02d_%s" % (index + 1, plane["plane_id"])
        frame = {
            "capture": str(capture), "frame_id": manifest["frame_id"],
            "pointcloud_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "valid_point_count": len(points), "voxel_point_count": len(voxel), "planes": planes,
        }
        frames.append(frame); clouds.append(points)
        plot_planes(voxel, planes, output / ("02_camera_planes_frame_%02d.png" % (index + 1)),
                    "%s — iterative RANSAC planes" % manifest["frame_id"])
    tracks = choose_support_tracks([frame["planes"] for frame in frames])
    if not tracks or tracks[0]["frame_coverage"] != len(frames):
        raise RuntimeError("no support plane repeated in every frame")
    support = tracks[0]
    normal, plane_d = support["mean_normal_camera"], support["mean_plane_d_m"]
    level = level_transform(normal, plane_d)
    optical_angle = math.degrees(math.acos(abs(float(np.asarray(normal)[2]))))
    for index, points in enumerate(clouds):
        plot_level(points, level, output / ("03_level_frame_support_plane_%02d.png" % (index + 1)),
                   "LEVEL_ONLY_NOT_BODY — frame %d" % (index + 1))
    result = {
        "schema_version": 1,
        "state": "LEVEL_ONLY_NOT_BODY",
        "parameters": {"voxel_m": args.voxel, "plane_count": args.planes,
                       "ransac_threshold_m": args.threshold, "iterations": args.iterations},
        "frames": frames,
        "plane_tracks_ranked": tracks,
        "selected_support_track_id": support["track_id"],
        "selection_evidence": "highest repeatability+extent+inlier+normal-stability score; not largest-plane assumption",
        "T_level_camera_candidate": level.tolist(),
        "level_observability": {"roll_pitch": "OBSERVED_FROM_SUPPORT_NORMAL",
                                "vertical_origin": "SUPPORT_PLANE_Z_ZERO",
                                "yaw": "UNOBSERVED_FROM_SINGLE_HORIZONTAL_PLANE",
                                "x_translation": "UNOBSERVED_FROM_SINGLE_HORIZONTAL_PLANE",
                                "y_translation": "UNOBSERVED_FROM_SINGLE_HORIZONTAL_PLANE"},
        "camera_optical_axis_to_support_normal_deg": optical_angle,
        "camera_optical_axis_elevation_from_support_deg": 90.0 - optical_angle,
        "planning_allowed": False,
    }
    (output / "support_plane_candidates.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "support": support["track_id"],
                      "normal": normal, "d_m": plane_d,
                      "normal_max_deviation_deg": support["normal_max_deviation_deg"],
                      "offset_std_m": support["offset_std_m"]}))


if __name__ == "__main__":
    main()
