#!/usr/bin/env python3
"""Offline fixed-orientation A/B search; never communicates with hardware."""

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ares_r.motion.ab_cartesian import CartesianIK
from ares_r.perception.robot_collision import transform_xyz_rpy


def load(path):
    return json.loads(Path(path).read_text())


def build_solver(audit, model, world):
    arm = world["arms"]["right"]
    body_model = transform_xyz_rpy(arm["base_xyz_m"], arm["base_rpy_rad"]) @ np.asarray(audit["T_controller_model"])
    tool = np.asarray(audit["diagnostics"]["tool_data"]["pose_mm_rad"], dtype=float)
    link6_tcp = transform_xyz_rpy(tool[:3]*.001, tool[3:])
    return CartesianIK(Path(model["asset_root"]) / model["urdf"], body_model, link6_tcp)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    audit = load(a.audit)
    solver = build_solver(audit, load(ROOT / "config/robot_collision_model.json"),
                          load(ROOT / "config/robot_world.json"))
    q0 = np.asarray(audit["diagnostics"]["joint_position_rad"])
    rng = np.random.default_rng(9)
    results = []
    started = time.perf_counter()
    for x in (.68, .71, .74):
        for z in (.97, 1.00, 1.03):
            for left_y, right_y in ((-.10, -.55), (-.13, -.60), (-.13, -.55)):
                A, B = np.array([x, right_y, z]), np.array([x, left_y, z])
                for trial in range(15):
                    seed = np.clip(q0 + rng.normal(0, [.8, .6, .6, .8, .5, .8]),
                                   solver.lower + .1, solver.upper - .1)
                    objective = lambda q: np.r_[solver.fk(q)[:3, 3] - A, .002*(q-seed)]
                    initial = least_squares(objective, seed,
                                            bounds=(solver.lower, solver.upper), max_nfev=70)
                    if np.linalg.norm(solver.fk(initial.x)[:3, 3] - A) > .002:
                        continue
                    orientation = solver.fk(initial.x)[:3, :3]
                    try:
                        qa = solver.solve(A, orientation, initial.x).joints_rad
                        qb = solver.solve(B, orientation, qa).joints_rad
                        # A reference Cartesian chord may be classified, but is
                        # never used as a motion trajectory. cuRobo plans both legs.
                        chord, errors = solver.straight(A, B, orientation, qa, samples=41)
                    except ValueError:
                        continue
                    if np.max(np.abs(chord[-1] - qb)) > .12:
                        continue
                    margin = float(np.min(np.minimum(chord-solver.lower,
                                                      solver.upper-chord)))
                    if margin < .15:
                        continue
                    rank = float(abs(left_y-right_y) + .05*margin - .02*abs(z-.99))
                    results.append({"A_xyz_m": A.tolist(), "B_xyz_m": B.tolist(),
                                    "A_joints_rad": chord[0].tolist(),
                                    "B_joints_rad": chord[-1].tolist(),
                                    "orientation_matrix": orientation.tolist(),
                                    "span_m": float(abs(left_y-right_y)),
                                    "height_m": z, "joint_limit_margin_rad": margin,
                                    "rank": rank, "reference_chord_ik_errors": errors,
                                    "source_trial": trial})
    results.sort(key=lambda row: row["rank"], reverse=True)
    payload = {"planning_only": True, "execution_allowed": False,
               "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
               "motion_planner_policy": "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG",
               "source_audit": str(Path(a.audit).resolve()), "searched_s": time.perf_counter()-started,
               "valid_kinematic_pairs": len(results), "candidates": results[:30]}
    Path(a.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"searched_s": payload["searched_s"], "valid_pairs": len(results),
                      "best": results[:3]}, indent=2))


if __name__ == "__main__":
    main()
