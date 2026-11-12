"""Opening-specific collision geometry for the pinned EG2-4C2 gripper.

The component OBBs preserve the space between fingers and linkage members.  A
single union AABB remains a fail-closed fallback for unknown opening only.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping

import numpy as np

from ares_r.perception.robot_collision import _axis_rotation, transform_xyz_rpy
from ares_r.perception.robot_owned_filter import grid_spheres_local


_LINKS = ("4C2_baselink", "4C2_Link1", "4C2_Link2", "4C2_Link3",
          "4C2_Link4", "4C2_Link5", "4C2_Link6")


def _joint(origin, axis, angle):
    return transform_xyz_rpy(origin, (0.0, 0.0, 0.0)) @ _axis_rotation(axis, angle)


def component_transforms(opening_percent: int) -> dict:
    """Return link6->component transforms from the pinned URDF linkage."""
    if type(opening_percent) is not int or not 0 <= opening_percent <= 100:
        raise ValueError("opening percent must be an integer in 0..100")
    opening = 0.82 * opening_percent / 100.0
    result = {"4C2_baselink": np.eye(4)}
    result["4C2_Link1"] = _joint((-.04, -.009, .079), (0, -1, 0), opening)
    result["4C2_Link2"] = _joint((-.03, -.009, .081), (0, -1, 0), opening)
    result["4C2_Link3"] = _joint(( .03, -.009, .081), (0, -1, 0), -opening)
    result["4C2_Link4"] = _joint(( .04, -.009, .079), (0, -1, 0), -opening)
    result["4C2_Link5"] = result["4C2_Link1"] @ _joint(
        (.0223, .003, .035591), (0, 1, 0), opening)
    result["4C2_Link6"] = result["4C2_Link4"] @ _joint(
        (-.0223, .003, .035591), (0, -1, 0), opening)
    return result


def build_gripper_component_model(collision_model: Mapping[str, object],
                                  opening_percent: int, *, inflation_m=0.0) -> dict:
    if not 0 <= float(inflation_m) <= .008:
        raise ValueError("component inflation must be 0..8 mm")
    audits = collision_model.get("mesh_audit", {}).get("gripper", {})
    if set(_LINKS) - set(audits):
        raise ValueError("pinned gripper component mesh bounds are incomplete")
    transforms = component_transforms(opening_percent)
    components = []
    for link in _LINKS:
        bounds = audits[link]
        low = np.asarray(bounds["bounds_min_m"], dtype=float)
        high = np.asarray(bounds["bounds_max_m"], dtype=float)
        if low.shape != (3,) or high.shape != (3,) or np.any(high <= low):
            raise ValueError("invalid pinned mesh bounds for %s" % link)
        transform = transforms[link]
        center_local = (low + high) / 2.0
        components.append({
            "component_id": link,
            "center_link6_m": (transform[:3, :3] @ center_local
                                + transform[:3, 3]).tolist(),
            "rotation_link6": transform[:3, :3].tolist(),
            "half_extents_m": ((high-low)/2.0 + float(inflation_m)).tolist(),
            "mesh_sha256": collision_model["asset_sha256"][
                "eg2_4c2_meshes/%s.STL" % link],
        })
    core = {
        "schema_version": 1,
        "frame": "link6",
        "asset_revision": collision_model["asset_revision"],
        "urdf_sha256": collision_model["asset_sha256"][collision_model["urdf"]],
        "opening_percent": opening_percent,
        "opening_angle_rad": .82 * opening_percent / 100.0,
        "inflation_m": float(inflation_m),
        "components": components,
        "representation": "PINNED_COMPONENT_OBB_NO_UNION",
    }
    core["revision"] = "sha256:" + hashlib.sha256(json.dumps(
        core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return core


def verify_gripper_component_model(value, collision_model):
    expected = build_gripper_component_model(
        collision_model, int(value["opening_percent"]),
        inflation_m=float(value["inflation_m"]))
    if value != expected:
        raise ValueError("gripper component geometry revision/source mismatch")
    return expected


def component_spheres_link6(value, collision_model, cell_m):
    verify_gripper_component_model(value, collision_model)
    if not .015 <= float(cell_m) <= .060:
        raise ValueError("component sphere cell must be 15..60 mm")
    result = []
    for component in value["components"]:
        rotation = np.asarray(component["rotation_link6"], dtype=float)
        center = np.asarray(component["center_link6_m"], dtype=float)
        local_box = {"center_m": [0.0, 0.0, 0.0],
                     "half_extents_m": component["half_extents_m"]}
        for sphere in grid_spheres_local(local_box, float(cell_m)):
            result.append({
                "center": (rotation @ np.asarray(sphere["center"], dtype=float)
                           + center).tolist(),
                "radius": float(sphere["radius"]),
                "component_id": component["component_id"],
            })
    return result


def component_spheres_body(value, collision_model, cell_m, T_body_link6):
    """SafetyKernel/WebUI adapter over the identical planner sphere source."""
    transform = np.asarray(T_body_link6, dtype=float)
    if transform.shape != (4, 4):
        raise ValueError("T_body_link6 must be 4x4")
    result = []
    for sphere in component_spheres_link6(value, collision_model, cell_m):
        center = (transform @ np.r_[sphere["center"], 1.0])[:3]
        result.append(dict(sphere, center_body_m=center.tolist()))
    return result


def component_boxes_body(value, collision_model, T_body_link6):
    """Return the exact component OBBs used by terminal contact validation."""
    verify_gripper_component_model(value, collision_model)
    transform = np.asarray(T_body_link6, dtype=float)
    if transform.shape != (4, 4):
        raise ValueError("T_body_link6 must be 4x4")
    result = []
    for component in value["components"]:
        center = (transform @ np.r_[component["center_link6_m"], 1.0])[:3]
        rotation = transform[:3, :3] @ np.asarray(
            component["rotation_link6"], dtype=float)
        result.append({
            "geometry_id": component["component_id"],
            "center_body_m": center.tolist(),
            "rotation_body": rotation.tolist(),
            "half_extents_m": list(component["half_extents_m"]),
            "dims_m": (2.0 * np.asarray(component["half_extents_m"])).tolist(),
            "component_revision": value["revision"],
        })
    return result
