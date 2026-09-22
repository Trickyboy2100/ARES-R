#!/usr/bin/env python3
"""P3.2 cuRobo-only planning on an already frozen fresh BODY scene.

No robot/base/gripper movement adapters are imported.  Cartesian samples are
used solely to classify the swept straight reference corridor, never as a
trajectory.  The actual point-to-point trajectory always comes from cuRobo.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.cli import load_config
from ares_r.motion.curobo import CUROBO_COMMIT
from ares_r.motion.curobo_params import planning_profile
from ares_r.motion.se3 import pose_mm_rad_to_matrix
from search_p32_ab import build_solver


def load(path):
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scene_dir", type=Path)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--search", type=Path, required=True)
    p.add_argument("--candidate", type=int, default=0)
    p.add_argument("--direction", choices=("A_to_B", "B_to_A", "CURRENT_to_A"), required=True)
    p.add_argument("--policy", choices=("DIRECT", "BLOCK"), required=True)
    p.add_argument("--collision-activation-distance-m", type=float,
                   help="planning-only cuRobo optimizer obstacle activation distance")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("refusing to overwrite planning artifact")
    a.output.mkdir(parents=True)
    config = load_config(str(ROOT / "config/system.json"))
    scene = load(a.scene_dir / "compiled_scene.json")
    report = load(a.scene_dir / "scene_report.json")
    audit = load(a.audit)
    candidate = load(a.search)["candidates"][a.candidate]
    source, destination = (("A", "B") if a.direction == "A_to_B" else
                           ("B", "A") if a.direction == "B_to_A" else ("CURRENT", "A"))
    goal = candidate[destination+"_joints_rad"]
    start = (audit["diagnostics"]["joint_position_rad"] if source == "CURRENT" else
             candidate[source+"_joints_rad"])
    goal_xyz = candidate[destination+"_xyz_m"]
    tool = audit["diagnostics"]["tool_data"]["pose_mm_rad"]
    solver = build_solver(audit, load(ROOT / "config/robot_collision_model.json"),
                          load(ROOT / "config/robot_world.json"))
    start_xyz = (solver.fk(start)[:3, 3].tolist() if source == "CURRENT" else
                 candidate[source+"_xyz_m"])
    orientation = np.asarray(candidate["orientation_matrix"])
    if source == "CURRENT" and a.policy != "DIRECT":
        raise ValueError("current-to-A reposition must be a direct cuRobo request")
    ab = None
    if source != "CURRENT" and a.policy != "BLOCK":
        reference, errors = solver.straight(start_xyz, goal_xyz, orientation, start, samples=61)
        if float(np.max(np.abs(reference[-1]-goal))) > .12:
            raise ValueError("reference IK branch differs from goal")
        ab = {"motion_policy": "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG",
              "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
              "reference_chord_joints_rad": reference.tolist(),
              "reference_ik_errors": errors,
              "planner_mode": "CUROBO_DIRECT", "explicit_waypoints": []}
    parameters = planning_profile(config)
    if a.collision_activation_distance_m is not None:
        if not .005 <= a.collision_activation_distance_m <= .08:
            raise ValueError("activation distance must be between 5 and 80 mm")
        parameters["optimizer_collision_activation_distance"] = a.collision_activation_distance_m
    request = {"schema_version": 2, "planning_only": True, "execution_allowed": False,
        "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
        "mode": report["mode"], "compiled_scene": scene,
        "scene_snapshot_id": scene["scene_snapshot_id"], "scene_digest": scene["digest"],
        "start_rad": start, "goal_rad": goal, "active_arm": "right",
        "T_body_model": report["T_body_model"],
        "T_link6_tcp": pose_mm_rad_to_matrix(tool),
        "geometry_revision": report["geometry_revision"],
        "inactive_arm_revision": report["inactive_arm_revision"],
        "collision_model": load(config["robot_collision"]["model"]),
        "robot_yaml": config["curobo"]["robot_yaml"], "expected_commit": CUROBO_COMMIT,
        "planning_parameters": parameters, "benchmark_runs": 1,
        "ab_demo": ab}
    (a.output / "planner_request.json").write_text(json.dumps(request, indent=2)+"\n")
    metadata = {"P31_PUSHED_AND_ALIGNED": True,
        "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
        "READY_FOR_FIRST_SUPERVISED_CLEAR_EXECUTION": "NO",
        "execution_allowed": False, "source_scene": str(a.scene_dir.resolve()),
        "snapshot_id": scene["scene_snapshot_id"], "direction": a.direction,
        "policy": a.policy, "start_endpoint": source, "goal_endpoint": destination,
        "start_body_xyz_m": start_xyz, "goal_body_xyz_m": goal_xyz,
        "candidate_index": a.candidate, "reference_corridor_only": True,
        "optimizer_collision_activation_distance_m": parameters["optimizer_collision_activation_distance"],
        "ab_contract": candidate, "explicit_waypoints": []}
    (a.output / "ab_plan_contract.json").write_text(json.dumps(metadata, indent=2)+"\n")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    with (a.output / "planner.log").open("w") as stream:
        completed = subprocess.run([config["curobo"]["python"], "-m",
            "ares_r.motion.production_scene_worker", str(a.output/"planner_request.json"),
            str(a.output/"planning.json")], cwd=ROOT, env=env,
            stdout=stream, stderr=subprocess.STDOUT,
            timeout=float(config["curobo"]["timeout_s"]), check=False)
    if completed.returncode or not (a.output/"planning.json").exists():
        raise RuntimeError(f"planning contract failed; inspect {a.output/'planner.log'}")
    result = load(a.output/"planning.json")
    print(json.dumps({"direction": a.direction, "policy": a.policy,
        "classification": result.get("ab_demo", {}).get("corridor", {}).get("classification"),
        "result": result["observed_result"], "clearance": result["clearance_m"],
        "arc_m": result.get("ab_demo", {}).get("arc_height_above_endpoints_m"),
        "planning_s": result["timing_s"]["planning_samples"]}, indent=2))


if __name__ == "__main__":
    main()
