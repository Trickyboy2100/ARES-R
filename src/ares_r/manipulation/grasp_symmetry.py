"""Discrete grasp symmetries for two-finger tooling.

The two candidates differ by 180 degrees about the tool approach axis.  They
describe the same object pose and insertion direction but can live on very
different wrist/IK branches.  A branch is selected before contact and remains
bound to the attached-object task; this module never flips an already-held
object in place.
"""

from __future__ import annotations

import numpy as np


ROLL_ABOUT_APPROACH_180 = np.diag([-1.0, -1.0, 1.0])


def two_finger_grasp_rotations(rotation):
    rotation = np.asarray(rotation, dtype=float)
    if (rotation.shape != (3, 3) or not np.isfinite(rotation).all() or
            not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) or
            not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-5)):
        raise ValueError("proper 3x3 grasp rotation required")
    return (
        ("EPIC_AS_REPORTED", rotation.copy()),
        ("TWO_FINGER_ROLL_180", rotation @ ROLL_ABOUT_APPROACH_180),
    )
