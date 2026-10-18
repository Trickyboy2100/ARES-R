#!/usr/bin/env python3
"""Render reusable BODY-frame motion/avoidance diagnostics.

The upper row is always TOP, REAR and RIGHT-SIDE projections.  The lower-left
plot compares dense planner clearance traces.  Everything is reconstructed
from frozen scene/planner artifacts; this command has no device or motion path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


EDGES = tuple((i, j) for i in range(8) for j in range(i + 1, 8)
              if bin(i ^ j).count("1") == 1)
PROJECTIONS = (
    ("TOP | BODY +X forward, +Y left", 0, 1),
    ("REAR | BODY +Y left, +Z up", 1, 2),
    ("RIGHT SIDE | BODY +X forward, +Z up", 0, 2),
)
AXIS_LABELS = ("BODY X [m]", "BODY Y [m]", "BODY Z [m]")
PLAN_COLORS = ("#d946ef", "#22c55e", "#0ea5e9", "#f97316", "#a855f7")


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def box_corners(center, rotation, half_extents) -> np.ndarray:
    signs = np.asarray([[x, y, z] for x in (-1, 1)
                        for y in (-1, 1) for z in (-1, 1)], dtype=float)
    return (np.asarray(center, dtype=float) +
            (signs * np.asarray(half_extents, dtype=float)) @
            np.asarray(rotation, dtype=float).T)


def curobo_cuboid_body_corners(value: dict, t_body_model) -> np.ndarray:
    """Convert one cuRobo model-frame cuboid (wxyz quaternion) to BODY."""
    pose = np.asarray(value["pose"], dtype=float)
    transform = np.asarray(t_body_model, dtype=float)
    w, x, y, z = pose[3:]
    norm = np.linalg.norm([w, x, y, z])
    if norm == 0:
        raise ValueError("cuRobo cuboid quaternion cannot be zero")
    w, x, y, z = np.asarray([w, x, y, z]) / norm
    rotation_model = np.asarray([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])
    center_body = (transform @ np.r_[pose[:3], 1.0])[:3]
    rotation_body = transform[:3, :3] @ rotation_model
    return box_corners(center_body, rotation_body,
                       np.asarray(value["dims"], dtype=float) / 2.0)


def parse_plan_argument(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("plan must be LABEL=/path/to/planning.json")
    label, path = value.split("=", 1)
    if not label.strip() or not path.strip():
        raise argparse.ArgumentTypeError("plan label and path must be non-empty")
    return label.strip(), Path(path).expanduser()


def _draw_box(ax, points, axes, color, linewidth=.7, alpha=.4, zorder=2):
    first, second = axes
    for start, end in EDGES:
        ax.plot([points[start, first], points[end, first]],
                [points[start, second], points[end, second]],
                color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)


def _scene_paths(scene_dir: Path):
    scene_dir = scene_dir.resolve()
    scene_root = scene_dir / "scene" if (scene_dir / "scene").is_dir() else scene_dir
    live_root = scene_root.parent
    return (scene_root / "compiled_scene.json",
            scene_root / "clean_residual.npz",
            live_root / "whole_robot_geometry.json")


def _attached_corners(request: dict):
    attached = request.get("attached_object_collision")
    if not attached or not request.get("robot_yaml_urdf"):
        return None
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    from ares_r.perception.robot_collision import arm_link_transforms
    link6 = arm_link_transforms(Path(request["robot_yaml_urdf"]),
                                request["start_rad"])["link6"]
    t_body_link6 = np.asarray(request["T_body_model"], dtype=float) @ link6
    geometry = attached["link6_aabb"]
    center = (t_body_link6 @ np.r_[geometry["center_m"], 1.0])[:3]
    return box_corners(center, t_body_link6[:3, :3],
                       np.asarray(geometry["dims_m"], dtype=float) / 2.0)


def render(scene_dir: Path, plans: list[tuple[str, Path]], output: Path,
           target_body, title: str, preferred_clearance_mm: float,
           max_cloud_points: int = 20000) -> dict:
    compiled_path, cloud_path, robot_path = _scene_paths(scene_dir)
    compiled = load_json(compiled_path)
    robot = load_json(robot_path)
    loaded = [(label, load_json(path)) for label, path in plans]
    request_path = plans[0][1].parent / "planner_request.json"
    request = load_json(request_path)
    cloud_file = np.load(cloud_path)
    cloud_key = "points_body_m" if "points_body_m" in cloud_file.files else cloud_file.files[0]
    cloud = np.asarray(cloud_file[cloud_key], dtype=float)
    if len(cloud) > max_cloud_points:
        cloud = cloud[::max(1, len(cloud) // max_cloud_points)]

    cuboids = [(name, curobo_cuboid_body_corners(value, request["T_body_model"]))
               for name, value in compiled.get("cuboids", {}).items()]
    limiting = loaded[0][1].get("path_limiting_object_id")
    attached = _attached_corners(request)
    nonempty_paths = [np.asarray(plan.get("tcp_path_body_m") or [], dtype=float)
                      for _, plan in loaded]
    current = next((path[0] for path in nonempty_paths if len(path)), None)
    target = (np.asarray(target_body, dtype=float) if target_body is not None else
              next((path[-1] for path in nonempty_paths if len(path)), None))

    fig = plt.figure(figsize=(24, 14))
    for panel, (view_title, first, second) in enumerate(PROJECTIONS, 1):
        ax = fig.add_subplot(2, 3, panel)
        ax.scatter(cloud[:, first], cloud[:, second], s=1, color="#777777",
                   alpha=.25, rasterized=True, label="clean residual cloud")
        for name, points in cuboids:
            if name == limiting:
                style = ("#d00000", 3.0, .95, 7)
            elif name.startswith("observed_"):
                style = ("#f59e0b", .55, .20, 2)
            elif name.startswith("known_support"):
                style = ("#8b5cf6", 1.2, .55, 3)
            else:
                continue
            _draw_box(ax, points, (first, second), *style)
        for geometry in robot.get("boxes", []):
            points = box_corners(geometry["center_body_m"],
                                 geometry["rotation_body"],
                                 geometry["half_extents_m"])
            owner = geometry.get("owner")
            color = ("#2563eb" if owner == "left_arm" else
                     "#00a6a6" if owner == "right_arm" else "#333333")
            _draw_box(ax, points, (first, second), color, 1.0, .6, 4)
        if attached is not None:
            _draw_box(ax, attached, (first, second), "#ff1493", 3.0, .95, 8)
        for index, ((label, _), path) in enumerate(zip(loaded, nonempty_paths)):
            if len(path):
                ax.plot(path[:, first], path[:, second], color=PLAN_COLORS[index % len(PLAN_COLORS)],
                        linewidth=2.2, label=label, zorder=9)
        if current is not None:
            ax.scatter(current[first], current[second], marker="*", s=230,
                       color="#111111", zorder=10, label="CURRENT TCP")
        if target is not None:
            ax.scatter(target[first], target[second], marker="X", s=180,
                       color="#16a34a", zorder=10, label="TARGET TCP")
        ax.set_title(view_title, fontsize=13, weight="bold")
        ax.set_xlabel(AXIS_LABELS[first]); ax.set_ylabel(AXIS_LABELS[second])
        ax.grid(alpha=.25); ax.set_aspect("equal", adjustable="datalim")
        if panel == 1:
            ax.legend(fontsize=8, loc="best")

    clearance_ax = fig.add_subplot(2, 3, 4)
    for index, (label, plan) in enumerate(loaded):
        trace = np.asarray(plan.get("planner_clearance_trace_m") or [], dtype=float)
        if len(trace):
            clearance_ax.plot(np.linspace(0, 100, len(trace)), trace * 1000,
                              color=PLAN_COLORS[index % len(PLAN_COLORS)], label=label)
    clearance_ax.axhline(0, color="red", linewidth=2, label="hard collision")
    clearance_ax.axhline(preferred_clearance_mm, color="#f59e0b", linestyle="--",
                         label="preferred %.0f mm" % preferred_clearance_mm)
    clearance_ax.set(title="Modeled clearance along candidate trajectories",
                     xlabel="Path progress [%]", ylabel="Minimum clearance [mm]")
    clearance_ax.grid(alpha=.3); clearance_ax.legend(fontsize=8)

    status_ax = fig.add_subplot(2, 3, 5)
    status_ax.axis("off")
    rows = []
    for label, plan in loaded:
        clearance = (plan.get("clearance_m") or {}).get("planned_path")
        orientation = plan.get("orientation_validation") or {}
        rows.append([label, plan.get("observed_result", "UNKNOWN"),
                     "-" if clearance is None else "%.1f mm" % (clearance * 1000),
                     "-" if not orientation else ("PASS" if orientation.get("passed") else "FAIL")])
    table = status_ax.table(cellText=rows,
                            colLabels=["Candidate", "Result", "Min clearance", "Orientation"],
                            loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(9); table.scale(1, 1.7)
    status_ax.set_title("Candidate summary")

    note_ax = fig.add_subplot(2, 3, 6); note_ax.axis("off")
    primary = loaded[0][1]
    orientation = primary.get("orientation_validation") or {}
    start_clearance = (primary.get("clearance_m") or {}).get("start")
    notes = ["FROZEN-ARTIFACT DIAGNOSTIC — NO DEVICE COMMANDS",
             "", "scene: %s" % compiled.get("scene_snapshot_id", "UNKNOWN"),
             "limiting object: %s" % (limiting or "not reported")]
    if start_clearance is not None:
        notes.append("start clearance: %.1f mm" % (start_clearance * 1000))
    if orientation:
        error = orientation.get("max_orientation_error_deg",
                                orientation.get("max_level_error_deg"))
        notes.append("orientation: %s%s" %
                     ("PASS" if orientation.get("passed") else "FAIL",
                      "" if error is None else " (max %.1f deg)" % error))
    notes += ["", "Legend:", "cyan=right arm, blue=left arm",
              "pink=attached object, orange=observed world",
              "red=reported limiting primitive, purple=support"]
    note_ax.text(0, 1, "\n".join(notes), va="top", family="monospace", fontsize=11)

    fig.suptitle(title, fontsize=18, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, .96))
    output = output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("refusing to overwrite diagnostic image: %s" % output)
    fig.savefig(output, dpi=180); plt.close(fig)
    return {"output": str(output), "scene_snapshot_id": compiled.get("scene_snapshot_id"),
            "plan_count": len(loaded), "limiting_object_id": limiting,
            "device_commands_issued": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True,
                        help="live_scene root or its scene/ child")
    parser.add_argument("--plan", action="append", type=parse_plan_argument, required=True,
                        help="repeatable LABEL=/path/to/planning.json")
    parser.add_argument("--target-body", nargs=3, type=float, metavar=("X", "Y", "Z"))
    parser.add_argument("--title", default="BODY Motion / Avoidance Diagnostic")
    parser.add_argument("--preferred-clearance-mm", type=float, default=30.0)
    parser.add_argument("--max-cloud-points", type=int, default=20000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = render(args.scene_dir, args.plan, args.output, args.target_body,
                    args.title, args.preferred_clearance_mm, args.max_cloud_points)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
