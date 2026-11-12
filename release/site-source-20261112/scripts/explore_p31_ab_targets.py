#!/usr/bin/env python3
"""Read-only FK survey for choosing a fresh BODY A/B planning experiment."""

import argparse
import itertools
import json
from pathlib import Path
import sys

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from ares_r.perception.robot_collision import arm_link_transforms, transform_xyz_rpy


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("config/robot_collision_model.json"))
    parser.add_argument("--world", type=Path, default=Path("config/robot_world.json"))
    parser.add_argument("--arm", choices=("left", "right"), default="right")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit, model, world = load(args.audit), load(args.model), load(args.world)
    joints = np.asarray(audit["diagnostics"]["joint_position_rad"], dtype=float)
    arm = world["arms"][args.arm]
    body_model = (transform_xyz_rpy(arm["base_xyz_m"], arm["base_rpy_rad"])
                  @ np.asarray(audit["T_controller_model"]))
    tool = np.asarray(audit["diagnostics"]["tool_data"]["pose_mm_rad"], dtype=float)
    link_tcp = transform_xyz_rpy(tool[:3] * .001, tool[3:])
    urdf = Path(model["asset_root"]) / model["urdf"]
    candidates = []
    steps = np.linspace(-.8, .8, 9)
    for d1, d2, d3 in itertools.product(steps, repeat=3):
        delta = np.asarray([d1, d2, d3, 0, 0, 0])
        q = joints + delta
        frame = body_model @ arm_link_transforms(urdf, q)["link6"] @ link_tcp
        xyz = frame[:3, 3]
        candidates.append({"delta_rad": delta.tolist(), "joints_rad": q.tolist(),
                           "tcp_body_m": xyz.tolist(),
                           "orientation_body_matrix": frame[:3, :3].tolist()})
    data = {"schema_version": 1, "planning_only": True, "execution_allowed": False,
            "arm": args.arm, "start_joints_rad": joints.tolist(),
            "source_audit": str(args.audit.resolve()), "candidates": candidates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for target in ((.72, -.38, 1.10), (.72, -.12, 1.10)):
        ranked = sorted(candidates, key=lambda value: (
            np.linalg.norm(np.asarray(value["tcp_body_m"]) - target)
            + .08 * np.linalg.norm(value["delta_rad"])))[:8]
        print(json.dumps({"target_body_m": target,
                          "closest": [{"tcp_body_m": value["tcp_body_m"],
                                       "delta_rad": value["delta_rad"]}
                                      for value in ranked]}, indent=2))


if __name__ == "__main__":
    main()
