#!/usr/bin/env python3
"""Export live-joint cuRobo collision spheres into BODY, planning-only.

The script consumes saved read-only diagnostics.  It has no robot SDK import
and cannot issue motion.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def transform(xyz, rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    result = np.eye(4)
    result[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                      [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                      [-sp, cp*sr, cp*cr]]
    result[:3, 3] = xyz
    return result


def sphere_surface(center, radius, count=48):
    # Deterministic Fibonacci surface, adequate for registration scoring.
    rows = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for index in range(count):
        z = 1.0 - 2.0 * (index + .5) / count
        radial = math.sqrt(max(0.0, 1.0 - z*z))
        angle = golden * index
        rows.append(center + radius * np.array([radial*math.cos(angle), radial*math.sin(angle), z]))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot-yaml", required=True)
    parser.add_argument("--robot-state", required=True)
    parser.add_argument("--robot-world", required=True)
    parser.add_argument("--controller-model-correction", required=True)
    parser.add_argument("--arm", choices=("left", "right"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    import torch
    import yaml
    from curobo.motion_planner import MotionPlanner, MotionPlannerCfg
    from curobo.types import JointState

    robot_path = Path(args.robot_yaml)
    robot = yaml.safe_load(robot_path.read_text())
    saved = json.loads(Path(args.robot_state).read_text())
    arm_state = saved.get("arms", saved)[args.arm]
    joints = np.asarray(arm_state["joint_position_rad"], dtype=float)
    correction_raw = json.loads(Path(args.controller_model_correction).read_text())
    if correction_raw.get("arm") != args.arm:
        raise RuntimeError("controller/model correction belongs to another arm")
    correction = np.asarray(correction_raw["T_controller_model"], dtype=float)
    world = json.loads(Path(args.robot_world).read_text())
    mount = world["arms"][args.arm]
    body_controller = transform(mount["base_xyz_m"], mount["base_rpy_rad"])
    body_model = body_controller @ correction

    sentinel = {"cuboid": {"remote_sentinel": {"dims": [.01, .01, .01], "pose": [10, 10, 10, 1, 0, 0, 0]}}}
    cfg = MotionPlannerCfg.create(robot=robot, scene_model=sentinel, interpolation_dt=.02,
                                  use_cuda_graph=False, self_collision_check=True,
                                  num_trajopt_seeds=2, num_ik_seeds=4)
    planner = MotionPlanner(cfg)
    names = list(planner.joint_names)
    expected = ["joint%d" % index for index in range(1, 7)]
    state = JointState.from_position(torch.tensor(joints[[expected.index(name) for name in names]][None, :],
                                                   device="cuda:0", dtype=torch.float32), joint_names=names)
    geometry = planner.compute_kinematics(state)
    spheres_model = geometry.robot_spheres.detach().cpu().numpy().reshape(-1, 4)
    spheres_model = spheres_model[spheres_model[:, 3] > 0]
    spheres_body, surface_body = [], []
    for index, sphere in enumerate(spheres_model):
        center = (body_model @ np.r_[sphere[:3], 1.0])[:3]
        radius = float(sphere[3])
        spheres_body.append({"id": "model_sphere_%03d" % index,
                             "center_body_m": center.tolist(), "radius_m": radius})
        surface_body.extend(sphere_surface(center, radius))
    payload = {
        "schema_version": 1, "state": "READ_ONLY_PLANNING_MODEL_GEOMETRY",
        "arm": args.arm, "joint_position_rad": joints.tolist(),
        "joint_source": str(Path(args.robot_state)),
        "robot_yaml": str(robot_path),
        "robot_model_sha256": hashlib.sha256(robot_path.read_bytes() + Path(robot["kinematics"]["urdf_path"]).read_bytes()).hexdigest(),
        "controller_model_correction_source": str(Path(args.controller_model_correction)),
        "T_body_model": body_model.tolist(),
        "sphere_count": len(spheres_body), "surface_point_count": len(surface_body),
        "spheres": spheres_body, "surface_points_body_m": np.asarray(surface_body).tolist(),
        "limitations": ["cuRobo arm collision spheres only", "gripper/tool mesh absent", "link6/tool area must be masked for registration"],
        "execution_allowed": False,
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output": str(output), "sphere_count": len(spheres_body),
                      "surface_point_count": len(surface_body)}))


if __name__ == "__main__":
    main()
