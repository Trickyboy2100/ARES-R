"""CPU/URDF dense world check independent of cuRobo's collision query.

This is a second modeled check, not physical collision certification. It uses
the same versioned collision boxes but computes link FK and box distances
without asking the planner for spheres or accepting its clearance output.
"""

from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ares_r.perception.robot_collision import transform_xyz_rpy
from ares_r.perception.robot_owned_filter import grid_spheres_local


def _quaternion_rotation(q):
    w, x, y, z = [float(v) for v in q]
    return np.asarray([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])


def _urdf_joint_origins(urdf_path):
    root = ET.parse(Path(urdf_path)).getroot()
    origins = []
    for index in range(1, 7):
        joint = root.find("joint[@name='joint%d']" % index)
        if joint is None or joint.find("axis").get("xyz") != "0 0 1":
            raise ValueError("unexpected six-axis URDF")
        origin = joint.find("origin")
        origins.append(transform_xyz_rpy(
            [float(v) for v in origin.get("xyz").split()],
            [float(v) for v in origin.get("rpy").split()]))
    return origins


def _dense_points(points, subdivisions):
    q = np.asarray(points, dtype=float)
    if q.ndim != 2 or q.shape[1] != 6 or len(q) < 2 or not np.isfinite(q).all():
        raise ValueError("finite Nx6 trajectory required")
    if not 2 <= subdivisions <= 16:
        raise ValueError("dense subdivisions outside audited range")
    factors = np.arange(subdivisions, dtype=float) / subdivisions
    return np.concatenate([before[None, :] + factors[:, None] * (after-before)
                           for before, after in zip(q, q[1:])] + [q[-1:]])


def _bounded_knots(points, max_joint_step_rad=0.002):
    """Drop time-resampling redundancy while bounding validation joint gaps."""
    q=np.asarray(points,dtype=float)
    selected=[q[0]];last=q[0]
    for row in q[1:-1]:
        if float(np.max(np.abs(row-last))) >= max_joint_step_rad:
            selected.append(row);last=row
    if len(selected)==1 or not np.array_equal(selected[-1],q[-1]):
        selected.append(q[-1])
    return np.asarray(selected)


def validate_dense_world(points, request, *, subdivisions=4):
    """Return worst signed sphere/cuboid gap and BODY central TCP margin."""
    input_count=len(points)
    knots=_bounded_knots(points)
    q = _dense_points(knots, subdivisions)
    model = request["collision_model"]
    cell = float(request["planning_parameters"].get("active_sphere_cell_m", 0.035))
    local = {link: grid_spheres_local(box, cell)
             for link, box in model["arm_link_boxes"].items()}
    tool_box = (request["execution_tool_envelope"]["box"]
                if request.get("execution_tool_envelope")
                else model["gripper_max_envelope_link6"])
    local["link6"].extend(grid_spheres_local(tool_box, cell))
    attached = request.get("attached_object_collision")
    if attached is not None:
        from ares_r.manipulation.attached_collision import verify_attached_collision
        verify_attached_collision(attached,
            request.get("motion_constraints", {}).get("attached_object_revision"))
        local["link6"].extend(grid_spheres_local(attached["link6_aabb"], cell))
    origins = _urdf_joint_origins(request["robot_yaml_urdf"])
    tool = np.asarray(request["T_link6_tcp"], dtype=float)
    body_model = np.asarray(request["T_body_model"], dtype=float)
    if tool.shape != (4, 4) or body_model.shape != (4, 4):
        raise ValueError("full-SE3 tool and BODY transforms required")
    centers = []
    radii = []
    central_margin = float("inf")
    for row in q:
        frame = np.eye(4)
        link_frames = {"base_link": frame.copy()}
        for index, (origin, angle) in enumerate(zip(origins, row), 1):
            frame = frame @ origin @ transform_xyz_rpy([0, 0, 0], [0, 0, float(angle)])
            link_frames["link%d" % index] = frame.copy()
        tcp_body = body_model @ frame @ tool
        y = float(tcp_body[1, 3])
        margin = (-y - 0.070 if request["active_arm"] == "right" else y - 0.070)
        central_margin = min(central_margin, margin)
        row_centers = []
        row_radii = []
        for link, spheres in local.items():
            pose = link_frames[link]
            locations = np.asarray([s["center"] for s in spheres], dtype=float)
            row_centers.append(locations @ pose[:3, :3].T + pose[:3, 3])
            row_radii.extend(float(s["radius"]) for s in spheres)
        centers.append(np.concatenate(row_centers))
        radii = row_radii
    sphere_centers = np.asarray(centers)
    sphere_radii = np.asarray(radii)
    by_object = {}
    for name, box in request["compiled_scene"]["cuboids"].items():
        rotation = _quaternion_rotation(box["pose"][3:])
        center = np.asarray(box["pose"][:3], dtype=float)
        dims = np.asarray(box["dims"], dtype=float)
        local_centers = (sphere_centers - center) @ rotation
        delta = np.abs(local_centers) - dims / 2
        signed = (np.linalg.norm(np.maximum(delta, 0), axis=-1)
                  + np.minimum(np.max(delta, axis=-1), 0) - sphere_radii[None, :])
        by_object[name] = float(np.min(signed))
    minimum_name = min(by_object, key=by_object.get) if by_object else None
    minimum = by_object[minimum_name] if minimum_name else float("inf")
    return {"validator": "independent_cpu_urdf_sphere_cuboid_v1",
            "input_trajectory_samples":int(input_count),
            "validation_knots":int(len(knots)),
            "maximum_knot_joint_step_rad":float(np.max(np.abs(np.diff(knots,axis=0)))),
            "dense_samples": int(len(q)), "subdivisions": subdivisions,
            "min_clearance_m": minimum, "limiting_object_id": minimum_name,
            "central_tcp_margin_m": central_margin,
            "collision_free": math.isfinite(minimum) and minimum > 0 and central_margin > 0,
            "self_collision_independently_checked": False}
