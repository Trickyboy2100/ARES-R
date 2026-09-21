#!/usr/bin/env python3
"""Explain robot-adjacent residuals against OBB and exact planner geometry."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.body_pointcloud import load_artifact
from ares_r.perception.residual_cloud import PROFILES, DEFAULT_PROFILE, clean_and_cluster
from ares_r.perception.robot_collision import load_geometry_snapshot, self_filter_body_cloud
from ares_r.perception.robot_owned_filter import (
    attribute_cluster, build_robot_owned_filter, filter_robot_owned)

ROI = [[.22, -.76, .70], [1.30, .76, 1.40]]


def _profile():
    return next(value for value in PROFILES if value.name == DEFAULT_PROFILE)


def _wire_box(axis, box, color, alpha=.35):
    center = np.asarray(box.center_body_m); rotation = np.asarray(box.rotation_body)
    half = np.asarray(box.half_extents_m)
    corners = np.asarray([center + rotation @ (half * [x, y, z])
                          for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    for first, second in ((0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
                          (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)):
        axis.plot(*zip(corners[first], corners[second]), color=color, alpha=alpha, linewidth=.7)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    cloud, _ = load_artifact(args.manifest); snapshot = load_geometry_snapshot(args.geometry)
    p2_keep, p2_stats = self_filter_body_cloud(cloud.points_body_m, snapshot, .030)
    clean_old, boxes_old, cleanup_old = clean_and_cluster(
        np.asarray(cloud.points_body_m)[p2_keep], ROI, _profile())
    owned = build_robot_owned_filter(snapshot)
    canonical_keep, canonical_stats = filter_robot_owned(cloud.points_body_m, owned)
    clean_new, boxes_new, cleanup_new = clean_and_cluster(
        np.asarray(cloud.points_body_m)[canonical_keep], ROI, _profile())
    rows = []
    for box in boxes_old:
        low, high = np.asarray(box["min_m"]), np.asarray(box["max_m"])
        member = clean_old[np.all((clean_old >= low) & (clean_old <= high), axis=1)]
        attribution = attribute_cluster(member, owned)
        inflated_low, inflated_high = low - .015, high + .015
        aabb_distances = []
        for sphere in owned.spheres:
            center = np.asarray(sphere.center_body_m)
            closest = np.minimum(np.maximum(center, inflated_low), inflated_high)
            aabb_distances.append(float(np.linalg.norm(center - closest) - sphere.radius_m))
        attribution["inflated_cluster_aabb_to_planning_sphere_m"] = min(aabb_distances)
        row = {"residual_id": box["object_id"], "bounds": box,
               "attribution": attribution}
        if row["attribution"]["classification"] == "ROBOT_OWNED_PLANNER_GEOMETRY":
            row["root_cause"] = "planner circumscribed-sphere volume outside P2 OBB self-filter"
        elif attribution["nearest_planning_sphere"]["signed_distance_m"] > 0 and min(aabb_distances) < 0:
            row["root_cause"] = "cluster AABB fills unobserved empty volume between points and robot"
            row["attribution"]["classification"] = "AABB_EMPTY_VOLUME_BRIDGE"
        else:
            row["root_cause"] = "external or sensor residual; not robot-owned by validated geometry"
        rows.append(row)
    result = {"schema_version": 1, "pointcloud_sha256": cloud.source_sha256,
              "joint_snapshot_revision": snapshot.joint_snapshot_revision,
              "tool_revision": snapshot.tool_revision,
              "geometry_revision": snapshot.geometry_revision,
              "p2_obb_filter": p2_stats, "robot_owned_filter": canonical_stats,
              "robot_owned_geometry": owned.as_dict(),
              "old_cleanup": cleanup_old, "canonical_cleanup": cleanup_new,
              "old_residual_count": len(boxes_old),
              "canonical_residual_count": len(boxes_new),
              "residual_attribution": rows,
              "state_sync": "same read-only joint/tool snapshot feeds OBB and planner geometry",
              "decision": "ROBOT_OWNED_FILTER union is admissible only for points inside exact planner geometry; no global margin increase"}
    (args.output_dir / "robot_adjacent_attribution.json").write_text(
        json.dumps(result, indent=2) + "\n")
    (args.output_dir / "robot_owned_filter_geometry.json").write_text(
        json.dumps(owned.as_dict(), indent=2) + "\n")
    np.savez_compressed(args.output_dir / "canonical_clean_residual.npz",
                        points_body_m=clean_new)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure = plt.figure(figsize=(14, 8)); axis = figure.add_subplot(111, projection="3d")
    stride = max(1, len(clean_old) // 25000)
    axis.scatter(clean_old[::stride, 0], clean_old[::stride, 1], clean_old[::stride, 2],
                 s=.25, c="0.65", alpha=.45, label="P2-filtered residual")
    sphere_centers = np.asarray([sphere.center_body_m for sphere in owned.spheres])
    axis.scatter(sphere_centers[:, 0], sphere_centers[:, 1], sphere_centers[:, 2],
                 s=3, c="#ffbf00", alpha=.65, label="exact planner sphere centers")
    for box in owned.boxes:
        if box.owner in ("right_arm", "right_gripper_tool"):
            _wire_box(axis, box, "#00d7ff")
    axis.set(xlabel="BODY +X forward [m]", ylabel="BODY +Y left [m]", zlabel="BODY +Z [m]")
    axis.set_xlim(.2, 1.1); axis.set_ylim(-.75, .55); axis.set_zlim(.7, 1.4)
    axis.view_init(24, -62); axis.legend(loc="upper left")
    axis.set_title("P3.1 robot-adjacent residual attribution\ncyan=P2 OBB, yellow=exact planning spheres")
    figure.tight_layout(); figure.savefig(args.output_dir / "robot_adjacent_overlay.png", dpi=180)
    print(json.dumps({"output": str(args.output_dir),
                      "old_residuals": len(boxes_old), "new_residuals": len(boxes_new),
                      "sphere_only_removed": canonical_stats["sphere_only_removed_points"],
                      "robot_owned_clusters": [row["residual_id"] for row in rows
                                               if row["attribution"]["classification"] == "ROBOT_OWNED_PLANNER_GEOMETRY"]}, indent=2))


if __name__ == "__main__":
    main()
