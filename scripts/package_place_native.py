#!/usr/bin/env python3
"""Package the place trajectories for the audited right supervised sender.

Mirrors ``scripts/package_first_pick_native.py``: same sender pin, same
``ARES_R_RIGHT_V2`` file contract, same speed ceilings.  It writes bytes only;
starting the sender stays an on-site, operator-confirmed action.
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ares_r.motion.native_execution_package import package_native_preview, verify_installed_sender

SENDER = Path("/home/yikun/ares-r-curobo-assets/jaka_right_supervised_path_v6_pick")
SPEEDS = {"preplace": (0.10, 0.20), "descend": (0.05, 0.10), "retreat": (0.05, 0.10)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--preplace-planning", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    package = json.loads(args.package.read_text(encoding="utf-8"))
    planning = json.loads(args.preplace_planning.read_text(encoding="utf-8"))
    request = json.loads((args.package.parent / "preplace_request.json")
                         .read_text(encoding="utf-8"))
    site = json.loads((ROOT / "config/jaka_mini2_motion.site.json").read_text(encoding="utf-8"))
    sender_sha = verify_installed_sender(SENDER)

    trajectories = {"preplace": planning["trajectory_points_rad"],
                    "descend": package["trajectories"]["descend"],
                    "retreat": package["trajectories"]["retreat"]}
    audits = {}
    for name, points in trajectories.items():
        speed, accel = SPEEDS[name]
        text, audit = package_native_preview(
            points, 0.008, site, tool_id=1,
            controller_tool_pose_mm_rad=request["controller_tool_pose_mm_rad"],
            captured_at_unix=int(time.time()), speed_ceiling_rad_s=speed,
            accel_ceiling_rad_s2=accel, tracking_stop_threshold_deg=1.5)
        (args.output / (name + ".native.txt")).write_text(text)
        (args.output / (name + ".audit.json")).write_text(json.dumps(audit, indent=2) + "\n")
        audits[name] = audit
    (args.output / "native_manifest.json").write_text(json.dumps({
        "place_package_sha256": package["package_sha256"],
        "sender": str(SENDER), "sender_sha256": sender_sha,
        "segments": audits}, indent=2) + "\n")
    print(json.dumps({name: {"duration_s": audit["duration_s"],
                             "samples": audit["sample_count"],
                             "predicted_tracking_deg": audit["predicted_tracking_gate_deg"]}
                      for name, audit in audits.items()}, indent=2))


if __name__ == "__main__":
    main()
