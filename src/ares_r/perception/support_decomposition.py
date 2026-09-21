"""Generic support-surface and protruding-object decomposition in BODY.

This deterministic V0 keeps the P3 single-AABB result as a comparator while
emitting multiple conservative axis-aligned primitives from observed points.
It never labels occluded volume as free.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np


@dataclass(frozen=True)
class DecompositionProfile:
    support_bin_m: float = .005
    support_band_m: float = .010
    support_min_points: int = 120
    support_min_span_m: float = .10
    support_footprint_extension_m: float = .08
    protrusion_min_height_m: float = .025
    component_tolerance_m: float = .018
    component_min_points: int = 10
    tile_xy_m: float = .04
    slice_z_m: float = .03
    primitive_min_dim_m: float = .008
    inflation_m: float = .007


def _cloud(points):
    import open3d as o3d
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.asarray(points, dtype=float)))


def _bounds(points):
    low, high = points.min(axis=0), points.max(axis=0)
    return low, high


def _volume(low, high):
    return float(np.prod(np.maximum(0.0, np.asarray(high) - np.asarray(low))))


def detect_support_levels(points, profile=DecompositionProfile()):
    """Detect horizontal observed support bands without changing calibration."""
    points = np.asarray(points, dtype=float)
    cloud = _cloud(points)
    import open3d as o3d
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=.025, max_nn=30))
    normals = np.asarray(cloud.normals)
    low = np.floor(points[:, 2].min() / profile.support_bin_m) * profile.support_bin_m
    high = np.ceil(points[:, 2].max() / profile.support_bin_m) * profile.support_bin_m
    edges = np.arange(low, high + 2 * profile.support_bin_m, profile.support_bin_m)
    counts, edges = np.histogram(points[:, 2], bins=edges)
    candidates = []
    for index in range(len(counts)):
        if counts[index] < profile.support_min_points:
            continue
        previous = counts[index - 1] if index else 0
        following = counts[index + 1] if index + 1 < len(counts) else 0
        if counts[index] < previous or counts[index] < following:
            continue
        z = float((edges[index] + edges[index + 1]) / 2.0)
        band_mask = np.abs(points[:, 2] - z) <= profile.support_band_m
        band = points[band_mask]; band_normals = normals[band_mask]
        if len(band) < profile.support_min_points:
            continue
        flattened = band.copy(); flattened[:, 2] = 0.0
        labels = np.asarray(_cloud(flattened).cluster_dbscan(
            eps=max(.025, profile.component_tolerance_m), min_points=12,
            print_progress=False), dtype=int)
        for label in sorted(set(labels.tolist()) - {-1}):
            component = band[labels == label]
            component_normals = band_normals[labels == label]
            if len(component) < profile.support_min_points:
                continue
            span = np.ptp(component[:, :2], axis=0)
            if float(min(span)) < .060 or float(max(span)) < profile.support_min_span_m:
                continue
            horizontal_fraction = float(np.mean(np.abs(component_normals[:, 2]) >= .85))
            if horizontal_fraction < .45:
                continue
            candidates.append({"z_m": float(np.median(component[:, 2])),
                               "point_count": int(len(component)),
                               "xy_min_m": component[:, :2].min(axis=0).tolist(),
                               "xy_max_m": component[:, :2].max(axis=0).tolist(),
                               "xy_span_m": span.tolist(),
                               "horizontal_normal_fraction": horizontal_fraction})
    merged = []
    for item in sorted(candidates, key=lambda value: value["z_m"]):
        overlaps_previous = False
        if merged and abs(item["z_m"] - merged[-1]["z_m"]) <= 2 * profile.support_bin_m:
            low = np.maximum(item["xy_min_m"], merged[-1]["xy_min_m"])
            high = np.minimum(item["xy_max_m"], merged[-1]["xy_max_m"])
            overlaps_previous = bool(np.all(low <= high))
        if overlaps_previous:
            if item["point_count"] > merged[-1]["point_count"]:
                merged[-1] = item
        else:
            merged.append(item)
    return merged


def _support_assignment(points, supports, profile):
    assignment = np.full(len(points), -1, dtype=int)
    height = np.full(len(points), np.nan)
    for index, support in enumerate(supports):
        xy_low = np.asarray(support["xy_min_m"]) - profile.support_footprint_extension_m
        xy_high = np.asarray(support["xy_max_m"]) + profile.support_footprint_extension_m
        within = np.all((points[:, :2] >= xy_low) & (points[:, :2] <= xy_high), axis=1)
        local = points[:, 2] - support["z_m"]
        valid = within & (local >= -profile.support_band_m) & (local <= .45)
        # Assign to the lowest observed support beneath the point.  An upper
        # face of an object must not hide that the object protrudes from the
        # lower dock/table support on which it stands.
        replace = valid & (np.isnan(height) | (local > height))
        assignment[replace] = index
        height[replace] = local[replace]
    return assignment, height


def _spatial_components(points, profile):
    if not len(points):
        return []
    labels = np.asarray(_cloud(points).cluster_dbscan(
        eps=profile.component_tolerance_m,
        min_points=profile.component_min_points,
        print_progress=False), dtype=int)
    return [points[labels == label] for label in sorted(set(labels.tolist()) - {-1})]


def _tile_component(points, profile, semantic, source_id, minimum_points=None):
    """Split occupied observations into small XYZ cells; never fill empty cells."""
    if not len(points):
        return []
    origin = points.min(axis=0)
    scale = np.asarray([profile.tile_xy_m, profile.tile_xy_m, profile.slice_z_m])
    keys = np.floor((points - origin) / scale).astype(int)
    primitives = []
    for serial, key in enumerate(sorted(set(map(tuple, keys.tolist())))):
        member = points[np.all(keys == np.asarray(key), axis=1)]
        threshold=(max(3,profile.component_min_points//2)
                   if minimum_points is None else int(minimum_points))
        if len(member) < threshold:
            continue
        low, high = _bounds(member)
        dims = np.maximum(high - low, profile.primitive_min_dim_m)
        center = (low + high) / 2.0
        primitives.append({"primitive_id": "%s_%s_%03d" % (source_id, semantic.lower(), serial),
                           "semantic": semantic, "source_cluster": source_id,
                           "point_count": int(len(member)),
                           "center_m": center.tolist(), "dims_m": dims.tolist(),
                           "inflation_m": profile.inflation_m,
                           "observed_bounds_m": [low.tolist(), high.tolist()]})
    return primitives


def decompose_support_objects(points_body_m, old_boxes, profile=DecompositionProfile()):
    started = time.perf_counter(); points = np.asarray(points_body_m, dtype=float)
    supports = detect_support_levels(points, profile); support_s = time.perf_counter()
    assignment, height = _support_assignment(points, supports, profile)
    primitives = []; labelled = np.zeros(len(points), dtype=bool)
    support_records = []
    for index, support in enumerate(supports):
        band = ((assignment == index) & (np.abs(height) <= profile.support_band_m)
                & ~labelled)
        support_points = points[band]
        if len(support_points):
            labelled |= band
            low, high = _bounds(support_points)
            support_records.append({**support, "support_id": "support_%02d" % index,
                                    "observed_bounds_m": [low.tolist(), high.tolist()]})
            primitives.extend(_tile_component(support_points, profile, "SUPPORT_SURFACE",
                                              "support_%02d" % index,minimum_points=1))
        protruding = ((assignment == index) & (height > profile.protrusion_min_height_m)
                      & ~labelled)
        candidate_indices=np.flatnonzero(protruding)
        candidate=points[candidate_indices]
        labels=(np.asarray(_cloud(candidate).cluster_dbscan(
            eps=profile.component_tolerance_m,min_points=profile.component_min_points,
            print_progress=False),dtype=int) if len(candidate) else np.asarray([],dtype=int))
        for component_index,label in enumerate(sorted(set(labels.tolist())-{-1})):
            component=candidate[labels==label]
            labelled[candidate_indices[labels==label]]=True
            source = "support_%02d_component_%02d" % (index, component_index)
            # A compact protruding component remains one primitive. Large or
            # sparse connected observations are tiled to preserve visible gaps.
            low, high = _bounds(component); dims = high - low
            occupancy = len(component) * (.005 ** 3) / max(_volume(low, high), 1e-9)
            if max(dims) <= .28 and occupancy >= .001:
                primitives.append({"primitive_id": source + "_protruding",
                                   "semantic": "PROTRUDING_OBSTACLE",
                                   "source_cluster": source,
                                   "point_count": int(len(component)),
                                   "center_m": ((low + high) / 2).tolist(),
                                   "dims_m": np.maximum(dims, profile.primitive_min_dim_m).tolist(),
                                   "inflation_m": profile.inflation_m,
                                   "observed_bounds_m": [low.tolist(), high.tolist()]})
            else:
                primitives.extend(_tile_component(component, profile,
                                                  "PROTRUDING_OBSTACLE", source))
    # Remaining observed structure/unknown occupancy is split rather than
    # expanded to a connected-component-wide solid box.
    structure=(~labelled)&(assignment>=0)
    primitives.extend(_tile_component(points[structure],profile,"STRUCTURE",
                                      "remaining_structure",minimum_points=1))
    labelled|=structure
    remaining = points[~labelled]
    # Grid every remaining observed point.  The prior cleanup stage already
    # rejected sparse noise; decomposition must not silently drop survivors.
    primitives.extend(_tile_component(remaining,profile,"UNKNOWN_OCCUPIED",
                                      "remaining_observed",minimum_points=1))
    old_volume = sum(_volume(np.asarray(box["min_m"]), np.asarray(box["max_m"]))
                     for box in old_boxes)
    new_volume = sum(float(np.prod(primitive["dims_m"])) for primitive in primitives)
    report = {"schema_version": 1, "frame": "BODY", "unit": "m",
              "profile": profile.__dict__, "supports": support_records,
              "primitives": primitives,
              "semantics": ["SUPPORT_SURFACE", "STRUCTURE", "PROTRUDING_OBSTACLE",
                            "UNKNOWN_OCCUPIED", "TARGET_FREE_VOLUME"],
              "target_free_volume_policy": "contract only; no unseen volume subtracted",
              "old_single_aabb_count": int(len(old_boxes)),
              "old_single_aabb_occupied_volume_m3": old_volume,
              "multi_primitive_count": int(len(primitives)),
              "input_observed_point_count": int(len(points)),
              "primitive_point_count_sum": int(sum(item["point_count"] for item in primitives)),
              "observed_point_accounting_ratio": float(
                  sum(item["point_count"] for item in primitives)/max(1,len(points))),
              "multi_primitive_occupied_volume_m3": new_volume,
              "occupied_volume_ratio": new_volume / old_volume if old_volume else None,
              "timing_s": {"support_detection": support_s - started,
                           "assignment_decomposition_primitives": time.perf_counter() - support_s,
                           "total": time.perf_counter() - started}}
    return report


def _aabb_sphere_gap(low, high, sphere, inflation):
    center = np.asarray(sphere.center_body_m)
    closest = np.minimum(np.maximum(center, low - inflation), high + inflation)
    return float(np.linalg.norm(center - closest) - sphere.radius_m)


def refine_robot_adjacent_primitives(points_body_m, report, robot_owned,
                                     cell_m=.015, inflation_m=.003):
    """Split only abstraction-induced robot collisions; never delete points.

    A primitive is refined when its inflated AABB intersects exact planning
    spheres while every observed source point remains outside those spheres.
    A genuine point-level collision is retained unchanged and reported.
    """
    points = np.asarray(points_body_m, dtype=float); output=[]; records=[]
    for primitive in report["primitives"]:
        low, high = map(np.asarray, primitive["observed_bounds_m"])
        member = points[np.all((points >= low - 1e-9) & (points <= high + 1e-9), axis=1)]
        aabb_gap = min(_aabb_sphere_gap(low, high, sphere, primitive["inflation_m"])
                       for sphere in robot_owned.spheres)
        point_gap = min(float(np.min(np.linalg.norm(member - np.asarray(sphere.center_body_m), axis=1)
                                      - sphere.radius_m))
                        for sphere in robot_owned.spheres) if len(member) else float("inf")
        if aabb_gap >= 0 or point_gap <= 0:
            output.append(primitive)
            if point_gap <= 0:
                records.append({"primitive_id": primitive["primitive_id"],
                                "decision": "RETAIN_GENUINE_POINT_COLLISION",
                                "aabb_gap_m": aabb_gap, "point_gap_m": point_gap})
            continue
        origin = member.min(axis=0)
        keys = np.floor((member - origin) / cell_m).astype(int)
        children=[]
        for serial, key in enumerate(sorted(set(map(tuple, keys.tolist())))):
            child_points = member[np.all(keys == np.asarray(key), axis=1)]
            child_low, child_high = _bounds(child_points)
            dims = np.maximum(child_high - child_low, .004)
            child = dict(primitive)
            child.update({"primitive_id": "%s_refined_%03d" % (primitive["primitive_id"], serial),
                          "point_count": int(len(child_points)),
                          "center_m": ((child_low + child_high) / 2).tolist(),
                          "dims_m": dims.tolist(), "inflation_m": inflation_m,
                          "observed_bounds_m": [child_low.tolist(), child_high.tolist()],
                          "refinement": "AABB_EMPTY_VOLUME_BRIDGE against exact planning spheres"})
            children.append(child)
        output.extend(children)
        records.append({"primitive_id": primitive["primitive_id"],
                        "decision": "SPLIT_NO_POINT_DELETION", "aabb_gap_m": aabb_gap,
                        "point_gap_m": point_gap, "child_count": len(children)})
    updated = dict(report);updated["primitives"] = output
    updated["multi_primitive_count"] = len(output)
    updated["multi_primitive_occupied_volume_m3"] = sum(
        float(np.prod(item["dims_m"])) for item in output)
    old_volume = updated["old_single_aabb_occupied_volume_m3"]
    updated["occupied_volume_ratio"] = (updated["multi_primitive_occupied_volume_m3"] /
                                        old_volume if old_volume else None)
    updated["robot_adjacent_refinement"] = {
        "cell_m": cell_m, "inflation_m": inflation_m,
        "policy": "split abstraction collision only; retain point-level collision",
        "records": records}
    return updated
