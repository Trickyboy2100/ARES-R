#!/usr/bin/env python3
"""Render P3.3 profile-repeat distributions; never label a rejected path safe."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sweep_summary", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError("refusing to overwrite sweep visualization")
    args.output_dir.mkdir(parents=True)
    summary = json.loads(args.sweep_summary.read_text())
    # A fail-closed early stop can leave later requested cases unrun; do not
    # imply those directions were measured by rendering empty panels.
    cases = [case for case in summary["cases"]
             if any(item["case"] == case for item in summary["trials"])]
    fig, axes = plt.subplots(len(cases), 3, figsize=(14, 2.7*len(cases)), squeeze=False)
    for row_index, case in enumerate(cases):
        rows = [item for item in summary["trials"] if item["case"] == case]
        for axis_index, (key, ylabel, scale) in enumerate((
                ("independent_clearance_m", "dense gap [mm]", 1000),
                ("max_tcp_z_m", "maximum BODY TCP Z [m]", 1),
                ("planning_time_s", "cuRobo planning [s]", 1))):
            ax = axes[row_index, axis_index]
            for item in rows:
                value = item.get(key)
                if value is None:
                    continue
                color = "#1a9850" if item["accepted"] else "#d73027"
                jitter = (item["repeat"] - 2) * 0.9
                ax.scatter(item["activation_mm"] + jitter, value*scale,
                           color=color, s=36, alpha=.8)
            if axis_index == 0:
                ax.axhline(30, color="black", linestyle="--", linewidth=1.2,
                           label="P3.3 acceptance gate")
                ax.legend(loc="best", fontsize=8)
            ax.set_xticks(summary["profiles_mm"])
            ax.set_xlim(min(summary["profiles_mm"])-5, max(summary["profiles_mm"])+5)
            ax.set_xlabel("optimizer activation [mm]")
            ax.set_ylabel(ylabel)
            ax.set_title(case)
            ax.grid(alpha=.3)
    fig.suptitle("P3.3 frozen-scene cuRobo repeats; RED = rejected; unmeasured cases omitted",
                 fontsize=14, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, .97))
    fig.savefig(args.output_dir / "p33_clearance_profile_sweep.png", dpi=175)
    plt.close(fig)
    compact = {"schema_version": 1, "planning_only": True,
               "execution_allowed": False, "gate_mm": 30,
               "completed_repeats": len(summary["trials"]),
               "cases": {}}
    for case in cases:
        compact["cases"][case] = {}
        for activation in summary["profiles_mm"]:
            values = [row.get("independent_clearance_m") for row in summary["trials"]
                      if row["case"] == case and row["activation_mm"] == activation]
            values = [v*1000 for v in values if v is not None]
            compact["cases"][case][str(activation)] = {
                "count": len(values), "min_mm": min(values) if values else None,
                "median_mm": float(np.median(values)) if values else None,
                "max_mm": max(values) if values else None,
                "all_above_30mm": len(values) >= summary["repeats"] and min(values) >= 30}
    (args.output_dir / "sweep_distribution.json").write_text(json.dumps(compact, indent=2) + "\n")
    print(json.dumps({"image": str(args.output_dir / "p33_clearance_profile_sweep.png"),
                      "trials": len(summary["trials"])}))


if __name__ == "__main__":
    main()
