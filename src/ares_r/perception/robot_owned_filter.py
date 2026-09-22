"""Canonical robot-owned point-cloud filter geometry.

The filter is the explicit union of the validated P2 OBB geometry and the
exact circumscribed sphere geometry used by the P3 cuRobo planner.  This keeps
overlay, self-filtering, and planning ownership consistent without globally
inflating every scene obstacle.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time

import numpy as np

from .robot_collision import CollisionBox, RobotGeometrySnapshot, _inside_box


def _digest(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RobotOwnedSphere:
    geometry_id: str
    owner: str
    center_body_m: tuple
    radius_m: float
    source_box_id: str

    def as_dict(self):
        return {"geometry_id": self.geometry_id, "owner": self.owner,
                "center_body_m": list(self.center_body_m), "radius_m": self.radius_m,
                "source_box_id": self.source_box_id,
                "source": "exact P3 planner circumscribed-cell sphere"}


@dataclass(frozen=True)
class RobotOwnedFilterGeometry:
    boxes: tuple
    spheres: tuple
    planning_sphere_cell_m: float
    obb_sensor_margin_m: float
    gripper_sensor_margin_m: float
    sphere_sensor_margin_m: float
    source_scene_revision: str
    revision: str

    def as_dict(self):
        return {"schema_version": 1, "frame": "BODY", "unit": "m",
                "contract": "ROBOT_OWNED_FILTER",
                "boxes": [box.as_dict() for box in self.boxes],
                "spheres": [sphere.as_dict() for sphere in self.spheres],
                "planning_sphere_cell_m": self.planning_sphere_cell_m,
                "obb_sensor_margin_m": self.obb_sensor_margin_m,
                "gripper_sensor_margin_m": self.gripper_sensor_margin_m,
                "sphere_sensor_margin_m": self.sphere_sensor_margin_m,
                "source_scene_revision": self.source_scene_revision,
                "revision": self.revision,
                "provenance": {
                    "boxes": "validated P2 mesh-derived OBB and fixed BODY geometry",
                    "spheres": "same cell construction and 35 mm cell size as P3 active-arm planner",
                    "ownership": "union; no scene-derived obstacle is silently relabelled",
                }}


def grid_spheres_local(box, max_cell_m=.035):
    """Planner/filter shared circumscribed-cell spheres in a box local frame."""
    center = np.asarray(box["center_m"], dtype=float)
    half = np.asarray(box["half_extents_m"], dtype=float)
    count = np.maximum(1, np.ceil(2 * half / max_cell_m).astype(int))
    cell = 2 * half / count
    radius = float(np.linalg.norm(cell / 2))
    axes = [center[index] - half[index] + cell[index] * (.5 + np.arange(count[index]))
            for index in range(3)]
    return [{"center": [float(x), float(y), float(z)], "radius": radius}
            for x in axes[0] for y in axes[1] for z in axes[2]]


def _box_grid_spheres(box: CollisionBox, cell_m: float) -> list:
    center = np.asarray(box.center_body_m, dtype=float)
    rotation = np.asarray(box.rotation_body, dtype=float)
    values = []
    local = {"center_m": [0.0, 0.0, 0.0], "half_extents_m": box.half_extents_m}
    for serial, sphere in enumerate(grid_spheres_local(local, cell_m)):
        point = center + rotation @ np.asarray(sphere["center"])
        values.append(RobotOwnedSphere(
            "%s/planning_sphere_%03d" % (box.geometry_id, serial), box.owner,
            tuple(point.tolist()), sphere["radius"], box.geometry_id))
    return values


def build_robot_owned_filter(snapshot: RobotGeometrySnapshot, *, planning_sphere_cell_m=.035,
                             obb_sensor_margin_m=.020,
                             gripper_sensor_margin_m=.020,
                             sphere_sensor_margin_m=.003) -> RobotOwnedFilterGeometry:
    if not .015 <= planning_sphere_cell_m <= .060:
        raise ValueError("planning sphere cell must be between 15 and 60 mm")
    if (not 0 <= obb_sensor_margin_m <= .05 or
            not 0 <= gripper_sensor_margin_m <= .05 or
            not 0 <= sphere_sensor_margin_m <= .02):
        raise ValueError("sensor margins exceed commissioned bounds")
    boxes = tuple(box for box in snapshot.boxes if box.filter_owned)
    planning_boxes = [box for box in boxes
                      if box.kind in ("arm_link", "gripper_max_envelope")]
    spheres = tuple(sphere for box in planning_boxes
                    for sphere in _box_grid_spheres(box, planning_sphere_cell_m))
    payload = {"scene": snapshot.scene_revision,
               "cell_m": planning_sphere_cell_m,
               "obb_margin_m": obb_sensor_margin_m,
               "gripper_margin_m": gripper_sensor_margin_m,
               "sphere_margin_m": sphere_sensor_margin_m,
               "boxes": [box.as_dict() for box in boxes],
               "spheres": [sphere.as_dict() for sphere in spheres]}
    return RobotOwnedFilterGeometry(boxes, spheres, planning_sphere_cell_m,
                                    obb_sensor_margin_m, gripper_sensor_margin_m,
                                    sphere_sensor_margin_m,
                                    snapshot.scene_revision, _digest(payload))


def _sphere_assign(points, spheres, margin_m):
    hit = np.zeros(len(points), dtype=bool)
    owner = np.full(len(points), -1, dtype=np.int32)
    best = np.full(len(points), np.inf)
    for index, sphere in enumerate(spheres):
        signed = np.linalg.norm(points - np.asarray(sphere.center_body_m), axis=1) - sphere.radius_m
        improve = signed < best
        best[improve] = signed[improve]
        owner[improve] = index
        hit |= signed <= margin_m
    return hit, owner, best


def filter_robot_owned(points_body_m, geometry: RobotOwnedFilterGeometry):
    started = time.perf_counter(); points = np.asarray(points_body_m, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("BODY Nx3 points required")
    obb_hit = np.zeros(len(points), dtype=bool)
    for box in geometry.boxes:
        margin = (geometry.gripper_sensor_margin_m
                  if box.kind == "gripper_max_envelope"
                  else geometry.obb_sensor_margin_m)
        obb_hit |= _inside_box(points, box, margin)
    sphere_hit = np.zeros(len(points), dtype=bool)
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        # The controller's system Python intentionally has no SciPy.  This
        # bounded NumPy path keeps the pure-geometry contract usable there.
        for sphere in geometry.spheres:
            center = np.asarray(sphere.center_body_m)
            radius = sphere.radius_m + geometry.sphere_sensor_margin_m
            candidates = np.flatnonzero(np.all(np.abs(points - center) <= radius, axis=1))
            if len(candidates):
                sphere_hit[candidates] |= (np.linalg.norm(points[candidates] - center, axis=1)
                                           <= radius)
    else:
        tree = cKDTree(points)
        for sphere in geometry.spheres:
            indices = tree.query_ball_point(np.asarray(sphere.center_body_m),
                                            sphere.radius_m + geometry.sphere_sensor_margin_m)
            sphere_hit[np.asarray(indices, dtype=int)] = True
    robot = obb_hit | sphere_hit
    stats = {"raw_points": int(len(points)), "removed_points": int(robot.sum()),
             "retained_points": int((~robot).sum()),
             "obb_removed_points": int(obb_hit.sum()),
             "planning_sphere_removed_points": int(sphere_hit.sum()),
             "sphere_only_removed_points": int((sphere_hit & ~obb_hit).sum()),
             "revision": geometry.revision,
             "elapsed_s": time.perf_counter() - started}
    return ~robot, stats


def point_signed_distance_to_box(points, box: CollisionBox):
    points = np.asarray(points, dtype=float)
    local = (points - np.asarray(box.center_body_m)) @ np.asarray(box.rotation_body)
    delta = np.abs(local) - np.asarray(box.half_extents_m)
    return np.linalg.norm(np.maximum(delta, 0.0), axis=1) + np.minimum(
        np.max(delta, axis=1), 0.0)


def attribute_cluster(points, geometry: RobotOwnedFilterGeometry):
    """Return nearest P2 OBB and exact-planner-sphere provenance."""
    points = np.asarray(points, dtype=float)
    box_rows = []
    for box in geometry.boxes:
        distances = point_signed_distance_to_box(points, box)
        box_rows.append((float(distances.min()), box))
    sphere_hit, sphere_owner, sphere_distance = _sphere_assign(
        points, geometry.spheres, geometry.sphere_sensor_margin_m)
    sphere_index = int(sphere_owner[int(np.argmin(sphere_distance))])
    nearest_sphere = geometry.spheres[sphere_index]
    box_rows.sort(key=lambda row: row[0])
    nearest_box_distance, nearest_box = box_rows[0]
    return {"point_count": int(len(points)),
            "nearest_obb": {"geometry_id": nearest_box.geometry_id,
                            "owner": nearest_box.owner,
                            "kind": nearest_box.kind,
                            "signed_distance_m": nearest_box_distance},
            "nearest_planning_sphere": {
                "geometry_id": nearest_sphere.geometry_id,
                "owner": nearest_sphere.owner,
                "source_box_id": nearest_sphere.source_box_id,
                "signed_distance_m": float(sphere_distance.min())},
            "points_inside_planning_sphere_filter": int(sphere_hit.sum()),
            "classification": ("ROBOT_OWNED_PLANNER_GEOMETRY"
                               if sphere_hit.any() else "NOT_ROBOT_OWNED")}
