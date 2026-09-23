"""Canonical fresh Pixel Pro + live robot state to planning-scene backend.

This module owns orchestration only.  It accepts no obstacle coordinates,
cluster IDs, prior SceneSnapshot, or historical evidence input.  The camera
and robot-state subprocesses remain isolated in their site Python runtimes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "worklog/evidence/2026-09-23-p3-5-live-scenes"


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_live_planning_scene(config: dict, destination: Path | None = None,
                              active_arm: str = "right") -> dict:
    """Build one immutable scene solely from a fresh scan and current state."""
    if active_arm not in ("left", "right"):
        raise ValueError("active arm must be left or right")
    destination = Path(destination) if destination else EVIDENCE / ("live_scan_" + _stamp())
    if destination.exists():
        raise FileExistsError("live scene output already exists")
    python = Path(config["epic_pointcloud"]["body_cloud_viewer_python"])
    command = [str(python), str(ROOT / "scripts/p32_scan_scene.py"),
               "--mode", "LIVE", "--output", str(destination),
               "--open3d-python", str(python), "--active", active_arm]
    result = subprocess.run(command, cwd=ROOT,
                            env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
                            text=True, capture_output=True, timeout=240, check=False)
    if result.returncode:
        raise RuntimeError("live scene build failed closed: " +
                           (result.stderr or result.stdout)[-1800:])
    summary = json.loads((destination / "fresh_scene_summary.json").read_text())
    report = json.loads((destination / "scene/scene_report.json").read_text())
    compiled = json.loads((destination / "scene/compiled_scene.json").read_text())
    if (summary.get("mode") != "LIVE" or report.get("mode") != "LIVE" or
            summary["snapshot_id"] != report["snapshot_id"] or
            report["snapshot_id"] != compiled["scene_snapshot_id"] or
            summary["pointcloud_sha256"] != report["pointcloud_sha256"]):
        raise RuntimeError("fresh scene provenance mismatch")
    return {
        "scene_dir": str(destination.resolve()),
        "scene_snapshot_id": summary["snapshot_id"],
        "scene_digest": report["compiled_scene_digest"],
        "pointcloud_sha256": summary["pointcloud_sha256"],
        "primitive_count": len(report["objects"]),
        "support_count": len((report.get("support_decomposition") or {}).get("supports", [])),
        "timing_s": summary["timing_s"],
        "total_s": summary["total_s"],
        "valid": True,
        "active_arm": active_arm,
        "runtime_inputs": ["fresh_camera", "current_robot_state",
                           "commissioned_calibration", "generic_scene_parameters"],
    }
