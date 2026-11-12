#!/usr/bin/env python3
"""Read-only tool-centerline audit against the pinned link6 gripper envelope."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from ares_r.perception.robot_collision import transform_xyz_rpy


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-audit", type=Path, required=True)
    parser.add_argument("--right-audit", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("config/robot_collision_model.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    model = load(args.model)
    envelope = model["gripper_max_envelope_link6"]
    center = np.asarray(envelope["center_m"])
    half = np.asarray(envelope["half_extents_m"])
    model_low, model_high = center - half, center + half
    result = {"schema_version": 1, "frame": "link6/flange", "unit": "mm",
              "analysis_only": True, "model_revision": model["asset_revision"],
              "gripper_envelope_z_max_mm": float(model_high[2] * 1000),
              "flange_normal_assumption": "link6 +Z, supported by pinned gripper envelope extending from z=0",
              "arms": {}}
    for side, path in (("left", args.left_audit), ("right", args.right_audit)):
        audit = load(path)
        tool = audit["diagnostics"]["tool_data"]
        pose = np.asarray(tool["pose_mm_rad"], dtype=float)
        frame = transform_xyz_rpy(pose[:3] * .001, pose[3:])
        tool_z = frame[:3, 2]
        tilt = float(np.degrees(np.arccos(np.clip(tool_z[2], -1, 1))))
        lateral = float(np.linalg.norm(pose[:2]))
        result["arms"][side] = {
            "tool_id": tool["tool_id"], "tcp_link6_xyz_mm": pose[:3].tolist(),
            "tool_rpy_rad": pose[3:].tolist(),
            "distance_from_flange_normal_mm": lateral,
            "axial_distance_mm": float(pose[2]),
            "tool_z_vs_flange_plus_z_deg": tilt,
            "tcp_ahead_of_pinned_gripper_envelope_mm": float(pose[2] - model_high[2] * 1000),
            "source_audit": str(path.resolve()),
        }
    (args.output_dir / "tcp_centerline_audit.json").write_text(
        json.dumps(result, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    figure, axes = plt.subplots(2, 2, figsize=(12, 11))
    for col, side in enumerate(("left", "right")):
        item = result["arms"][side]
        x, y, z = item["tcp_link6_xyz_mm"]
        top = axes[0, col]
        top.add_patch(Rectangle((model_low[0] * 1000, model_low[1] * 1000),
                                2 * half[0] * 1000, 2 * half[1] * 1000,
                                facecolor="lightskyblue", alpha=.25,
                                edgecolor="tab:blue", linewidth=2))
        top.scatter([0], [0], marker="+", s=130, c="black", label="flange +Z axis")
        top.scatter([x], [y], s=110, c="crimson", label="controller TCP")
        top.plot([0, x], [0, y], "r--")
        top.set(title=f"{side}: looking along flange +Z (XY)", xlabel="link6 X [mm]",
                ylabel="link6 Y [mm]", xlim=(-65, 65), ylim=(-65, 65))
        top.set_aspect("equal"); top.grid(True); top.legend(loc="lower left")
        side_view = axes[1, col]
        side_view.add_patch(Rectangle((model_low[0] * 1000, model_low[2] * 1000),
                                      2 * half[0] * 1000, 2 * half[2] * 1000,
                                      facecolor="lightskyblue", alpha=.25,
                                      edgecolor="tab:blue", linewidth=2,
                                      label="pinned gripper envelope"))
        side_view.axvline(0, color="black", ls="--", label="flange centerline")
        side_view.scatter([x], [z], s=110, c="crimson", label="controller TCP")
        side_view.set(title=(f"{side}: lateral {item['distance_from_flange_normal_mm']:.1f} mm; "
                             f"TCP {item['tcp_ahead_of_pinned_gripper_envelope_mm']:.1f} mm beyond model"),
                      xlabel="link6 X [mm]", ylabel="link6 Z [mm]",
                      xlim=(-65, 65), ylim=(-10, 205))
        side_view.grid(True); side_view.legend(loc="upper left")
    figure.tight_layout()
    figure.savefig(args.output_dir / "tcp_centerline_audit.png", dpi=180)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
