#!/usr/bin/env python3
"""Reproduce the P3.8E timing summary from frozen, non-motion evidence."""

import argparse
import json
import math
from pathlib import Path
import statistics


PICK = Path("worklog/evidence/2026-09-24-p3-8b1a/live_pick_authorized_20260924T175237")
P34 = Path("worklog/evidence/2026-09-23-p3-4")
PLACE = Path("worklog/evidence/2026-09-28-place")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def percentile(values, fraction):
    values = sorted(values)
    return values[int(fraction * (len(values) - 1))]


def motion(root, name):
    rows = jsonl(root / "execution" / (name + ".jsonl"))
    stamps = [row["wall_unix_ns"] / 1e9 for row in rows if "wall_unix_ns" in row]
    errors = [row["tracking_error_deg"] for row in rows if "tracking_error_deg" in row]
    return {
        "start_unix": min(stamps),
        "end_unix": max(stamps),
        "wall_s": max(stamps) - min(stamps),
        "tracking_max_deg": max(errors),
        "tracking_p95_deg": percentile(errors, .95),
        "tracking_rms_deg": math.sqrt(sum(value * value for value in errors) / len(errors)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repo.resolve()
    pick = root / PICK
    observation = load(pick / "manipulation_observation.json")
    motions = {name: motion(pick, name) for name in ("pregrasp", "contact", "lift")}
    epoch_durations = []
    for path in sorted((root / "worklog/evidence/2026-09-24-p3-8b").glob(
            "*epoch*/manipulation_observation.json")):
        row = load(path)
        epoch_durations.append(row["completed_at_unix"] - row["captured_at_unix"])
    base_durations = []
    for path in sorted((root / PLACE).glob("*/place_base_move_completion.json")):
        base_durations.append(load(path)["elapsed_s"])
    p34 = load(root / P34 / "summary.json")
    first = observation["captured_at_unix"]
    last = load(pick / "execution/final_hold_snapshot.jsonl") if False else motions["lift"]["end_unix"]
    motion_total = sum(row["wall_s"] for row in motions.values())
    execution_span = motions["lift"]["end_unix"] - (pick / "native/native_manifest.json").stat().st_mtime
    prepare_span = (pick / "native/native_manifest.json").stat().st_mtime - first
    report = {
        "schema_version": 1,
        "mode": "FROZEN_ARTIFACT_REPLAY_NO_HARDWARE",
        "sources": {"pick": str(PICK), "planner": str(P34), "place": str(PLACE)},
        "successful_pick": {
            "observation_s": observation["completed_at_unix"] - first,
            "observation_to_planner_request_s": (pick / "fresh_pregrasp_plan/planner_request.json").stat().st_mtime - observation["completed_at_unix"],
            "planner_request_to_result_s": (pick / "fresh_pregrasp_plan/planning.json").stat().st_mtime - (pick / "fresh_pregrasp_plan/planner_request.json").stat().st_mtime,
            "planning_to_package_s": (pick / "fresh_first_pick_package/first_pick_execution_package.json").stat().st_mtime - (pick / "fresh_pregrasp_plan/planning.json").stat().st_mtime,
            "package_to_native_ready_s": (pick / "native/native_manifest.json").stat().st_mtime - (pick / "fresh_first_pick_package/first_pick_execution_package.json").stat().st_mtime,
            "prepare_span_s": prepare_span,
            "execution_span_native_ready_to_hold_s": execution_span,
            "observation_to_hold_s": last - first,
            "motion_total_s": motion_total,
            "non_motion_inside_execution_span_s": execution_span - motion_total,
            "motions": motions,
        },
        "observation_epochs": {
            "samples": len(epoch_durations),
            "durations_s": epoch_durations,
            "p50_s": statistics.median(epoch_durations),
            "min_s": min(epoch_durations),
            "max_s": max(epoch_durations),
        },
        "base_completion": {
            "samples": len(base_durations),
            "durations_s": base_durations,
            "p50_s": statistics.median(base_durations),
        },
        "p34_replay": p34,
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
