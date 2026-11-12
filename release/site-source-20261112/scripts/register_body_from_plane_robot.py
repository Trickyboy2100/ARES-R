#!/usr/bin/env python3
"""Estimate an UNCOMMISSIONED CAMERA->BODY candidate from plane + robot model.

This is a replay-only optimizer.  It consumes saved PLY and saved read-only
joint/model geometry; it cannot import a robot SDK or execute a trajectory.
"""

import argparse
import json
import math
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d
from scipy.optimize import differential_evolution, minimize
from scipy.spatial import cKDTree

from ares_r.perception.body_registration import canonical_transform_revision


def rz(angle):
    c, s = math.cos(angle), math.sin(angle)
    result = np.eye(4)
    result[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return result


def candidate_matrix(parameters, level):
    yaw, x, y, table_height = map(float, parameters)
    translation = np.eye(4); translation[:3, 3] = [x, y, table_height]
    return translation @ rz(yaw) @ level


def load_points(path, voxel=.012):
    cloud = o3d.io.read_point_cloud(str(path))
    points = np.asarray(cloud.points, dtype=float)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)] / 1000.0
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(voxel)
    return np.asarray(cloud.points)


def load_organized_roi(path, roi, voxel=.008):
    """Load a documented pixel ROI from the organized 1920x1200 binary PLY."""
    blob = Path(path).read_bytes()
    marker = b"end_header\n"; end = blob.find(marker) + len(marker)
    header = blob[:end].decode("ascii")
    count = int(re.search(r"element vertex (\d+)", header).group(1))
    if "format binary_little_endian" not in header or count != 1920 * 1200:
        raise RuntimeError("organized Pixel Pro binary PLY required for robot pixel mask")
    record = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                       ("r", "u1"), ("g", "u1"), ("b", "u1")])
    values = np.frombuffer(blob, dtype=record, count=count, offset=end).reshape(1200, 1920)
    xmin, xmax, ymin, ymax = roi
    selected = values[ymin:ymax, xmin:xmax]
    points = np.column_stack([selected["x"].ravel(), selected["y"].ravel(), selected["z"].ravel()]).astype(float)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)] / 1000.0
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(voxel)
    return np.asarray(cloud.points)


