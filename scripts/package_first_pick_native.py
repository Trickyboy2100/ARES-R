#!/usr/bin/env python3
"""Package the three authorized first-pick paths for the audited right sender."""

import argparse
import json
from pathlib import Path
import sys
import time
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion.native_execution_package import package_native_preview, verify_installed_sender

SENDER = Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--package", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    package = json.loads(a.package.read_text())
    site = json.loads((ROOT / "config/jaka_mini2_motion.site.json").read_text())
    verify_installed_sender(SENDER)
    trajectories = {
        "pregrasp": package["trajectories"]["pregrasp"],
        "contact": package["trajectories"]["contact"],
        "lift": package["trajectories"]["lift"],
    }
    speeds = {"pregrasp": (0.10, 0.20), "contact": (0.05, 0.10),
              "lift": (0.05, 0.10)}
    audits = {}
    for name, points in trajectories.items():
        speed, accel = speeds[name]
        text, audit = package_native_preview(
            points, 0.008, site, tool_id=1,
            controller_tool_pose_mm_rad=package["controller_tool_pose_mm_rad"],
            captured_at_unix=int(time.time()), speed_ceiling_rad_s=speed,
            accel_ceiling_rad_s2=accel, tracking_stop_threshold_deg=1.5,
            max_excursion_rad=math.radians(220))
        (a.output / (name + ".native.txt")).write_text(text)
        (a.output / (name + ".audit.json")).write_text(json.dumps(audit, indent=2) + "\n")
        audits[name] = audit
    (a.output / "native_manifest.json").write_text(json.dumps({
        "first_pick_package_sha256": package["package_sha256"],
        "sender": str(SENDER), "segments": audits}, indent=2) + "\n")
    print(json.dumps({k: {"duration_s": v["duration_s"],
                                "samples": v["sample_count"],
                                "tracking_prediction_deg": v["predicted_tracking_gate_deg"]}
                      for k, v in audits.items()}, indent=2))


if __name__ == "__main__":
    main()
