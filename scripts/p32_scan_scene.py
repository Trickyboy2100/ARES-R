#!/usr/bin/env python3
"""Fresh camera/state/geometry/SceneSnapshot for one P3.2 planning-only leg.

This command has no motion adapter and never arms an execution lease.  It is
safe to run while the robot is stationary; captured data remain local.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.perception.body_pointcloud import capture_body_cloud


def run(*args, python=None):
    subprocess.run([python or sys.executable, *map(str, args)], cwd=ROOT,
                   env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("CLEAR", "AVOID", "BLOCK"), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--open3d-python", type=Path, required=True,
                   help="site Python with Open3D for residual decomposition")
    p.add_argument("--block-search", type=Path,
                   help="versioned A/B search artifact; required for BLOCK goal enclosure")
    p.add_argument("--candidate", type=int, default=1)
    args = p.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite prior capture")
    output.mkdir(parents=True)
    config = json.loads((ROOT / "config/system.json").read_text())
    started = time.perf_counter()
    manifest = capture_body_cloud(config)
    capture_s = time.perf_counter() - started
    model = json.loads(Path(config["robot_collision"]["model"]).read_text())
    robot_urdf = Path(model["asset_root"]) / model["urdf"]
    left = output / "left_fk_audit.json"
    right = output / "right_fk_audit.json"
    run(ROOT / "scripts/audit_curobo_fk.py", robot_urdf, left, "--side", "left")
    run(ROOT / "scripts/audit_curobo_fk.py", robot_urdf, right, "--side", "right")
    geometry = output / "whole_robot_geometry.json"
    run(ROOT / "scripts/export_whole_robot_geometry.py", "--model",
        config["robot_collision"]["model"], "--world", ROOT / "config/robot_world.json",
        "--left-audit", left, "--right-audit", right, "--output", geometry)
    pointer = json.loads((manifest.parents[2] / "latest.json").read_text())
    pointer["manifest"] = str(manifest.resolve())
    pointer["camera_capture_elapsed_s"] = capture_s
    (output / "capture_pointer.json").write_text(json.dumps(pointer, indent=2)+"\n")
    scene = output / "scene"
    target_args = []
    if args.mode == "BLOCK":
        if args.block_search is None:
            raise ValueError("BLOCK requires explicit A/B contract; no guessed goal")
        candidate = json.loads(args.block_search.read_text())["candidates"][args.candidate]
        actual = json.loads(right.read_text())["diagnostics"]["joint_position_rad"]
        target = {"schema_version": 1, "contract": "P3_2_SYNTHETIC_BLOCK_GOAL",
                  "active_arm": "right", "start_rad": actual,
                  "goal_rad": candidate["B_joints_rad"],
                  "A": {"frame": "BODY", "xyz_m": candidate["A_xyz_m"]},
                  "B": {"frame": "BODY", "xyz_m": candidate["B_xyz_m"]},
                  "execution_allowed": False}
        target_file = output / "block_targets.json"
        target_file.write_text(json.dumps(target, indent=2)+"\n")
        target_args = ["--targets", target_file]
    run(ROOT / "scripts/build_p3_production_scene.py", "--mode", args.mode,
        "--manifest", manifest, "--geometry", geometry,
        "--left-audit", left, "--right-audit", right,
        "--obstacle-pipeline", "multi_primitive", "--capture-pointer",
        output / "capture_pointer.json", "--output", scene, *target_args,
        python=str(args.open3d_python))
    report = json.loads((scene / "scene_report.json").read_text())
    summary = {"planning_only": True, "execution_allowed": False,
               "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
               "capture_manifest": str(manifest.resolve()),
               "pointcloud_sha256": report["pointcloud_sha256"],
               "snapshot_id": report["snapshot_id"],
               "joint_snapshot_revision": report["joint_snapshot_revision"],
               "mode": args.mode, "total_s": time.perf_counter()-started}
    (output / "fresh_scene_summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
