#!/usr/bin/env python3
"""Static audit that generic scene runtime has no object/demo hard-coding."""

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "src/ares_r/motion/live_scene.py",
    "src/ares_r/motion/local_scene_service.py",
    "src/ares_r/motion/scene_aware_motion.py",
    "src/ares_r/motion/scene_aware_planner.py",
    "scripts/p32_scan_scene.py",
    "scripts/build_p3_production_scene.py",
    "src/ares_r/motion/production_scene_worker.py",
    "src/ares_r/perception/support_decomposition.py",
)
FORBIDDEN = {
    "fixed_scene_snapshot": r"SCENE_[0-9a-f]{8,}",
    "specific_cluster_id": r"observed_support_03",
    "historical_current_base": r"current_base_(?:clear|avoid|block)",
    "historical_scene_input": r"worklog/evidence/2026-09-(?:20|21)-",
    "manual_box_coordinate": r"(?:box|dock)_(?:xyz|pose|coordinate)",
    "fixed_obstacle_count": r"(?:obstacle|primitive)_count\s*[=!<>]=?\s*\d+",
}


def audit():
    findings = []
    for relative in FILES:
        text = (ROOT / relative).read_text()
        for rule, pattern in FORBIDDEN.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                findings.append({"rule": rule, "file": relative,
                                 "line": text.count("\n", 0, match.start()) + 1,
                                 "match": match.group(0)})
    live = (ROOT / "src/ares_r/motion/live_scene.py").read_text()
    required = ("fresh_camera", "current_robot_state", "commissioned_calibration",
                "generic_scene_parameters")
    missing = [item for item in required if item not in live]
    return {"schema_version": 1,
            "SCENE_RUNTIME_HARDCODE_AUDIT": "PASS" if not findings and not missing else "FAIL",
            "NO_MANUAL_OBSTACLE_COORDINATES": not any(
                row["rule"] == "manual_box_coordinate" for row in findings),
            "NO_OBJECT_SPECIFIC_AVOIDANCE_CODE": not any(
                row["rule"] == "specific_cluster_id" for row in findings),
            "files": list(FILES), "findings": findings,
            "missing_runtime_inputs": missing}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")
    if result["SCENE_RUNTIME_HARDCODE_AUDIT"] != "PASS":
        raise SystemExit(2)
