"""Small, dependency-free SE(3) helpers for controller TCP provenance."""

import hashlib
import json
import math
from typing import Sequence


def pose_mm_rad_to_matrix(values: Sequence[float]):
    """JAKA tool pose `[mm, mm, mm, r, p, y]` to `T_link6_tcp`.

    Rotation follows the controller/display convention already used by ARES-R:
    `Rz(yaw) * Ry(pitch) * Rx(roll)`.  This convention is explicit and covered by
    regression tests; a site tool revision must still be verified against JAKA App.
    """
    if len(values) != 6 or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("tool pose must contain six finite values")
    x, y, z = (float(value) / 1000.0 for value in values[:3])
    roll, pitch, yaw = (float(value) for value in values[3:])
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, x],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, y],
        [-sp, cp * sr, cp * cr, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def transform_revision(matrix) -> str:
    canonical = [[round(float(value), 12) for value in row] for row in matrix]
    blob = json.dumps(canonical, separators=(",", ":"), sort_keys=False).encode("ascii")
    return "sha256:" + hashlib.sha256(blob).hexdigest()
