#!/usr/bin/env python3
"""Generate the P0-B dual-arm BODY-camera cross-check report; no hardware I/O."""

import argparse
import json
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))

from ares_r.perception.handeye_crosscheck import REPORT_RELATIVE, build_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-validation", action="store_true",
                        help="preserve the matrix and add report provenance to config/system.json")
    args = parser.parse_args()
    report = build_report(REPOSITORY)
    target = REPOSITORY / REPORT_RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.write_validation:
        system_path = REPOSITORY / "config/system.json"
        system = json.loads(system_path.read_text(encoding="utf-8"))
        if report["state"] != "COMMISSIONED":
            raise SystemExit("cross-check failed; refusing to preserve COMMISSIONED provenance")
        section = system["epic_pointcloud"]
        section["T_body_camera_validation"] = {
            "state": report["state"],
            "validation_revision": report["validation_revision"],
            "report": str(REPORT_RELATIVE),
            "selected_semantic": report["selected_semantic"],
            "source_arm": "right",
            "crosscheck_arm": "left",
            "fusion": "none",
        }
        system_path.write_text(json.dumps(system, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["state"] == "COMMISSIONED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
