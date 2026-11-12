#!/usr/bin/env python3
"""P3.3 repeatable, planning-only frozen-scene cuRobo profile sweep.

Each child process is a new cuRobo planning call with the same pinned scene,
start/goal and conservative tool envelope. No hardware movement API is used.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion.execution_candidate import trial_summary, select_reproducible_candidate

EVIDENCE = ROOT / "worklog/evidence/2026-09-22-p3-2-ab-demo"
SEARCH = ROOT / "worklog/evidence/2026-09-21-p3-2-ab-demo/search_v2.json"
CASES = {
    "avoid_a_to_b": ("avoid_leg_a_to_b", "scene_v2", "A_to_B"),
    "avoid_b_to_a": ("avoid_leg_b_to_a", "scene", "B_to_A"),
    "clear_a_to_b": ("clear_leg_a_to_b", "scene", "A_to_B"),
    "clear_b_to_a": ("clear_leg_b_to_a", "scene", "B_to_A"),
    "current_to_a": ("clear_leg_a_to_b", "scene", "CURRENT_to_A"),
}
ACTIVATION_MM = (10, 20, 30, 40)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=sorted(CASES), default=list(CASES))
    parser.add_argument("--profiles-mm", nargs="+", type=int, default=list(ACTIVATION_MM))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.repeats < 3 or any(mm not in ACTIVATION_MM for mm in args.profiles_mm):
        raise ValueError("P3.3 requires >=3 repeats and audited activation profiles")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "planning_only": True, "execution_allowed": False,
                "curobo_only": True, "explicit_waypoints": [],
                "conservative_tool_envelope": True, "cases": args.cases,
                "profiles_mm": args.profiles_mm, "repeats": args.repeats,
                "started_at_unix": time.time(), "trials": [], "groups": {}}
    summary_path = args.output / "sweep_summary.json"
    for case in args.cases:
        source_dir, scene_name, direction = CASES[case]
        base = EVIDENCE / source_dir
        for millimetres in args.profiles_mm:
            group = "%s/activation_%02dmm" % (case, millimetres)
            rows = []
            for repeat in range(args.repeats):
                output = args.output / group / ("repeat_%02d" % (repeat + 1))
                if output.exists():
                    raise FileExistsError("refusing to reuse an earlier trial: %s" % output)
                command = [sys.executable, str(ROOT / "scripts/run_p32_ab_plan.py"),
                    str(base / scene_name), "--audit", str(base / "right_fk_audit.json"),
                    "--search", str(SEARCH), "--candidate", "1", "--direction", direction,
                    "--policy", "DIRECT", "--execution-tool-envelope",
                    "--collision-activation-distance-m", str(millimetres / 1000),
                    "--output", str(output)]
                print("P33_SWEEP_START", group, repeat + 1, flush=True)
                started = time.monotonic()
                completed = subprocess.run(command, cwd=ROOT, text=True,
                                           capture_output=True, check=False)
                elapsed = time.monotonic() - started
                plan_file = output / "planning.json"
                plan = json.loads(plan_file.read_text()) if plan_file.exists() else None
                request_file = output / "planner_request.json"
                request = json.loads(request_file.read_text()) if request_file.exists() else None
                envelope_revision = ((request or {}).get("execution_tool_envelope") or {}).get("revision")
                row = (trial_summary(plan, expected_envelope_revision=envelope_revision)
                       if plan and envelope_revision else {
                           "trajectory_hash": None, "accepted": False,
                           "rejections": ["PLANNER_FAILED_BEFORE_ARTIFACT"]})
                row.update({"case": case, "activation_mm": millimetres,
                            "repeat": repeat + 1, "process_returncode": completed.returncode,
                            "wall_elapsed_s": elapsed, "artifact": str(output.relative_to(ROOT))})
                (output / "sweep_stdout.txt").write_text(completed.stdout)
                (output / "sweep_stderr.txt").write_text(completed.stderr)
                rows.append(row)
                manifest["trials"].append(row)
                manifest["groups"][group] = {
                    "profile_reproducible": select_reproducible_candidate(rows) is not None,
                    "completed_repeats": len(rows)}
                summary_path.write_text(json.dumps(manifest, indent=2) + "\n")
                print("P33_SWEEP_RESULT", group, repeat + 1,
                      "accepted", row["accepted"], "gap", row.get("independent_clearance_m"),
                      "returncode", completed.returncode, flush=True)
    manifest["completed_at_unix"] = time.time()
    summary_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
