"""Conservative, planning-only link6 envelope for the P3.3 movement demo.

The pinned gripper geometry remains the source of the finger/body extent.  The
selected controller TCP translation is included as a second source; it is not
silently substituted for the physical grasp centre.
"""

from __future__ import annotations

import hashlib
import json
import math


def _digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_execution_tool_envelope(collision_model, tool_pose_mm_rad, *, inflation_m=0.008):
    """Return a single conservative link6 AABB covering gripper and TCP ray.

    The TCP orientation is deliberately not used to reposition the fingers;
    the translation defines the origin-to-controller-TCP ray in link6.  The
    source box is the pinned ARES maximum-open gripper mesh envelope.
    """
    if len(tool_pose_mm_rad) != 6:
        raise ValueError("six-value controller tool pose required")
    tool_pose = [float(v) for v in tool_pose_mm_rad]
    source = collision_model["gripper_max_envelope_link6"]
    center = [float(v) for v in source["center_m"]]
    half = [float(v) for v in source["half_extents_m"]]
    tool = [v / 1000.0 for v in tool_pose[:3]]
    if (len(center) != 3 or len(half) != 3
            or not all(math.isfinite(v) for v in center + half + tool_pose)
            or any(v <= 0 for v in half) or not 0.003 <= inflation_m <= 0.020
            or not 0.12 <= tool[2] <= 0.25):
        raise ValueError("untrusted gripper/TCP dimensions; no execution envelope")
    lower = [min(center[i] - half[i], 0.0, tool[i]) - inflation_m for i in range(3)]
    upper = [max(center[i] + half[i], 0.0, tool[i]) + inflation_m for i in range(3)]
    box = {"center_m": [(a + b) / 2 for a, b in zip(lower, upper)],
           "half_extents_m": [(b - a) / 2 for a, b in zip(lower, upper)]}
    provenance = {
        "schema_version": 1,
        "frame": "link6", "unit": "m", "box": box,
        "pinned_ares_gripper": {"center_m": center, "half_extents_m": half,
                                "asset_revision": collision_model["asset_revision"]},
        "controller_tcp_translation_m": tool,
        "rough_flange_to_grasp_center_m": 0.145,
        "inflation_m": inflation_m,
        "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
        "EXECUTION_TOOL_ENVELOPE_CONSERVATIVE": "YES",
    }
    return dict(provenance, revision=_digest(provenance))


def verify_execution_tool_envelope(envelope, collision_model, tool_pose_mm_rad):
    expected = build_execution_tool_envelope(
        collision_model, tool_pose_mm_rad, inflation_m=float(envelope["inflation_m"]))
    if envelope != expected:
        raise ValueError("execution tool envelope revision/source mismatch")
    return expected
