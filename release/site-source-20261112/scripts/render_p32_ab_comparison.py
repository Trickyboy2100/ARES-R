#!/usr/bin/env python3
"""Three BODY views plus path metrics for cuRobo-only P3.2 planning evidence."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
import numpy as np
from scipy.spatial import ConvexHull


def load(path):
    return json.loads(Path(path).read_text())


def resample(points, count=101):
    points = np.asarray(points, dtype=float)
    distances = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    return np.column_stack([np.interp(np.linspace(0, distances[-1], count), distances, points[:, i])
                            for i in range(3)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clear-forward", required=True)
    p.add_argument("--clear-reverse", required=True)
    p.add_argument("--avoid-forward", required=True)
    p.add_argument("--avoid-reverse", required=True)
    p.add_argument("--avoid-scene", required=True)
    p.add_argument("--avoid-geometry", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    paths = {"clear_forward": load(a.clear_forward), "clear_reverse": load(a.clear_reverse),
             "avoid_forward": load(a.avoid_forward), "avoid_reverse": load(a.avoid_reverse)}
    scene = load(Path(a.avoid_scene) / "scene_report.json")
    geometry = load(a.avoid_geometry)
    contract = load(Path(a.avoid_forward).with_name("ab_plan_contract.json"))
    A = np.asarray(contract["ab_contract"]["A_xyz_m"])
    B = np.asarray(contract["ab_contract"]["B_xyz_m"])
    box_ids = paths["avoid_forward"]["ab_demo"]["corridor"]["observed_blocking_object_ids"]
    if not box_ids:
        raise ValueError("AVOID reference corridor not blocked by an observed obstacle")
    box_id = (paths["avoid_forward"]["path_limiting_object_id"]
              if paths["avoid_forward"]["path_limiting_object_id"] in box_ids else box_ids[0])
    box = next(item for item in scene["objects"] if item["id"] == box_id)
    cloud = np.load(Path(a.avoid_scene) / "clean_residual.npz")["points_body_m"]
    cloud = cloud[::max(1, len(cloud)//14000)]
    figures, axes = plt.subplots(1, 3, figsize=(22, 7))
    views = [("TOP: +X forward, +Y left", 0, 1),
             ("REAR: +Y left, +Z up", 1, 2),
             ("RIGHT: +X forward, +Z up", 0, 2)]
    lines = [("CLEAR A→B cuRobo", "clear_forward", "#239b56", "--"),
             ("CLEAR B→A cuRobo", "clear_reverse", "#56b870", ":"),
             ("AVOID A→B cuRobo", "avoid_forward", "#c0392b", "-"),
             ("AVOID B→A cuRobo", "avoid_reverse", "#d95f02", "-")]
    box_center, box_dims = np.asarray(box["center_m"]), np.asarray(box["dims_m"])
    for ax, (title, i, j) in zip(axes, views):
        ax.scatter(cloud[:, i], cloud[:, j], s=.6, c="#999999", alpha=.27,
                   label="observed BODY residual cloud")
        for item in geometry["boxes"]:
            center = np.asarray(item["center_body_m"])
            rotation = np.asarray(item["rotation_body"])
            half = np.asarray(item["half_extents_m"])
            corners = np.asarray([center + rotation @ (half*np.array([sx, sy, sz]))
                                  for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
            projected = corners[:, [i, j]]
            hull = ConvexHull(projected)
            owner = item["owner"]
            color = ("#2b83ba" if owner.startswith("right") else
                     "#fdae61" if owner.startswith("left") else
                     "#bd1e1e" if owner == "safety" else "#c3b131")
            ax.add_patch(Polygon(projected[hull.vertices], closed=True,
                                 edgecolor=color, facecolor=color, lw=.5, alpha=.075))
        for owner, color in (("left", "#fdae61"), ("right", "#2b83ba")):
            centers = []
            for link in ("base_link", "link1", "link2", "link3", "link4", "link5", "link6"):
                item = next((row for row in geometry["boxes"]
                             if row["geometry_id"] == owner+"/"+link), None)
                if item:
                    centers.append(item["center_body_m"])
            centers = np.asarray(centers)
            ax.plot(centers[:, i], centers[:, j], marker="o", ms=3,
                    lw=1.5, color=color, label=owner+" arm links")
        for label, name, color, style in lines:
            path = np.asarray(paths[name]["tcp_path_body_m"])
            if len(path):
                ax.plot(path[:, i], path[:, j], style, lw=3.0 if "AVOID" in label else 2.0,
                        color=color, label=label)
        for label, point, color in (("A", A, "#0c914d"), ("B", B, "#395bc7")):
            ax.scatter([point[i]], [point[j]], s=170, c=color, edgecolors="black", zorder=15)
            ax.annotate(label, (point[i], point[j]), xytext=(5, 8),
                        textcoords="offset points", weight="bold", fontsize=13)
        rect = Rectangle((box_center[i]-box_dims[i]/2, box_center[j]-box_dims[j]/2),
                         box_dims[i], box_dims[j], ec="#de6b00", fc="#ffb54d",
                         alpha=.28, lw=2.5, label="observed box AABB")
        ax.add_patch(rect)
        if (i, j) == (0, 1):
            ax.axhspan(-.07, .07, color="red", alpha=.07)
        if (i, j) == (1, 2):
            ax.axvspan(-.07, .07, color="red", alpha=.07)
        ax.set(title=title, xlabel=("BODY X [m]" if i == 0 else "BODY Y [m]"),
               ylabel=("BODY Y [m]" if j == 1 else "BODY Z [m]"))
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=.3)
    axes[0].set_xlim(-.1, 1.3); axes[0].set_ylim(-.75, .75)
    axes[1].set_xlim(-.75, .75); axes[1].set_ylim(.70, 1.70)
    axes[2].set_xlim(-.1, 1.3); axes[2].set_ylim(.70, 1.70)
    handles, labels = axes[0].get_legend_handles_labels()
    figures.legend(handles, labels, loc="lower center", ncol=4, fontsize=10)
    figures.suptitle("P3.2 cuRobo-only A/B planning; real box, NO waypoint; execution BLOCKED",
                     fontsize=15, weight="bold")
    figures.text(.015, .94, "AVOID scenes: %s / %s | calibration: %s | geometry: %s" % (
        paths["avoid_forward"]["scene_snapshot_id"], paths["avoid_reverse"]["scene_snapshot_id"],
        scene["calibration_revision"][:30], scene["geometry_revision"][:30]), fontsize=8)
    figures.text(.015, .915, "minimum modeled gap A→B %.1f mm, B→A %.1f mm | tool/TCP physical semantics UNRESOLVED" % (
        1000*paths["avoid_forward"]["clearance_m"]["planned_path"],
        1000*paths["avoid_reverse"]["clearance_m"]["planned_path"]), fontsize=9)
    figures.tight_layout(rect=(0, .08, 1, .89))
    figures.savefig(a.output_dir/"p32_three_views.png", dpi=180)
    plt.close(figures)

    comparison = {"planning_only": True, "execution_allowed": False,
                  "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
                  "clear_scene_ids": [paths["clear_forward"]["scene_snapshot_id"],
                                      paths["clear_reverse"]["scene_snapshot_id"]],
                  "avoid_scene_ids": [paths["avoid_forward"]["scene_snapshot_id"],
                                      paths["avoid_reverse"]["scene_snapshot_id"]],
                  "observed_box_id": box_id, "legs": {}}
    fig, axs = plt.subplots(2, 4, figsize=(18, 8), sharex="col")
    for row, direction in enumerate(("forward", "reverse")):
        clear = paths["clear_"+direction]
        avoid = paths["avoid_"+direction]
        avoid_path = a.avoid_forward if direction == "forward" else a.avoid_reverse
        leg_box_ids = avoid["ab_demo"]["corridor"]["observed_blocking_object_ids"]
        leg_box_id = (avoid["path_limiting_object_id"] if avoid["path_limiting_object_id"] in leg_box_ids
                      else leg_box_ids[0])
        c, v = resample(clear["tcp_path_body_m"]), resample(avoid["tcp_path_body_m"])
        separation = np.linalg.norm(c-v, axis=1)
        comparison["legs"][direction] = {
            "max_path_separation_m": float(separation.max()),
            "mean_path_separation_m": float(separation.mean()),
            "clear_path_length_m": clear["path_metrics"]["path_length_m"],
            "avoid_path_length_m": avoid["path_metrics"]["path_length_m"],
            "avoid_max_tcp_z_m": avoid["ab_demo"]["max_tcp_z_m"],
            "avoid_arc_height_m": avoid["ab_demo"]["arc_height_above_endpoints_m"],
            "clear_min_gap_m": clear["clearance_m"]["planned_path"],
            "avoid_min_gap_m": avoid["clearance_m"]["planned_path"],
            "avoid_box_id": leg_box_id,
            "avoid_box_gap_m": avoid["path_clearance_by_object_m"].get(leg_box_id)}
        progress = np.linspace(0, 1, len(c))
        for col, axis_name in enumerate("XYZ"):
            axs[row, col].plot(progress, c[:, col], "--", color="#239b56", label="CLEAR cuRobo")
            axs[row, col].plot(progress, v[:, col], color="#c0392b", label="AVOID cuRobo")
            axs[row, col].set_ylabel(f"{direction} BODY {axis_name} [m]")
            axs[row, col].grid(True, alpha=.3)
        axs[row, 3].plot(progress, 1000*separation, color="#782f9c")
        axs[row, 3].set_ylabel(f"{direction} separation [mm]")
        axs[row, 3].grid(True, alpha=.3)
    for axis in axs[-1]:axis.set_xlabel("normalized TCP arc progress")
    fig.legend(*axs[0, 0].get_legend_handles_labels(), loc="lower center", ncol=2)
    fig.suptitle("P3.2 SAME A/B: scene-aware cuRobo with/without observed box; no waypoint",
                 fontsize=15, weight="bold")
    fig.tight_layout(rect=(0, .07, 1, .94))
    fig.savefig(a.output_dir/"p32_path_comparison.png", dpi=180)
    plt.close(fig)
    (a.output_dir/"comparison.json").write_text(json.dumps(comparison, indent=2)+"\n")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
