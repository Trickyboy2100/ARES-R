#!/usr/bin/env python3
"""Planning-only A/B and B/A preview on one fresh stationary scene.

Both legs start from hypothetical joints. They are deliberately non-executable:
before any physical leg, capture a new scene and verify the live start again.
No robot, base, gripper, or camera control adapter is imported here.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from ares_r.perception.robot_collision import arm_link_transforms, transform_xyz_rpy


def load(path):
    return json.loads(Path(path).read_text())


def fk_body(joints, audit, model, world, arm):
    arm_world = world["arms"][arm]
    body_model = (transform_xyz_rpy(arm_world["base_xyz_m"], arm_world["base_rpy_rad"])
                  @ np.asarray(audit["T_controller_model"]))
    tool = np.asarray(audit["diagnostics"]["tool_data"]["pose_mm_rad"], dtype=float)
    link_tcp = transform_xyz_rpy(tool[:3] * .001, tool[3:])
    root = Path(model["asset_root"]) / model["urdf"]
    return (body_model @ arm_link_transforms(root, joints)["link6"] @ link_tcp)[:3, 3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_dir", type=Path)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--a-delta-rad", type=float, nargs=6, required=True)
    parser.add_argument("--b-delta-rad", type=float, nargs=6, required=True)
    parser.add_argument("--benchmark-runs", type=int, default=1)
    args = parser.parse_args()
    if args.benchmark_runs < 1 or args.benchmark_runs > 5:
        raise ValueError("benchmark-runs must be 1..5")
    args.output.mkdir(parents=True, exist_ok=False)
    original = load(args.scene_dir / "targets.json")
    report = load(args.scene_dir / "scene_report.json")
    audit = load(args.audit)
    if original["active_arm"] != audit["arm"]:
        raise ValueError("audit and scene arm differ")
    actual = np.asarray(audit["diagnostics"]["joint_position_rad"], dtype=float)
    if np.max(np.abs(actual - np.asarray(original["start_rad"]))) > 1e-4:
        raise ValueError("fresh scene does not match the read-only live audit")
    delta_a = np.asarray(args.a_delta_rad, dtype=float)
    delta_b = np.asarray(args.b_delta_rad, dtype=float)
    if not np.isfinite(delta_a).all() or not np.isfinite(delta_b).all():
        raise ValueError("finite joint deltas required")
    q_a, q_b = actual + delta_a, actual + delta_b
    model = load(REPOSITORY / "config/robot_collision_model.json")
    world = load(REPOSITORY / "config/robot_world.json")
    xyz_a = fk_body(q_a, audit, model, world, audit["arm"])
    xyz_b = fk_body(q_b, audit, model, world, audit["arm"])
    contract = {"schema_version": 1, "contract": "P3_1_OFFLINE_AB_PREVIEW",
                "planning_only": True, "execution_allowed": False,
                "execution_block_reason": "hypothetical starts differ from captured live joints; each physical leg needs fresh scan/state/snapshot",
                "scene_snapshot_id": report["snapshot_id"],
                "captured_live_joints_rad": actual.tolist(),
                "A": {"joints_rad": q_a.tolist(), "body_tcp_xyz_m": xyz_a.tolist()},
                "B": {"joints_rad": q_b.tolist(), "body_tcp_xyz_m": xyz_b.tolist()},
                "endpoint_distance_m": float(np.linalg.norm(xyz_a - xyz_b))}
    (args.output / "ab_contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    for name, start, goal, start_xyz, goal_xyz in (
        ("A_to_B", q_a, q_b, xyz_a, xyz_b),
        ("B_to_A", q_b, q_a, xyz_b, xyz_a),
    ):
        leg = args.output / name
        leg.mkdir()
        for filename in ("compiled_scene.json", "scene_report.json", "clean_residual.npz"):
            (leg / filename).symlink_to((args.scene_dir / filename).resolve())
        targets = {"schema_version": 1, "contract": "P3_1_HYPOTHETICAL_START_PREVIEW",
                   "active_arm": audit["arm"], "planning_only": True,
                   "execution_allowed": False,
                   "captured_live_start_rad": actual.tolist(),
                   "start_rad": start.tolist(), "goal_rad": goal.tolist(),
                   "A": {"frame": "BODY", "xyz_m": start_xyz.tolist()},
                   "B": {"frame": "BODY", "xyz_m": goal_xyz.tolist()}}
        (leg / "targets.json").write_text(json.dumps(targets, indent=2) + "\n")
        command = [sys.executable, str(REPOSITORY / "scripts/run_p3_production_plan.py"),
                   str(leg), "--audit", str(args.audit), "--output", str(leg / "planning.json"),
                   "--benchmark-runs", str(args.benchmark_runs)]
        with (leg / "runner_summary.json").open("w") as stream:
            completed = subprocess.run(command, cwd=REPOSITORY, stdout=stream,
                                       stderr=subprocess.STDOUT, check=False,
                                       env=dict(os.environ, PYTHONPATH=str(REPOSITORY / "src")))
        if not (leg / "planning.json").is_file():
            raise RuntimeError("planner produced no result for %s (exit %d)" %
                               (name, completed.returncode))
        plan = load(leg / "planning.json")
        print(json.dumps({"leg": name, "result": plan["observed_result"],
                          "expectation_met": plan["expectation_met"],
                          "clearance_m": plan["clearance_m"],
                          "planning_s": plan["timing_s"]["planning_samples"]}, indent=2))


if __name__ == "__main__":
    main()
