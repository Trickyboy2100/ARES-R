#!/usr/bin/env python3
"""Orthographic BODY views for a planning-only A/B obstacle experiment."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-preview", type=Path,
                        help="box-free A/B preview overlaid as dashed paths")
    parser.add_argument("--proposed-box-center", type=float, nargs=3)
    parser.add_argument("--proposed-box-dims", type=float, nargs=3)
    parser.add_argument("--observed-box-center", type=float, nargs=3)
    parser.add_argument("--observed-box-dims", type=float, nargs=3)
    args = parser.parse_args()
    contract = load(args.preview / "ab_contract.json")
    geometry = load(args.geometry)
    forward = load(args.preview / "A_to_B/planning.json")
    reverse = load(args.preview / "B_to_A/planning.json")
    cloud = np.load(args.scene / "clean_residual.npz")["points_body_m"]
    cloud = cloud[::max(1, len(cloud) // 14000)]
    paths = [("A → B current", np.asarray(forward.get("tcp_path_body_m", [])),
              "#1167b1", "-", 3),
             ("B → A current", np.asarray(reverse.get("tcp_path_body_m", [])),
              "#d7191c", "-", 3)]
    if args.reference_preview:
        reference = load(args.reference_preview / "ab_contract.json")
        if (np.max(np.abs(np.asarray(reference["A"]["joints_rad"]) -
                          np.asarray(contract["A"]["joints_rad"]))) > 1e-4 or
            np.max(np.abs(np.asarray(reference["B"]["joints_rad"]) -
                          np.asarray(contract["B"]["joints_rad"]))) > 1e-4):
            raise ValueError("reference A/B joints do not match current A/B")
        for leg in ("A_to_B", "B_to_A"):
            old = load(args.reference_preview / leg / "planning.json")
            paths.append((leg.replace("_", " ") + " box-free",
                          np.asarray(old.get("tcp_path_body_m", [])),
                          "#1a9641", "--", 2.5))
    A = np.asarray(contract["A"]["body_tcp_xyz_m"])
    B = np.asarray(contract["B"]["body_tcp_xyz_m"])
    figure, axes = plt.subplots(1, 3, figsize=(22, 7))
    views = [("TOP: +X forward, +Y left", 0, 1),
             ("REAR: +Y left, +Z up", 1, 2),
             ("RIGHT: +X forward, +Z up", 0, 2)]
    for ax, (title, i, j) in zip(axes, views):
        ax.scatter(cloud[:, i], cloud[:, j], s=.8, c="#808080", alpha=.35,
                   label="observed residual cloud")
        for arm, color in (("left", "#fdae61"), ("right", "#2b83ba")):
            centers = []
            for link in ("base_link", "link1", "link2", "link3", "link4", "link5", "link6"):
                item = next((box for box in geometry["boxes"]
                             if box["geometry_id"] == arm + "/" + link), None)
                if item:
                    centers.append(item["center_body_m"])
            if centers:
                centers = np.asarray(centers)
                ax.plot(centers[:, i], centers[:, j], color=color, marker="o", ms=4,
                        linewidth=2, label=arm + " arm link centers")
        for name, path, color, style, width in paths:
            if len(path):
                ax.plot(path[:, i], path[:, j], color=color, linestyle=style,
                        linewidth=width, label=name + " planned TCP")
        for label, point, color in (("A", A, "#00a651"), ("B", B, "#6a3d9a")):
            ax.scatter([point[i]], [point[j]], s=170, c=color, edgecolors="black",
                       linewidths=1, zorder=10)
            ax.annotate(label, (point[i], point[j]), xytext=(5, 8),
                        textcoords="offset points", fontsize=13, weight="bold")
        box_center = args.observed_box_center or args.proposed_box_center
        box_dims = args.observed_box_dims or args.proposed_box_dims
        if box_center and box_dims:
            center = np.asarray(box_center)
            dims = np.asarray(box_dims)
            observed = args.observed_box_center is not None
            rect = Rectangle((center[i] - dims[i] / 2, center[j] - dims[j] / 2),
                             dims[i], dims[j], linewidth=2.5, edgecolor="#e66101",
                             facecolor="#fdb863", alpha=.22,
                             linestyle="-" if observed else "--",
                             label="observed box AABB" if observed else
                                   "placement proposal, NOT observed")
            ax.add_patch(rect)
        if (i, j) == (0, 1):
            ax.axhspan(-.07, .07, color="red", alpha=.08,
                       label="central TCP exclusion ±70 mm")
        if (i, j) == (1, 2):
            ax.axvspan(-.07, .07, color="red", alpha=.08)
        ax.set(title=title, xlabel=("BODY +X [m]" if i == 0 else "BODY +Y [m]"),
               ylabel=("BODY +Y [m]" if j == 1 else "BODY +Z [m]"))
        ax.grid(True, alpha=.35)
        ax.set_aspect("equal", adjustable="box")
    axes[0].set_xlim(-.1, 1.3); axes[0].set_ylim(-.75, .75)
    axes[1].set_xlim(-.75, .75); axes[1].set_ylim(.70, 1.75)
    axes[2].set_xlim(-.1, 1.3); axes[2].set_ylim(.70, 1.75)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=4, fontsize=10)
    figure.suptitle("P3.1 CURRENT-BASE A/B PLANNING PREVIEW — NO MOTION / NO EXECUTION",
                     fontsize=15, weight="bold")
    figure.tight_layout(rect=(0, .08, 1, .94))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    print(args.output)


if __name__ == "__main__":
    main()
