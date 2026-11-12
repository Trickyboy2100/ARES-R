"""Hard level-TCP seed construction for cuRobo trajectory optimization.

This module does not replace cuRobo.  It constructs collision-agnostic IK
seeds on the requested Cartesian orientation manifold; cuRobo still optimizes
the seed in the complete collision world and the independent validators remain
authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from ares_r.motion.tcp_orientation import (level_rotation,
                                           nearest_level_roll_branch,
                                           tcp_yaw_rad)


@dataclass(frozen=True)
class ManifoldSeed:
    joints_rad: np.ndarray
    cartesian_offset_m: tuple[float, float, float]
    start_yaw_rad: float
    goal_yaw_rad: float
    roll_branch: int
    max_joint_step_rad: float


def _shortest_angle_delta(start: float, goal: float) -> float:
    return math.atan2(math.sin(goal - start), math.cos(goal - start))


def _resample(rows: np.ndarray, count: int) -> np.ndarray:
    source = np.linspace(0.0, 1.0, len(rows))
    target = np.linspace(0.0, 1.0, int(count))
    return np.column_stack([np.interp(target, source, rows[:, column])
                            for column in range(rows.shape[1])])


def build_level_manifold_seeds(ik, start_joints, goal_position_m, *,
                               goal_yaw_rad=0.0, horizon=32,
                               sample_count=25, offsets_m=None,
                               max_joint_step_rad=0.22):
    """Return continuous IK seeds that stay level while yaw changes smoothly.

    ``offsets_m`` are generic sinusoidal Cartesian arches.  They are not
    waypoints and are never executed directly; they only offer cuRobo several
    homotopy seeds around singular bands.
    """
    start = np.asarray(start_joints, dtype=float)
    if start.shape != (6,) or not np.isfinite(start).all():
        raise ValueError("finite six-joint start required")
    goal_position = np.asarray(goal_position_m, dtype=float)
    if goal_position.shape != (3,) or not np.isfinite(goal_position).all():
        raise ValueError("finite BODY goal position required")
    if horizon < 3 or sample_count < 3:
        raise ValueError("manifold seed needs at least three samples")
    start_pose = ik.fk(start)
    start_position = start_pose[:3, 3]
    start_yaw = tcp_yaw_rad(start_pose[:3, :3])
    roll_branch = nearest_level_roll_branch(start_pose[:3, :3])
    yaw_delta = _shortest_angle_delta(start_yaw, float(goal_yaw_rad))
    offsets = offsets_m or (
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.04), (0.0, 0.0, 0.08),
        (0.0, 0.05, 0.06), (0.0, -0.05, 0.06),
        (-0.04, 0.0, 0.06), (0.04, 0.0, 0.06),
    )
    answers = []
    for raw_offset in offsets:
        offset = np.asarray(raw_offset, dtype=float)
        q = start.copy(); rows = [q.copy()]
        valid = True
        for fraction in np.linspace(0.0, 1.0, sample_count)[1:]:
            position = ((1.0 - fraction) * start_position + fraction * goal_position +
                        math.sin(math.pi * fraction) * offset)
            yaw = start_yaw + fraction * yaw_delta
            try:
                solved = ik.solve(position, level_rotation(yaw, roll_branch), q)
            except ValueError:
                valid = False
                break
            next_q = np.asarray(solved.joints_rad, dtype=float)
            if float(np.max(np.abs(next_q - q))) > max_joint_step_rad:
                valid = False
                break
            rows.append(next_q); q = next_q
        if not valid:
            continue
        dense = _resample(np.asarray(rows), horizon)
        answers.append(ManifoldSeed(
            joints_rad=dense,
            cartesian_offset_m=tuple(float(value) for value in offset),
            start_yaw_rad=float(start_yaw),
            goal_yaw_rad=float(goal_yaw_rad),
            roll_branch=roll_branch,
            max_joint_step_rad=float(np.max(np.abs(np.diff(dense, axis=0)))),
        ))
    return answers
