#!/usr/bin/env python3
"""Compare box-free and box-present planning-only A/B paths and clearances."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return json.loads(Path(path).read_text())


def resample(points, count=101):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 2:
        raise ValueError("successful Nx3 TCP path required")
    arc = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))))
    if arc[-1] <= 0:
        raise ValueError("zero-length TCP path")
    return np.column_stack([np.interp(np.linspace(0, arc[-1], count), arc, points[:, i])
                            for i in range(3)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear-preview", type=Path, required=True)
    parser.add_argument("--avoid-preview", type=Path, required=True)
    parser.add_argument("--box-object-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    clear_contract = load(args.clear_preview / "ab_contract.json")
    avoid_contract = load(args.avoid_preview / "ab_contract.json")
    for label in ("A", "B"):
        if np.max(np.abs(np.asarray(clear_contract[label]["joints_rad"]) -
                          np.asarray(avoid_contract[label]["joints_rad"]))) > 1e-4:
            raise ValueError("A/B contract changed between CLEAR and AVOID")
    output = {"schema_version": 1, "planning_only": True,
              "execution_allowed": False,
              "clear_snapshot_id": clear_contract["scene_snapshot_id"],
              "avoid_snapshot_id": avoid_contract["scene_snapshot_id"],
              "box_object_id": args.box_object_id, "legs": {}}
    figure, axes = plt.subplots(2, 4, figsize=(18, 8), sharex="col")
    progress = np.linspace(0, 1, 101)
    for row, leg in enumerate(("A_to_B", "B_to_A")):
        clear = load(args.clear_preview / leg / "planning.json")
        avoid = load(args.avoid_preview / leg / "planning.json")
        if clear["observed_result"] != "SUCCESS" or avoid["observed_result"] != "SUCCESS":
            raise ValueError("cannot compare failed paths")
        clear_path = resample(clear["tcp_path_body_m"])
        avoid_path = resample(avoid["tcp_path_body_m"])
        separation = np.linalg.norm(clear_path - avoid_path, axis=1)
        box_gap = avoid["path_clearance_by_object_m"].get(args.box_object_id)
        if box_gap is None:
            raise ValueError("observed box missing from AVOID planner world")
        output["legs"][leg] = {
            "clear_tcp_path_length_m": clear["path_metrics"]["path_length_m"],
            "avoid_tcp_path_length_m": avoid["path_metrics"]["path_length_m"],
            "added_tcp_path_length_m": (avoid["path_metrics"]["path_length_m"] -
                                        clear["path_metrics"]["path_length_m"]),
            "max_path_separation_m": float(separation.max()),
            "mean_path_separation_m": float(separation.mean()),
            "clear_min_world_gap_m": clear["clearance_m"]["planned_path"],
            "avoid_min_world_gap_m": avoid["clearance_m"]["planned_path"],
            "avoid_box_gap_m": box_gap,
            "avoid_joint_linear_baseline_gap_m": avoid["clearance_m"]["joint_linear_baseline"],
            "avoid_limiting_object_id": avoid["path_limiting_object_id"],
            "clear_planning_s": clear["timing_s"]["planning_samples"],
            "avoid_planning_s": avoid["timing_s"]["planning_samples"],
        }
        for col, label in enumerate(("BODY X", "BODY Y", "BODY Z")):
            ax = axes[row, col]
            ax.plot(progress, clear_path[:, col], "--", color="#1a9641",
                    label="box-free CLEAR")
            ax.plot(progress, avoid_path[:, col], color="#d7191c",
                    label="observed-box AVOID")
            ax.set_ylabel(f"{leg} {label} [m]")
            ax.grid(True, alpha=.3)
        ax = axes[row, 3]
        ax.plot(progress, separation * 1000, color="#6a3d9a")
        ax.set_ylabel(f"{leg} path separation [mm]")
        ax.grid(True, alpha=.3)
    for ax in axes[-1]:
        ax.set_xlabel("normalized TCP path progress")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2)
    figure.suptitle("P3.1 SAME A/B: box-free vs observed-box planning-only paths",
                     fontsize=15, weight="bold")
    figure.tight_layout(rect=(0, .06, 1, .94))
    figure.savefig(args.output_dir / "ab_path_comparison.png", dpi=180)
    (args.output_dir / "comparison.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
