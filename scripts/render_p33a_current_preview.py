#!/usr/bin/env python3
"""Three BODY projections of the exact CURRENT→A cuRobo TCP path; no motion."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_dir", type=Path)
    parser.add_argument("plan_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preview output already exists")
    scene = json.loads((args.scene_dir / "scene/scene_report.json").read_text())
    plan = json.loads((args.plan_dir / "planning.json").read_text())
    contract = json.loads((args.plan_dir / "ab_plan_contract.json").read_text())
    cloud = np.load(args.scene_dir / "scene/clean_residual.npz")["points_body_m"]
    path = np.asarray(plan["tcp_path_body_m"])
    current = np.asarray(contract["start_body_xyz_m"])
    goal = np.asarray(contract["goal_body_xyz_m"])
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (title, i, j) in zip(axes, (
            ("TOP: +X forward, +Y left", 0, 1),
            ("REAR: +Y left, +Z up", 1, 2),
            ("RIGHT: +X forward, +Z up", 0, 2))):
        ax.scatter(cloud[:, i], cloud[:, j], s=.35, c="#777777", alpha=.3,
                   label="clean BODY residual cloud")
        ax.plot(path[:, i], path[:, j], color="#e63232", lw=3,
                label="exact cuRobo CURRENT→A TCP path")
        ax.scatter([current[i]], [current[j]], s=140, color="#ffad33",
                   edgecolor="black", zorder=5, label="actual CURRENT")
        ax.scatter([goal[i]], [goal[j]], s=140, color="#22bb66",
                   edgecolor="black", zorder=5, label="approved A")
        if i == 0 and j == 1:
            ax.axhspan(-.07, .07, color="red", alpha=.08,
                       label="central TCP exclusion")
        ax.set(title=title, xlabel=("BODY X [m]" if i == 0 else "BODY Y [m]"),
               ylabel=("BODY Y [m]" if j == 1 else "BODY Z [m]"))
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.3)
    axes[0].legend(loc="best", fontsize=8)
    gap = plan["independent_dense_validation"]["min_clearance_m"]
    fig.suptitle("P3.3A RIGHT CURRENT→A | planning-only preview | no waypoint | gap %.1f mm" %
                 (gap*1000), fontsize=14)
    fig.text(.02, .02, "snapshot=%s | calibration=%s | tool physical semantics unresolved" %
             (scene["snapshot_id"], scene["calibration_revision"][:30]), fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .93))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
