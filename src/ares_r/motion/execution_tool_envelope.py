"""Pinned physical gripper envelope for the P3.3A free-space motion demo."""

from __future__ import annotations

import hashlib
import json
import math


def _digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_execution_tool_envelope(collision_model, tool_pose_mm_rad, *, inflation_m=0.008,
                                  observed_demo_only=False, max_opening_percent=None):
    """Return the pinned maximum-open ARES gripper box with sensor inflation.

    Controller TCP is a kinematic/task frame, not measured physical material.
    It remains revision-bound provenance but does not enlarge collision body.
    """
    if len(tool_pose_mm_rad) != 6:
        raise ValueError("six-value controller tool pose required")
    tool_pose = [float(v) for v in tool_pose_mm_rad]
    if max_opening_percent is None:
        source = collision_model["gripper_max_envelope_link6"]
        opening_policy = "UNKNOWN_USE_FULL_OPENING_UNION"
    else:
        key = str(int(max_opening_percent))
        if float(max_opening_percent) != int(max_opening_percent):
            raise ValueError("gripper opening profile must be an integer percent")
        profiles = collision_model.get("gripper_envelopes_link6_by_max_opening_percent", {})
        if key not in profiles:
            raise ValueError("no pinned gripper envelope for maximum opening %s%%" % key)
        source = profiles[key]
        opening_policy = "PINNED_MESH_UNION_0_TO_%s_PERCENT" % key
    center = [float(v) for v in source["center_m"]]
    half = [float(v) for v in source["half_extents_m"]]
    # B-point Pixel Pro hold-out (2026-09-22, cloud SHA a9198f13...)
    # found four gripper-adjacent clusters outside the pinned mesh envelope.
    # This is a conservative, right A/B demo-only collision envelope. It is
    # deliberately not a new physical TCP calibration or a production model.
    observed_bounds = [[-.062, -.047, -.007], [.062, .017, .192]]
    tool = [v / 1000.0 for v in tool_pose[:3]]
    if (len(center) != 3 or len(half) != 3
            or not all(math.isfinite(v) for v in center + half + tool_pose)
            or any(v <= 0 for v in half) or not 0.003 <= inflation_m <= 0.020
            or not 0.12 <= tool[2] <= 0.25):
        raise ValueError("untrusted gripper/TCP dimensions; no execution envelope")
    lower = [center[i] - half[i] for i in range(3)]
    upper = [center[i] + half[i] for i in range(3)]
    if observed_demo_only:
        lower = [min(lower[i], observed_bounds[0][i]) for i in range(3)]
        upper = [max(upper[i], observed_bounds[1][i]) for i in range(3)]
    lower = [v - inflation_m for v in lower]
    upper = [v + inflation_m for v in upper]
    box = {"center_m": [(a + b) / 2 for a, b in zip(lower, upper)],
           "half_extents_m": [(b - a) / 2 for a, b in zip(lower, upper)]}
    provenance = {
        "schema_version": 2,
        "frame": "link6", "unit": "m", "box": box,
        "pinned_ares_gripper": {"center_m": center, "half_extents_m": half,
                                "asset_revision": collision_model["asset_revision"]},
        "maximum_opening_percent": max_opening_percent,
        "opening_geometry_policy": opening_policy,
        "controller_tcp_task_frame_translation_m": tool,
        "controller_tcp_is_physical_collision_body": False,
        "observed_demo_only": bool(observed_demo_only),
        "observed_gripper_bounds_link6_m": observed_bounds if observed_demo_only else None,
        "observed_source_pointcloud_sha256": (
            "a9198f1354f80c9b53a38ec983048fdf82877d074768da4d482e23a355d9cfe6"
            if observed_demo_only else None),
        "rough_flange_to_grasp_center_m": 0.145,
        "inflation_m": inflation_m,
        "TOOL_TCP_PHYSICAL_SEMANTICS_UNRESOLVED": "YES",
        "EXECUTION_TOOL_ENVELOPE_CONSERVATIVE": "YES",
    }
    return dict(provenance, revision=_digest(provenance))


def verify_execution_tool_envelope(envelope, collision_model, tool_pose_mm_rad):
    expected = build_execution_tool_envelope(
        collision_model, tool_pose_mm_rad, inflation_m=float(envelope["inflation_m"]),
        observed_demo_only=envelope.get("observed_demo_only") is True,
        max_opening_percent=envelope.get("maximum_opening_percent"))
    if envelope != expected:
        raise ValueError("execution tool envelope revision/source mismatch")
    return expected
