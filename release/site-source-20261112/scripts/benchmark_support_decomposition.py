#!/usr/bin/env python3
"""Compare fail-closed single AABBs with generic support decomposition."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.residual_cloud import PROFILES, DEFAULT_PROFILE, clean_and_cluster
from ares_r.perception.support_decomposition import decompose_support_objects

ROI = [[.22, -.76, .70], [1.30, .76, 1.40]]


def _draw_box(axis, center, dims, color, alpha=.6):
    center, half = np.asarray(center), np.asarray(dims) / 2
    corners = np.asarray([center + half * [x, y, z]
                          for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    for first, second in ((0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3),
                          (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)):
        axis.plot(*zip(corners[first], corners[second]), color=color, alpha=alpha, linewidth=.8)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_clean_npz", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    points = np.load(args.canonical_clean_npz)["points_body_m"]
    profile = next(value for value in PROFILES if value.name == DEFAULT_PROFILE)
    # Re-clustering already-clean points supplies the unchanged P3 comparator.
    old_clean, old_boxes, _ = clean_and_cluster(points, ROI, profile,
                                                table_half_band_m=0.0)
    report = decompose_support_objects(old_clean, old_boxes)
    (args.output_dir / "support_decomposition.json").write_text(
        json.dumps(report, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure = plt.figure(figsize=(16, 8))
    for index, title in enumerate(("old: one AABB per connected cluster",
                                   "new: observed multi-primitive world"), 1):
        axis = figure.add_subplot(1, 2, index, projection="3d")
        stride = max(1, len(old_clean) // 18000)
        axis.scatter(old_clean[::stride, 0], old_clean[::stride, 1], old_clean[::stride, 2],
                     s=.2, c="0.65", alpha=.35)
        if index == 1:
            for box in old_boxes:
                _draw_box(axis, box["center_m"], box["dims_m"], "#ff8c00")
        else:
            colors = {"SUPPORT_SURFACE": "#4daf4a", "STRUCTURE": "#377eb8",
                      "PROTRUDING_OBSTACLE": "#e41a1c", "UNKNOWN_OCCUPIED": "#984ea3"}
            for primitive in report["primitives"]:
                _draw_box(axis, primitive["center_m"], primitive["dims_m"],
                          colors[primitive["semantic"]], .65)
        axis.set_title(title); axis.set(xlabel="+X", ylabel="+Y", zlabel="+Z")
        axis.set_xlim(.2, 1.1); axis.set_ylim(-.7, .6); axis.set_zlim(.7, 1.35)
        axis.view_init(28, -62)
    figure.suptitle("P3.1 single-AABB vs generic support/object decomposition")
    figure.tight_layout(rect=(0, 0, 1, .92))
    figure.savefig(args.output_dir / "old_vs_multi_primitive.png", dpi=180)
    print(json.dumps({key: report[key] for key in (
        "old_single_aabb_count", "old_single_aabb_occupied_volume_m3",
        "multi_primitive_count", "multi_primitive_occupied_volume_m3",
        "occupied_volume_ratio", "timing_s")}, indent=2))


if __name__ == "__main__":
    main()
