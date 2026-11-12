#!/usr/bin/env python3
"""Build the three cuRobo requests for horizontal held-object placement.

The generated legs are semantic task legs, never a workaround for joint
excursion limits: level-yaw alignment at the current center, one direct cuRobo
move to 150 mm behind preplace, then one direct cuRobo move to preplace.
"""

import argparse
import copy
import json
from pathlib import Path

from ares_r.motion.tcp_orientation import level_rotation, nearest_level_roll_branch


def request_for(base, start, goal_position, *, align=False, roll_branch=0):
    value = copy.deepcopy(base)
    value["start_rad"] = [float(x) for x in start]
    value["benchmark_runs"] = 1
    value["warmup_policy"] = "ONCE_PER_RUNTIME"
    value["hard_level_manifold"] = {
        "schema_version": 1,
        "goal_position_m": [float(x) for x in goal_position],
        "goal_yaw_rad": 0.0,
        "ik_samples": 31,
        "max_ik_step_rad": 0.22,
        "seed_offsets_m": [[0, 0, 0], [0, 0, .04], [0, 0, .08],
                            [0, .05, .06], [0, -.05, .06],
                            [-.04, 0, .06], [.04, 0, .06]],
    }
    rotation = level_rotation(0.0, roll_branch).tolist()
    if align:
        value["orientation_lock"] = {
            "policy": "LEVEL_YAW_TARGET_V1", "criteria_rpy": [1., 0., 1.],
            "weight_scale": 200., "max_error_deg": 3.5,
            "target_R_body_tcp": rotation, "final_yaw_target_rad": 0.0,
            "non_terminal_orientation_cost": True,
        }
    else:
        value["orientation_lock"] = {
            "policy": "FIXED_ROTATION_V1", "criteria_rpy": [1., 1., 1.],
            "weight_scale": 200., "max_error_deg": 3.5,
            "target_R_body_tcp": rotation,
            "non_terminal_orientation_cost": True,
        }
    value["motion_contract"] = "CUROBO_HORIZONTAL_HELD_OBJECT_PLACE_V1"
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_request")
    parser.add_argument("output_dir")
    parser.add_argument("--preplace", nargs=3, type=float, required=True)
    args = parser.parse_args()
    base = json.loads(Path(args.base_request).read_text())
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    start = base["start_rad"]
    # The caller must replace the next leg's start with the selected previous
    # goal after planning; this prevents guessed or stale state chaining.
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    ik = RuntimeGoalIK(base["robot_yaml_urdf"], base["T_body_model"], base["T_link6_tcp"])
    current_xyz = ik.fk(start)[:3, 3].tolist()
    roll_branch = nearest_level_roll_branch(ik.fk(start)[:3, :3])
    preplace = list(args.preplace)
    rear = [preplace[0] - .15, preplace[1], preplace[2]]
    rows = {
        "00_center_to_rear_unconstrained_probe.json": dict(
            request_for(base, start, rear), orientation_lock=None,
            hard_level_manifold=None),
        "01_center_align_request.json": request_for(base, start, current_xyz, align=True,
                                                     roll_branch=roll_branch),
        "02_center_to_rear_template.json": request_for(base, start, rear,
                                                        roll_branch=roll_branch),
        "03_rear_to_preplace_template.json": request_for(base, start, preplace,
                                                          roll_branch=roll_branch),
    }
    for name, value in rows.items():
        (output / name).write_text(json.dumps(value, indent=2) + "\n")
    (output / "flow.json").write_text(json.dumps({
        "schema_version": 1,
        "flow": ["CENTER_ALIGN_LEVEL_FORWARD", "CUROBO_CENTER_TO_REAR_PREPLACE",
                 "CUROBO_REAR_PREPLACE_TO_PREPLACE"],
        "rear_offset_body_m": [-.15, 0., 0.],
        "single_joint_excursion_cap": None,
        "segmentation_for_excursion_cap": False,
        "templates_require_previous_selected_goal_binding": True,
        "level_roll_branch": roll_branch,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