def angle_delta(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def score(parameters, level, model_body, tree_camera):
    transform = candidate_matrix(parameters, level)
    body_camera = np.linalg.inv(transform)
    model_camera = (np.c_[model_body, np.ones(len(model_body))] @ body_camera.T)[:, :3]
    distances = tree_camera.query(model_camera, k=1, workers=-1)[0]
    clipped = np.minimum(distances, .12)
    trimmed = np.sort(clipped)[:max(10, int(.7 * len(clipped)))]
    robust = float(np.sqrt(np.mean(trimmed * trimmed)))
    inlier = float(np.mean(distances < .035))
    # Weak documented sanity priors: static camera is near the body centreline;
    # table height remains broad and is not asserted as measured truth.
    prior = .0025 * (parameters[2] / .35) ** 2
    return robust + .025 * (1.0 - inlier) + prior


def metrics(parameters, level, model_body, tree_camera):
    transform = candidate_matrix(parameters, level)
    body_camera = np.linalg.inv(transform)
    model_camera = (np.c_[model_body, np.ones(len(model_body))] @ body_camera.T)[:, :3]
    distances = tree_camera.query(model_camera, k=1, workers=-1)[0]
    return {
        "parameters": {"yaw_rad": float(parameters[0]), "yaw_deg": math.degrees(parameters[0]),
                       "camera_body_xyz_m": transform[:3, 3].tolist(),
                       "support_height_body_m": float(parameters[3])},
        "T_body_camera": transform.tolist(),
        "robot_surface_rmse_m": float(np.sqrt(np.mean(np.minimum(distances, .12) ** 2))),
        "robot_surface_median_m": float(np.median(distances)),
        "robot_surface_p90_m": float(np.quantile(distances, .9)),
        "robot_surface_inlier_ratio_20mm": float(np.mean(distances < .02)),
        "robot_surface_inlier_ratio_35mm": float(np.mean(distances < .035)),
        "objective": score(parameters, level, model_body, tree_camera),
    }


def plot_overlay(cloud_camera, transform, model_body, spheres, path, title):
    body = (np.c_[cloud_camera, np.ones(len(cloud_camera))] @ transform.T)[:, :3]
    sample = body[::max(1, len(body) // 60000)]
    figure = plt.figure(figsize=(14, 10)); axis = figure.add_subplot(111, projection="3d")
    axis.scatter(sample[:, 0], sample[:, 1], sample[:, 2], s=.35, alpha=.22, color="0.45", label="cloud")
    axis.scatter(model_body[:, 0], model_body[:, 1], model_body[:, 2], s=1.2, alpha=.75,
                 color="tab:orange", label="cuRobo right-arm sphere surfaces")
    axis.quiver(0, 0, 0, .25, 0, 0, color="r"); axis.quiver(0, 0, 0, 0, .25, 0, color="g"); axis.quiver(0, 0, 0, 0, 0, .25, color="b")
    # Central slab and right base.
    xx, zz = np.meshgrid(np.linspace(-.4, .8, 2), np.linspace(.4, 2.0, 2))
    for y in (-.07, .07): axis.plot_surface(xx, np.full_like(xx, y), zz, alpha=.12, color="red")
    axis.scatter([0], [-.2], [1.2], s=70, marker="^", color="purple", label="right base")
    axis.set(xlabel="BODY +X forward (m)", ylabel="BODY +Y left (m)", zlabel="BODY +Z up (m)", title=title)
    axis.legend(fontsize=8); figure.tight_layout(); figure.savefig(path, dpi=170); plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--support", required=True)
    parser.add_argument("--robot-geometry", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--robot-pixel-roi", nargs=4, type=int,
                        metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
                        help="audited organized-image ROI containing the visible right arm")
    parser.add_argument("captures", nargs="+")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False)
    support = json.loads(Path(args.support).read_text())
    geometry = json.loads(Path(args.robot_geometry).read_text())
    level = np.asarray(support["T_level_camera_candidate"], dtype=float)
    model_body = np.asarray(geometry["surface_points_body_m"], dtype=float)
    spheres = geometry["spheres"]
    clouds, trees = [], []
    normal = np.asarray(support["plane_tracks_ranked"][0]["mean_normal_camera"])
    d = float(support["plane_tracks_ranked"][0]["mean_plane_d_m"])
    for capture in args.captures:
        source = Path(capture) / "pointcloud.ply"
        points = load_points(source)
        registration_points = load_organized_roi(source, args.robot_pixel_roi) if args.robot_pixel_roi else points
        signed = registration_points @ normal + d
        # Remove the table itself and points below it; retain objects toward the camera.
        residual = registration_points[signed < -.025]
        if len(residual) < 100:
            raise RuntimeError("robot registration mask contains too few non-table points")
        clouds.append(points); trees.append(cKDTree(residual))

    seeds = [7, 17, 29, 43]
    solutions = []
    bounds = [(-math.pi, math.pi), (-.65, .65), (-.45, .45), (.55, 1.15)]
    # First frame drives global multi-start; every other frame independently refines.
    for seed in seeds:
        result = differential_evolution(lambda p: score(p, level, model_body, trees[0]), bounds,
                                        seed=seed, popsize=12, maxiter=70, polish=True, workers=1)
        solutions.append(metrics(result.x, level, model_body, trees[0]))
    solutions.sort(key=lambda item: item["objective"])
    best_parameters = np.array([solutions[0]["parameters"]["yaw_rad"],
                                solutions[0]["parameters"]["camera_body_xyz_m"][0],
                                solutions[0]["parameters"]["camera_body_xyz_m"][1],
                                solutions[0]["parameters"]["support_height_body_m"]])
    frame_metrics = []
    for index, tree in enumerate(trees):
        starts = [best_parameters.copy(), best_parameters + np.array([.25, .08, -.08, .04]),
                  best_parameters + np.array([-.25, -.08, .08, -.04])]
        local = []
        for start in starts:
            result = minimize(lambda p: score(p, level, model_body, tree), start,
                              method="Nelder-Mead", options={"maxiter": 700, "xatol": 1e-5, "fatol": 1e-6})
            local.append(metrics(result.x, level, model_body, tree))
        local.sort(key=lambda item: item["objective"])
        frame_metrics.append({"frame_index": index + 1, **local[0]})

    top = solutions[:min(4, len(solutions))]
    yaw_spread = max(angle_delta(item["parameters"]["yaw_rad"], top[0]["parameters"]["yaw_rad"]) for item in top)
    xyz = np.asarray([item["parameters"]["camera_body_xyz_m"] for item in top])
    multi_start_spread = float(np.max(np.linalg.norm(xyz - xyz[0], axis=1)))
    frame_yaw_spread = max(angle_delta(item["parameters"]["yaw_rad"], frame_metrics[0]["parameters"]["yaw_rad"]) for item in frame_metrics)
    frame_xyz = np.asarray([item["parameters"]["camera_body_xyz_m"] for item in frame_metrics])
    frame_translation_spread = float(np.max(np.linalg.norm(frame_xyz - frame_xyz[0], axis=1)))
    unique = (math.degrees(yaw_spread) < 3.0 and multi_start_spread < .04 and
              math.degrees(frame_yaw_spread) < 2.0 and frame_translation_spread < .025 and
              top[0]["robot_surface_inlier_ratio_35mm"] >= .25 and top[0]["robot_surface_median_m"] <= .045)
    transform = np.asarray(top[0]["T_body_camera"])
    evidence = {"support_revision": support["selected_support_track_id"],
                "robot_model_revision": geometry["robot_model_sha256"],
                "multi_start_seeds": seeds}
    revision = canonical_transform_revision(transform, evidence)
    result = {
        "schema_version": 1,
        "state": "CANDIDATE" if unique else "AUTO_REGISTRATION_INCONCLUSIVE",
        "planning_allowed": False,
        "execution_allowed": False,
        "method": "support-plane constrained yaw+xyz robust robot-sphere-surface registration",
        "registration_mask": {"organized_pixel_roi_xyxy": args.robot_pixel_roi,
                              "reason": "right arm is visibly clipped against the right image edge; table plane removed"},
        "T_body_camera": transform.tolist(),
        "candidate_revision": revision,
        "support_plane_residual_m": support["plane_tracks_ranked"][0]["members"][0]["rms_residual_m"],
        "robot_model_point_count": len(model_body),
        "cloud_voxel_point_counts": [len(cloud) for cloud in clouds],
        "multi_start_solutions": solutions,
        "four_frame_metrics": frame_metrics,
        "stability": {"multi_start_yaw_spread_deg": math.degrees(yaw_spread),
                      "multi_start_translation_spread_m": multi_start_spread,
                      "four_frame_yaw_spread_deg": math.degrees(frame_yaw_spread),
                      "four_frame_translation_spread_m": frame_translation_spread},
        "acceptance": {"unique_stable_solution": unique, "max_yaw_spread_deg": 3.0,
                       "max_translation_spread_m": .04, "min_inlier_ratio_35mm": .25,
                       "max_median_residual_m": .045},
        "limitations": geometry["limitations"] + ["single static robot posture", "no semantic robot mask",
                                                    "table height estimated rather than surveyed"],
    }
    (output / "T_body_camera.candidate.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "body_registration_metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    plot_overlay(clouds[0], transform, model_body, spheres, output / "04_body_overlay_full.png",
                 "%s — %s" % (result["state"], revision[7:19]))
    # Zoom is intentionally generated from the same evidence, with fixed BODY limits.
    plot_overlay(clouds[0], transform, model_body, spheres, output / "05_body_overlay_right_arm_zoom.png",
                 "Right-arm registration candidate — quantitative review required")
    print(json.dumps({"state": result["state"], "revision": revision,
                      "best": top[0], "stability": result["stability"]}))


if __name__ == "__main__":
    main()
