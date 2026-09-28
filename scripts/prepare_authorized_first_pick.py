#!/usr/bin/env python3
"""Prepare a fresh, observation-bound first-pick request and contact package.

This helper is deliberately hardware-free.  It derives all targets from one
committed manipulation observation and leaves actual sending to the audited
supervised executor.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ares_r.motion.grasp import approach_direction, rotation_matrix
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.execution_tool_envelope import build_execution_tool_envelope


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=Path, required=True)
    parser.add_argument("--template-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    observation = load(args.epoch / "manipulation_observation.json")
    if observation["transaction_state"] != "COMMITTED":
        raise RuntimeError("fresh committed manipulation observation required")
    report = load(args.epoch / "live_scene/scene/scene_report.json")
    compiled = load(args.epoch / "live_scene/scene/compiled_scene.json")
    request = load(args.template_plan / "planner_request.json")

    target = observation["target"]
    xyz = np.asarray(target["pose_m_rad"][:3], dtype=float)
    rotation = np.asarray(rotation_matrix(*target["pose_m_rad"][3:],
                                          target["orientation_convention"]), dtype=float)
    direction = np.asarray(approach_direction(rotation, target["approach_axis"]), dtype=float)
    pregrasp_xyz = xyz - 0.05 * direction
    start = observation["robot_state_after"]["right"]["diagnostics"]["joint_position_rad"]
    solver = RuntimeGoalIK(request["robot_yaml_urdf"], request["T_body_model"],
                           request["T_link6_tcp"])
    # The live current joints are far from the grasp branch.  Seed IK from the
    # last independently validated pregrasp solution; this is only a numerical
    # seed and all target/provenance fields still come from the fresh epoch.
    goal = solver.solve(pregrasp_xyz, rotation, request["goal_rad"])

    request.update({
        "compiled_scene": compiled,
        "scene_snapshot_id": observation["scene_snapshot_id"],
        "scene_digest": observation["scene_digest"],
        "start_rad": list(map(float, start)),
        "goal_rad": list(goal.joints_rad),
        "goal_candidates_rad": [list(goal.joints_rad)],
        "goal_candidate_metadata": None,
        "geometry_revision": report["geometry_revision"],
        "inactive_arm_revision": report["inactive_arm_revision"],
        "physical_state": "LIVE_AUTHORIZED_FIRST_PICK",
        "runtime_motion_goal": None,
    })
    request["execution_tool_envelope"] = build_execution_tool_envelope(
        request["collision_model"], request["controller_tool_pose_mm_rad"],
        inflation_m=0.008, max_opening_percent=40)
    # Fresh scene owns these values; do not retain stale template provenance.
    request["compiled_scene"]["scene_snapshot_id"] = observation["scene_snapshot_id"]
    request["compiled_scene"]["planning_context_digest"] = observation["scene_digest"]
    (args.output / "planner_request.json").write_text(json.dumps(request, indent=2) + "\n")
    summary = {
        "observation_id": observation["observation_id"],
        "scene_snapshot_id": observation["scene_snapshot_id"],
        "target_body_m": xyz.tolist(), "approach_direction_body": direction.tolist(),
        "pregrasp_body_m": pregrasp_xyz.tolist(), "start_rad": start,
        "goal_rad": list(goal.joints_rad), "ik_position_error_m": goal.position_error_m,
        "ik_orientation_error_deg": float(np.degrees(goal.orientation_error_rad)),
    }
    (args.output / "preparation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
