#!/usr/bin/env python3
"""Hash-bound real-request benchmark. Defaults to verification, never hardware."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(manifest):
    cases = manifest.get("cases", [])
    if not cases:
        raise ValueError("NO_REAL_FROZEN_REQUESTS: collect missing site artifacts first")
    result = []
    for case in cases:
        if not case.get("name") or case.get("expected") not in ("SUCCESS", "FAILURE"):
            raise ValueError("case name and explicit expected result required")
        source = Path(case["request"])
        if sha(source) != case["sha256"]:
            raise ValueError("request hash mismatch: " + str(source))
        request = json.loads(source.read_text())
        if request.get("planning_only") is not True or request.get("execution_allowed") is not False:
            raise ValueError("explicit offline request required")
        dependencies = case.get("dependencies", [])
        if not dependencies:
            raise ValueError("hash-bound model/scene dependencies required")
        bound = {}
        for item in dependencies:
            path = Path(item["path"]).resolve()
            if sha(path) != item["sha256"]:
                raise ValueError("dependency hash mismatch: " + str(path))
            bound[str(path)] = item["sha256"]
        for key in ("robot_yaml", "robot_yaml_urdf"):
            if str(Path(request[key]).resolve()) not in bound:
                raise ValueError("unbound model: " + key)
        result.append((case, request))
    return result


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--warm-runs", type=int, default=20)
    parser.add_argument("--profiles", nargs="+", choices=("FAST25", "FAST50", "QUALITY"),
                        default=["FAST25", "FAST50"])
    args = parser.parse_args()
    cases = verify(json.loads(args.manifest.read_text()))
    if not args.gpu:
        print(json.dumps({"verified_cases": len(cases), "gpu_run": False, "motion": False}))
        return
    if os.environ.get("ARES_R_OFFLINE_REPLAY") != "1":
        raise RuntimeError("run through scripts/offline_sandbox.sh --gpu")
    if args.output is None or not 3 <= args.warm_runs <= 30:
        raise ValueError("unique --output and 3..30 warm runs required")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("real CUDA required; no mock fallback")
    from ares_r.motion.persistent_planner_service import PlannerSupervisor
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"motion": False, "source_manifest_sha256": sha(args.manifest),
              "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
              "cuda": torch.version.cuda, "cases": []}
    for case, source in cases:
        for profile in args.profiles:
            supervisor = PlannerSupervisor()
            rows = []
            try:
                for repeat in range(args.warm_runs + 1):
                    request = copy.deepcopy(source)
                    request.update(warmup_policy="NONE", benchmark_runs=1)
                    if profile != "QUALITY":
                        request["planning_parameters"].update(num_trajopt_seeds=2, num_ik_seeds=4, use_cuda_graph=True)
                        request["solver_policy"] = dict(mode="FAST_SINGLE_PASS_V1",
                            initial_iters=25 if profile == "FAST25" else 50,
                            max_goal_candidates=1, distance_backend="NATIVE_CPU_V1")
                    else:
                        request.pop("solver_policy", None)
                        quality = json.loads((ROOT / "config/system.json").read_text())["curobo"]["planning"]
                        request["planning_parameters"].update(quality)
                    # Geometry, scene, orientation and start/goal are never changed.
                    uid = uuid.uuid4().hex
                    path = args.output / (uid + ".request.json")
                    path.write_text(json.dumps(request))
                    output = args.output / (uid + ".result.json")
                    budget = 240 if repeat == 0 or profile == "QUALITY" else 15
                    at = time.monotonic()
                    response = supervisor.plan(dict(job_id=uid, request=str(path),
                        output=str(output), log=str(args.output / (uid + ".log")),
                        deadline_monotonic=at + budget))
                    artifact = json.loads(output.read_text()) if output.exists() else {}
                    row = dict(repeat=repeat, wall_s=time.monotonic()-at, budget_s=budget,
                        observed=artifact.get("observed_result"), response=response,
                        timing_s=artifact.get("timing_s"), planner_job=artifact.get("planner_job"),
                        sphere_count=artifact.get("active_collision_sphere_count"),
                        obstacle_count=len(request["compiled_scene"]["cuboids"]),
                        independent_validation=artifact.get("independent_dense_validation"),
                        orientation_validation=artifact.get("orientation_validation"),
                        effective_solver_config=artifact.get("effective_solver_config"),
                        trajectory_hash=hashlib.sha256(json.dumps(artifact.get("trajectory_points_rad")).encode()).hexdigest(),
                        request_file=path.name, result_file=output.name if output.exists() else None)
                    rows.append(row)
                    # An actual recycled worker is not a warm sample, even after repeat0.
                    row["warm"] = bool((row["planner_job"] or {}).get("runtime_cache_hit"))
                    report["latest"] = dict(case=case["name"], profile=profile, runs=rows)
                    (args.output / "report.json").write_text(json.dumps(report, indent=2))
            finally:
                supervisor.reap()
            warm = [r["wall_s"] for r in rows if r["warm"]]
            report["cases"].append(dict(name=case["name"], profile=profile, runs=rows,
                expected=case["expected"], expected_rate=sum(r["observed"] == case["expected"] for r in rows)/len(rows),
                warm_p50_s=statistics.median(warm) if warm else None, warm_p95_s=percentile(warm,.95)))
            report.pop("latest", None)
            (args.output / "report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
