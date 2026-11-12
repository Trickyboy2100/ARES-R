#!/usr/bin/env python3
"""Open3D snapshot/interactive entry point for one canonical BODY cloud."""

import argparse
import json
import os
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.cli import load_config
from ares_r.perception.body_pointcloud import latest_manifest
from ares_r.visualization.body_cloud_live import benchmark_scans, run_live
from ares_r.visualization.body_cloud_viewer import render_snapshot, scene_spec, show_interactive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--snapshot")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--pick", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--benchmark-scans", type=int)
    parser.add_argument("--benchmark-output")
    args = parser.parse_args()
    config = load_config(str(REPOSITORY / "config/system.json"))
    world = REPOSITORY / "config/robot_world.json"
    crosscheck = REPOSITORY / "worklog/evidence/2026-09-20-body-camera-dual-arm-crosscheck/report.json"
    if args.benchmark_scans is not None:
        if not args.benchmark_output:
            parser.error("--benchmark-scans requires --benchmark-output")
        print(json.dumps(benchmark_scans(config, args.benchmark_scans, args.interval,
                                         Path(args.benchmark_output)), indent=2))
        return
    manifest = Path(args.manifest) if args.manifest else latest_manifest(config)
    if args.live:
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise SystemExit("native Open3D live viewer requires DISPLAY or WAYLAND_DISPLAY")
        run_live(config, world, crosscheck, args.interval, manifest)
        return
    spec = scene_spec(manifest, world, crosscheck)
    print(json.dumps({"frames": list(spec["frames"]), "table": spec["table"],
                      "calibration": spec["calibration"],
                      "points": spec["cloud"].valid_point_count}, indent=2))
    if args.snapshot:
        print(json.dumps(render_snapshot(spec, Path(args.snapshot)), indent=2))
    if args.interactive or (not args.snapshot and os.environ.get("DISPLAY")):
        show_interactive(spec, pick_points=args.pick)
    elif not args.snapshot:
        raise SystemExit("DISPLAY is unavailable; pass --snapshot OUTPUT.png")


if __name__ == "__main__":
    main()
