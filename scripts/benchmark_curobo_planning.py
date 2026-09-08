#!/usr/bin/env python3
"""Replay one saved planning request without importing or calling a robot SDK."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ares_r.motion.curobo_params import planning_profile
from ares_r.timing import run_logged_process, timestamp


PROFILES = {
    "current": {},
    "seeds4": {"num_ik_seeds": 4, "num_trajopt_seeds": 4},
    "cuda-graph": {"use_cuda_graph": True},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="current")
    parser.add_argument("--output-root", type=Path, default=Path("logs/curobo_benchmark"))
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    config = {"curobo": {"planning": PROFILES[args.profile]}}
    request.update(planning_only=True, simulation_only=True,
                   run_id="benchmark-%s-%s" % (args.profile, uuid.uuid4().hex[:8]),
                   request_timestamp=timestamp(), planning_parameters=planning_profile(config))
    output_dir = args.output_root / (time.strftime("%Y%m%d_%H%M%S_") + args.profile)
    output_dir.mkdir(parents=True, exist_ok=False)
    request_path = output_dir / "request.json"
    output_path = output_dir / "trajectory.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    returncode, wall_s = run_logged_process(
        [sys.executable, "-m", "ares_r.motion.obstacle_demo_worker",
         str(request_path), str(output_path)], env, output_dir / "planner.log", 300, "cuRobo")
    summary = {"profile": args.profile, "returncode": returncode,
               "wall_s": wall_s, "output": str(output_path)}
    if output_path.is_file():
        result = json.loads(output_path.read_text(encoding="utf-8"))
        plan_events = [e for e in result["timing"]["worker"] if e["phase"] == "plan_cspace"
                       and e["status"] == "completed"]
        summary.update(success=True, plan_events=plan_events,
                       worker_elapsed_ms=result["timing"]["completed"]["elapsed_ms"])
    else:
        summary["success"] = False
    print(json.dumps(summary, indent=2))
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
