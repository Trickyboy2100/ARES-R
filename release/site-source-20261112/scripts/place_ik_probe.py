#!/usr/bin/env python3
"""Soft IK and Cartesian headroom probing for the placement work.

``RuntimeGoalIK.solve`` raises the moment the residual contract is missed, which
is correct for producing a trajectory but useless for *measuring* where a
motion stops being feasible.  These helpers mirror that same residual (and the
same joint bounds) without the raise, so infeasibility becomes a number that can
be recorded in a package instead of a traceback.
"""

import math
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: From ``RuntimeGoalIK.solve``: position <= 1.5 mm and orientation <= 0.6 deg.
POSITION_CONTRACT_M = 0.0015
ORIENTATION_CONTRACT_DEG = math.degrees(0.6)

#: Deterministic seed for the IK branch search, so a plan is reproducible.
#: 1500 trials already surfaces every distinct branch on the recorded placement
#: pose (identical best and count at 800), so the search is not the bottleneck
#: it looks like.
CANDIDATE_SEED = 20260928
CANDIDATE_TRIALS = 1500
DUPLICATE_TOLERANCE_RAD = 0.02


def excursion_deg(start, joints):
    """Worst per-joint travel, in degrees -- the quantity the native cap limits."""
    start = np.asarray(start, dtype=float)
    joints = np.asarray(joints, dtype=float)
    return math.degrees(float(np.max(np.abs(joints - start))))


def joint_excursions_deg(start, joints):
    start = np.asarray(start, dtype=float)
    joints = np.asarray(joints, dtype=float)
    return [math.degrees(float(value)) for value in np.abs(joints - start)]


def goal_candidates(ik, xyz, rotation, seed, *, trials=CANDIDATE_TRIALS,
                    duplicate_rad=DUPLICATE_TOLERANCE_RAD):
    """Distinct IK solutions for one pose, cheapest per-joint travel first.

    Seeding from the current joints is not the same as minimising travel: on the
    2026-09-28 placement pose the seed-following branch needed 169.3 deg of J3
    while a sibling branch needed only 147.5 deg of J2.  The native sender caps
    per-joint travel, so the branch must be chosen, not inherited.
    """
    rng = np.random.default_rng(CANDIDATE_SEED)
    found = []
    for q0 in rng.uniform(ik.lower, ik.upper, size=(trials, 6)):
        try:
            solved = ik.solve(xyz, rotation, q0)
        except Exception:
            continue
        joints = np.asarray(solved.joints_rad, dtype=float)
        if any(np.max(np.abs(joints - other)) < duplicate_rad for other in found):
            continue
        found.append(joints)
    found.sort(key=lambda joints: excursion_deg(seed, joints))
    return found


def soft_solve(ik, rotation, xyz, seed, iterations=200):
    """Least-squares IK without the hard raise.  Returns (joints, pos_err, ori_deg)."""
    xyz = np.asarray(xyz, dtype=float)
    rotation = np.asarray(rotation, dtype=float)
    seed = np.asarray(seed, dtype=float)

    def residual(q):
        pose = ik.fk(q)
        error = Rotation.from_matrix(rotation.T @ pose[:3, :3]).as_rotvec()
        return np.r_[pose[:3, 3] - xyz, 0.18 * error, 0.0005 * (q - seed)]

    answer = least_squares(residual, np.clip(seed, ik.lower + 1e-5, ik.upper - 1e-5),
                           bounds=(ik.lower, ik.upper), max_nfev=iterations)
    pose = ik.fk(answer.x)
    return (answer.x,
            float(np.linalg.norm(pose[:3, 3] - xyz)),
            math.degrees(float(np.linalg.norm(
                Rotation.from_matrix(rotation.T @ pose[:3, :3]).as_rotvec()))))


def contract_met(position_error_m, orientation_error_deg):
    return (position_error_m < POSITION_CONTRACT_M and
            orientation_error_deg < ORIENTATION_CONTRACT_DEG)


def cartesian_headroom(ik, rotation, start_xyz, seed, direction, *, site_limits=None,
                       cap_m=0.20, step_m=0.005):
    """How far ``start_xyz`` can move along ``direction`` before a gate breaks.

    Two gates are checked, because on the placement retreat they bind in
    different places: the IK residual contract, and -- when ``site_limits`` is
    given -- the site soft joint margin.  The vertical retreat is actually
    stopped by J2's soft margin (60 mm), well before the IK contract (90 mm).

    The walk is incremental and re-seeded from the previous solution, so it
    measures the *continuous* travel of one motion, not the reach of an
    unrelated branch.
    """
    vector = np.asarray(direction, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise ValueError("probe direction must be non-zero")
    vector = vector / norm
    if site_limits is not None:
        lower = np.asarray(site_limits["lower_rad"], dtype=float)
        upper = np.asarray(site_limits["upper_rad"], dtype=float)
        margin = float(site_limits["soft_limit_margin_rad"])
    reached, joints = 0.0, np.asarray(seed, dtype=float)
    step = step_m
    while step <= cap_m + 1e-9:
        candidate, position_error, orientation_error = soft_solve(
            ik, rotation, np.asarray(start_xyz, dtype=float) + step * vector, joints)
        if not contract_met(position_error, orientation_error):
            break
        if site_limits is not None:
            slack = np.minimum(np.abs(candidate - lower), np.abs(upper - candidate))
            if float(slack.min()) < margin:
                break
        reached, joints = float(step), candidate
        step = round(step + step_m, 9)
    return reached, joints
