#!/usr/bin/env python3
"""Steady-state cuRobo benchmark and combined online-chain latency report."""

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np


def summary(values):
    values = np.asarray(values, dtype=float)
    p50 = float(np.percentile(values, 50))
    return {
        "count": len(values), "mean_ms": float(np.mean(values)), "p50_ms": p50,
        "p90_ms": float(np.percentile(values, 90)), "p95_ms": float(np.percentile(values, 95)),
        "max_ms": float(np.max(values)), "hz_from_p50": 1000/p50 if p50 else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--perception", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default="/home/yikun/ares-r-curobo-venv/bin/python")
    parser.add_argument("--runs", type=int, default=12)
    args = parser.parse_args()
    if not 10 <= args.runs <= 20:
        raise ValueError("planning benchmark requires 10-20 measured runs")
    request = json.loads(args.request.read_text())
    request.update(mode="FREE", planning_only=True, execution_allowed=False,
                   planning_scope="DEMO_OFFLINE_ONLY", benchmark_runs=args.runs)
    args.output.mkdir(parents=True, exist_ok=True)
    request_path = args.output / "curobo_benchmark_request.json"
    artifact_path = args.output / "curobo_benchmark_artifact.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/"src"))
    with (args.output/"curobo_benchmark.log").open("w") as log:
        result = subprocess.run([args.python, "-m", "ares_r.motion.pointcloud_demo_worker",
            str(request_path), str(artifact_path)], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode or not artifact_path.is_file():
        raise RuntimeError("cuRobo benchmark failed; inspect %s" % (args.output/"curobo_benchmark.log"))
    artifact = json.loads(artifact_path.read_text())
    measured = artifact["benchmark"]
    perception = json.loads(args.perception.read_text())
    perception_samples = [item["perception_scene_total_ms"] for item in perception["raw_samples_ms"]]
    world = measured["curobo_world_update_ms"]
    collision = measured["collision_query_ms"]
    planning = measured["planning_ms"]
    count = min(len(perception_samples), len(world), len(collision), len(planning))
    full = [perception_samples[index] + world[index] + collision[index] + planning[index] for index in range(count)]
    perception_p95 = perception["timing"]["perception_scene_total_ms"]["p95_ms"]
    recommendations = {
        "STATIC_SNAPSHOT": "SUPPORTED",
        "CHECKPOINT_RESCAN": "SUPPORTED",
        "SCENE_WATCHDOG_1HZ": "NOT_SUSTAINABLE" if perception_p95 > 1000 else "SUPPORTED",
        "SCENE_WATCHDOG_2HZ": "NOT_SUSTAINABLE" if perception_p95 > 500 else "SUPPORTED",
        "SCENE_WATCHDOG_5HZ": "NOT_SUSTAINABLE" if perception_p95 > 200 else "SUPPORTED",
    }
    combined = {
        "schema_version": 1, "mode": "FAST_MEMORY_ONLY_PLUS_STEADY_STATE_CUROBO",
        "execution_allowed": False, "warmup": {"camera_frames": perception["warmup_frames"], "planning_runs": 1},
        "measured": {"camera_frames": perception["measured_frames"], "planning_runs": args.runs},
        "perception": perception["timing"],
        "curobo": {
            "curobo_world_update_ms": summary(world),
            "collision_query_ms": summary(collision),
            "planning_ms": summary(planning),
        },
        "full_plan_total_ms": summary(full),
        "run_mode_recommendations": recommendations,
        "scene_snapshot_id": artifact["scene_snapshot_id"],
        "scene_digest": artifact["scene_digest"],
        "calibration_candidate_revision": artifact["calibration_candidate_revision"],
        "raw_curobo_samples_ms": measured,
    }
    (args.output/"latency_benchmark.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(json.dumps({"planning": combined["curobo"]["planning_ms"],
        "full": combined["full_plan_total_ms"], "recommendations": recommendations}, indent=2))


if __name__ == "__main__":
    main()
