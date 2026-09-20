"""Camera cloud -> ATOM obstacle cuboids, with the provenance made explicit.

The 2026-09-17 pipeline ran these stages as a demo and had to be discarded
because the transform underneath it was ambiguous. Now that ``T_body_camera`` is
commissioned the stages can be real, but two of them cannot be trusted by
construction and have to say so rather than quietly produce plausible boxes:

* the self-filter is only meaningful if the robot spheres describe the arm pose
  *at the moment of capture*, so a joint mismatch is a refusal and not a warning;
* the geometry to filter is still incomplete (chassis, grippers, payload), so the
  filter reports exactly which parts it covered and a caller that proceeds
  anyway gets that recorded in the snapshot.

Nothing here talks to a device or a planner. Everything returns counts so the
next stage can be audited against this one.
"""

import math
from typing import Mapping, Sequence

import numpy as np

#: Parts the site pipeline declares as required before a self-filter can be
#: called complete. Kept as data so the report can name what is absent.
REQUIRED_SELF_FILTER_PARTS = ("chassis", "left_arm", "right_arm", "left_gripper",
                              "right_gripper", "active_tool", "attached_object")


def _points(value, label):
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("%s must be an (n, 3) array" % label)
    return array


def crop_roi(points, low, high):
    """Keep the manipulation volume. Returns the kept points and the counts."""
    array = _points(points, "points")
    low = np.asarray(low, dtype=float)
    high = np.asarray(high, dtype=float)
    if low.shape != (3,) or high.shape != (3,):
        raise ValueError("ROI bounds must be three-vectors")
    if np.any(high <= low):
        raise ValueError("ROI max must exceed min on every axis")
    kept = array[np.all((array >= low) & (array <= high), axis=1)]
    return kept, dict(stage="roi", before=int(len(array)), after=int(len(kept)),
                      bounds_m=[low.tolist(), high.tolist()])


def self_filter(points, spheres, margin_m=0.025):
    """Drop points inside any robot sphere plus a margin.

    The margin makes the removal conservative in the direction that matters: a
    point just outside the modelled surface is dropped too, so an under-modelled
    arm cannot leave a shell of its own skin behind as a fake obstacle.
    """
    array = _points(points, "points")
    if not spheres:
        raise ValueError("self-filter needs at least one sphere; an empty filter "
                         "would silently disable it")
    margin = float(margin_m)
    if not math.isfinite(margin) or margin < 0.0:
        raise ValueError("margin must be finite and non-negative")
    keep = np.ones(len(array), dtype=bool)
    nearest = np.full(len(array), np.inf)
    for sphere in spheres:
        centre = np.asarray(sphere["center_body_m"], dtype=float)
        radius = float(sphere["radius_m"])
        if centre.shape != (3,) or not math.isfinite(radius) or radius <= 0.0:
            raise ValueError("each sphere needs a finite centre and a positive radius")
        gap = np.linalg.norm(array - centre, axis=1) - radius
        nearest = np.minimum(nearest, gap)
        keep &= gap > margin
    removed = ~keep
    return array[keep], dict(
        stage="self_filter", before=int(len(array)), after=int(len(array) - np.count_nonzero(removed)),
        removed=int(np.count_nonzero(removed)), sphere_count=len(spheres), margin_m=margin,
        removed_gap_m=dict(min=float(nearest[removed].min()) if removed.any() else None,
                           median=float(np.median(nearest[removed])) if removed.any() else None,
                           max=float(nearest[removed].max()) if removed.any() else None))


def remove_support(points, top_z_m, half_band_m=0.035):
    """Drop the support surface itself, which is modelled as a known cuboid."""
    array = _points(points, "points")
    band = abs(float(half_band_m))
    if not math.isfinite(float(top_z_m)) or not math.isfinite(band) or band <= 0.0:
        raise ValueError("support height and band must be finite, with a positive band")
    keep = np.abs(array[:, 2] - float(top_z_m)) > band
    return array[keep], dict(stage="support_removal", before=int(len(array)),
                             after=int(len(array) - np.count_nonzero(~keep)),
                             removed=int(np.count_nonzero(~keep)),
                             support_top_m=float(top_z_m), half_band_m=band)


def aabb_from_points(points, inflation_m, min_points, max_volume_m3=1.0):
    """One inflated cuboid per cluster, or None when the cluster is not usable."""
    array = _points(points, "points")
    if len(array) < int(min_points):
        return None
    low = array.min(axis=0) - float(inflation_m)
    high = array.max(axis=0) + float(inflation_m)
    dimensions = high - low
    if float(np.prod(np.maximum(dimensions, 1e-3))) > float(max_volume_m3):
        return None  # a floor or background remnant, not an object
    return dict(point_count=int(len(array)), min_m=low.tolist(), max_m=high.tolist(),
                center_m=((low + high) / 2.0).tolist(), dims_m=dimensions.tolist(),
                inflation_m=float(inflation_m))


def support_slab(low_xy, high_xy, top_z_m, thickness_m):
    """The known support as a cuboid whose top face is the fitted surface.

    The plane is the physical *top* of the table, so extending the box above it
    would invent occupied space the robot may legitimately move through.
    """
    low = np.asarray(low_xy, dtype=float)
    high = np.asarray(high_xy, dtype=float)
    if low.shape != (2,) or high.shape != (2,):
        raise ValueError("support extents must be two-vectors")
    thickness = abs(float(thickness_m))
    if thickness <= 0.0:
        raise ValueError("support thickness must be positive")
    top = float(top_z_m)
    box_low = [float(low[0]), float(low[1]), top - thickness]
    box_high = [float(high[0]), float(high[1]), top]
    return dict(min_m=box_low, max_m=box_high,
                center_m=[(a + b) / 2.0 for a, b in zip(box_low, box_high)],
                dims_m=[b - a for a, b in zip(box_low, box_high)])


def joint_state_matches(captured_rad, live_rad, tolerance_rad=1e-3):
    """Whether a robot geometry file still describes the arm as it was captured.

    Spheres from an earlier pose would carve holes in the wrong place, so this is
    a gate rather than a diagnostic.
    """
    captured = np.asarray(captured_rad, dtype=float)
    live = np.asarray(live_rad, dtype=float)
    if captured.shape != live.shape or not np.isfinite(captured).all() \
            or not np.isfinite(live).all():
        raise ValueError("both joint states must be finite vectors of equal length")
    worst = float(np.max(np.abs(captured - live)))
    return worst <= float(tolerance_rad), worst


def self_filter_completeness(declared_parts):
    """Which required parts a self-filter actually covers."""
    declared = set(str(part) for part in declared_parts)
    missing = [part for part in REQUIRED_SELF_FILTER_PARTS if part not in declared]
    return dict(declared=sorted(declared), missing=missing,
                complete=not missing)


def scene_object_specs(support, boxes, observation_id):
    """SceneObject argument tuples, so the world package stays the only writer."""
    specs = [dict(identifier="known_support_table", role="FIXED", shape="cuboid",
                  center_m=support["center_m"], dims_m=support["dims_m"],
                  inflation_m=0.0, source_observation_id=observation_id)]
    for index, box in enumerate(boxes):
        specs.append(dict(identifier="unknown_residual_%03d" % index, role="OBSTACLE",
                          shape="cuboid", center_m=box["center_m"], dims_m=box["dims_m"],
                          inflation_m=float(box["inflation_m"]),
                          source_observation_id=observation_id))
    return specs
