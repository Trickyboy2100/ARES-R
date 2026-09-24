"""Strict loader for the versioned Tray-to-Groove task parameters."""

from __future__ import annotations

import json
import math
from pathlib import Path


def load_task_parameters(path="config/tray_to_groove_v2.json") -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not value.get("revision"):
        raise ValueError("versioned tray-to-groove parameters required")
    scope = value["demo_scope"]
    if scope != {"manipulation_arm": "right", "inactive_arm_policy": "HOLD_CURRENT",
                 "dual_arm_concurrent": False}:
        raise ValueError("first customer demo scope must remain right/HOLD_CURRENT/non-concurrent")
    distances = [float(item) for item in value["contact"]["pregrasp_distance_candidates_m"]]
    if distances != [.03, .04, .05]:
        raise ValueError("pregrasp candidates must be the commissioned 30/40/50 mm set")
    verification = value["grasp_verification"]
    radius = float(verification["local_tcp_radius_m"])
    low, high = map(float, verification["allowed_radius_range_m"])
    if not .10 <= low <= radius <= high <= .20:
        raise ValueError("local TCP delta radius must stay in 10..20 cm")
    percentages = [value["gripper"][name]
                   for name in ("prepare_percent", "pregrasp_percent", "release_percent")]
    if percentages != [50, 40, 20]:
        raise ValueError("first demo gripper percentages must remain 50/40/20")
    for item in (value["place"]["preplace_height_m"],
                 value["place"]["placement_offset_m"],
                 value["place"]["lift_body_z_m"]):
        if not math.isfinite(float(item)):
            raise ValueError("task distances must be finite")
    if set(value["base_contracts"]) != {"PICK_BASE_POSE_V1", "PLACE_BASE_POSE_V1"}:
        raise ValueError("versioned pickup/place base contracts are required")
    if value["visibility_clear"].get("semantic") != "RIGHT_FRONT_VISIBILITY_CLEAR":
        raise ValueError("semantic visibility-clear target is required")
    if value["retreat"].get("semantic") != "VERTICAL_CLEARANCE_RETREAT":
        raise ValueError("versioned retreat contract is required")
    fidelity=value["collision_fidelity"]
    if (fidelity.get("gripper_max_opening_percent") != 40 or
            float(fidelity.get("active_sphere_cell_m", 0)) != .020 or
            float(fidelity.get("tool_envelope_inflation_m", 0)) != .008):
        raise ValueError("pinned 40-percent manipulation collision profile required")
    binding=value["target_binding"]
    if not binding.get("pick_preferred_semantics") or not binding.get("place_preferred_semantics"):
        raise ValueError("purpose-specific target binding semantics are required")
    return value


def gripper_percent_to_raw(percent: float, parameters: dict) -> int:
    percent = float(percent)
    if not 0 <= percent <= 100:
        raise ValueError("gripper percentage must be 0..100")
    cfg = parameters["gripper"]
    return round(float(cfg["raw_closed"]) + percent / 100.0 *
                 (float(cfg["raw_open"]) - float(cfg["raw_closed"])))
