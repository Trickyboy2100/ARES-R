#!/usr/bin/env python3
"""Capture right_pick 5700 + Pixel Pro cloud as one immutable epoch.

This command reads both arms but has no motion or gripper command path.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.adapters.epic import EpicClient
from ares_r.manipulation.observation_transaction import ManipulationObservationTransaction
from ares_r.motion.live_scene import build_live_planning_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "config/system.json").read_text(encoding="utf-8"))
    model = json.loads(Path(config["robot_collision"]["model"]).read_text())
    urdf = Path(model["asset_root"]) / model["urdf"]

    def read_state(label):
        directory = args.output / ("robot_state_" + label)
        directory.mkdir(parents=True, exist_ok=True)
        result = {}
        for side in ("left", "right"):
            target = directory / (side + ".json")
            subprocess.run(["python3", str(ROOT / "scripts/audit_curobo_fk.py"),
                            str(urdf), str(target), "--side", side], cwd=ROOT,
                           env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), check=True)
            result[side] = json.loads(target.read_text())
        return result

    epic = EpicClient(config["epic"])
    transaction = ManipulationObservationTransaction(
        config, detect=lambda name: epic._detect_profile(name, "pick"),
        read_robot_state=read_state, scene_builder=build_live_planning_scene)
    artifact = transaction.capture(args.output)
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
