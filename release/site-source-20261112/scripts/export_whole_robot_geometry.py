#!/usr/bin/env python3
"""Export one immutable BODY collision snapshot from saved read-only audits."""

import argparse
import json
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.robot_collision import build_geometry_snapshot, save_geometry_snapshot


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--world", required=True)
    parser.add_argument("--left-audit", required=True)
    parser.add_argument("--right-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audits = {"left": load(args.left_audit), "right": load(args.right_audit)}
    audits["left"]["report_path"] = str(Path(args.left_audit).resolve())
    audits["right"]["report_path"] = str(Path(args.right_audit).resolve())
    snapshot = build_geometry_snapshot(load(args.model), load(args.world), audits)
    save_geometry_snapshot(snapshot, Path(args.output))
    print(json.dumps({"output": str(Path(args.output).resolve()),
                      "box_count": len(snapshot.boxes),
                      "scene_revision": snapshot.scene_revision,
                      "timings_s": snapshot.timings_s}, indent=2))


if __name__ == "__main__":
    main()
