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


def audit_with_readonly_retry(urdf, output, side):
    """Retry transient JAKA read errors; never substitute cached joint state."""
    for attempt in range(3):
        try:
            # The system JAKA Python binding is the site-proven read-only
            # diagnostic runtime; Open3D's calib environment is for clouds.
            run(ROOT / "scripts/audit_curobo_fk.py", urdf, output,
                "--side", side, python="python3")
            return
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(1.0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("LIVE", "CLEAR", "AVOID", "BLOCK"), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--open3d-python", type=Path, required=True,
                   help="site Python with Open3D for residual decomposition")
    p.add_argument("--block-search", type=Path,
                   help="versioned A/B search artifact; required for BLOCK goal enclosure")
    p.add_argument("--candidate", type=int, default=1)
    p.add_argument("--active", choices=("left", "right"), default="right")
    p.add_argument("--deployment-voxel-m", type=float,
                   choices=(.005,.0075,.010), help="deployment scene voxel size")
    p.add_argument("--detection-artifact", type=Path,
                   help="Epic detection captured in the same manipulation transaction")
    args = p.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite prior capture")
    output.mkdir(parents=True)
    config = json.loads((ROOT / "config/system.json").read_text())
    deployment = json.loads((ROOT / "config/scene_aware_motion.json").read_text())
    scene_profile = deployment["scene"]
    deployment_voxel = (float(args.deployment_voxel_m) if args.deployment_voxel_m is not None
                        else float(scene_profile["deployment_voxel_m"]))
    started = time.perf_counter()
    manifest = capture_body_cloud(config)
    capture_s = time.perf_counter() - started
    # Pixel Pro acquisition briefly loads the shared controller network.  Let
    # it settle before independent, read-only JAKA state snapshots; retries
    # below still fail closed instead of using yesterday's joint positions.
    settle_at=time.perf_counter();time.sleep(.5);settle_s=time.perf_counter()-settle_at
    model = json.loads(Path(config["robot_collision"]["model"]).read_text())
    robot_urdf = Path(model["asset_root"]) / model["urdf"]
    left = output / "left_fk_audit.json"
    right = output / "right_fk_audit.json"
    audit_at=time.perf_counter();audit_with_readonly_retry(robot_urdf, left, "left")
    audit_with_readonly_retry(robot_urdf, right, "right");audit_s=time.perf_counter()-audit_at
    geometry = output / "whole_robot_geometry.json"
    geometry_at=time.perf_counter();run(ROOT / "scripts/export_whole_robot_geometry.py", "--model",
        config["robot_collision"]["model"], "--world", ROOT / "config/robot_world.json",
        "--left-audit", left, "--right-audit", right, "--output", geometry)
    geometry_s=time.perf_counter()-geometry_at
    pointer = json.loads((manifest.parents[2] / "latest.json").read_text())
    pointer["manifest"] = str(manifest.resolve())
    pointer["camera_capture_elapsed_s"] = capture_s
    pointer["capture_body_total_s"] = capture_s
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
        "--active", args.active,
        "--obstacle-pipeline", "multi_primitive",
        "--deployment-voxel-m", str(deployment_voxel),
        "--self-filter-margin-m", str(scene_profile["robot_self_filter_margin_m"]),
        "--gripper-self-filter-margin-m", str(scene_profile["gripper_self_filter_margin_m"]),
        "--capture-pointer",
        output / "capture_pointer.json", "--output", scene,
        *(["--detection-artifact", args.detection_artifact]
          if args.detection_artifact is not None else []), *target_args,
        python=str(args.open3d_python))
    report = json.loads((scene / "scene_report.json").read_text())
    summary = {"planning_only": True, "execution_allowed": False,
               "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
               "capture_manifest": str(manifest.resolve()),
               "pointcloud_sha256": report["pointcloud_sha256"],
               "snapshot_id": report["snapshot_id"],
               "joint_snapshot_revision": report["joint_snapshot_revision"],
               "mode": args.mode,
               "timing_s":{"capture_body":capture_s,"network_settle":settle_s,
                           "read_only_joint_audits":audit_s,
                           "geometry_export":geometry_s,
                           "scene_build":report["timing_s"]["total_post_capture"]},
               "total_s": time.perf_counter()-started}
    (output / "fresh_scene_summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
