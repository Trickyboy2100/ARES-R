"""Conservative BODY residual-cloud cleanup and deterministic AABB extraction.

This module consumes an already self-filtered cloud.  It never estimates camera
extrinsics and never accesses hardware.  Small obstacles are retained unless
they fail both local-density and minimum connected-voxel evidence.
"""

from dataclasses import dataclass
import time

import numpy as np


@dataclass(frozen=True)
class CleanupProfile:
    name: str
    method: str
    radius_m: float = 0.0
    min_neighbors: int = 0
    statistical_neighbors: int = 0
    statistical_std_ratio: float = 0.0
    voxel_m: float = 0.005
    cluster_tolerance_m: float = 0.012
    cluster_min_points: int = 8
    minimum_cluster_voxels: int = 12


PROFILES = (
    CleanupProfile("radius_3_18mm", "radius", 0.018, 3),
    CleanupProfile("radius_4_20mm", "radius", 0.020, 4),
    CleanupProfile("statistical_16_2p5", "statistical",
                   statistical_neighbors=16, statistical_std_ratio=2.5),
)
DEFAULT_PROFILE = "radius_4_20mm"


def workspace_crop(points, roi, table_z_m=0.750, table_half_band_m=0.040):
    points = np.asarray(points, dtype=float)
    low, high = np.asarray(roi[0], dtype=float), np.asarray(roi[1], dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or low.shape != (3,) or high.shape != (3,):
        raise ValueError("BODY points and a 3-D ROI are required")
    in_roi = np.all((points >= low) & (points <= high), axis=1)
    outside_table = np.abs(points[:, 2] - float(table_z_m)) > float(table_half_band_m)
    return in_roi & outside_table


def _cloud(points):
    import open3d as o3d
    return o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.asarray(points, dtype=float)))


def _filter(voxel_cloud, profile):
    if profile.method == "radius":
        _, indices = voxel_cloud.remove_radius_outlier(
            nb_points=profile.min_neighbors, radius=profile.radius_m)
    elif profile.method == "statistical":
        _, indices = voxel_cloud.remove_statistical_outlier(
            nb_neighbors=profile.statistical_neighbors,
            std_ratio=profile.statistical_std_ratio)
    else:
        raise ValueError("unknown cleanup method %r" % profile.method)
    return np.asarray(indices, dtype=int)


def _bounds(points):
    if not len(points):
        return {"point_count": 0, "min_m": None, "max_m": None,
                "center_m": None, "dims_m": None}
    low, high = points.min(axis=0), points.max(axis=0)
    return {"point_count": int(len(points)), "min_m": low.tolist(), "max_m": high.tolist(),
            "center_m": ((low + high) / 2.0).tolist(), "dims_m": (high - low).tolist()}


def clean_and_cluster(points_body_m, roi, profile, table_z_m=0.750,
                      table_half_band_m=0.040, box_bounds=None):
    """Return retained cluster voxels, AABBs and auditable stage metrics."""
    started = time.perf_counter(); points = np.asarray(points_body_m, dtype=float)
    selected = workspace_crop(points, roi, table_z_m, table_half_band_m)
    residual = points[selected]
    crop_s = time.perf_counter()
    voxel_cloud = _cloud(residual).voxel_down_sample(profile.voxel_m)
    voxel_points = np.asarray(voxel_cloud.points)
    voxel_s = time.perf_counter()
    kept_indices = _filter(voxel_cloud, profile)
    filtered = voxel_points[kept_indices]
    outlier_s = time.perf_counter()
    clustered = _cloud(filtered)
    labels = np.asarray(clustered.cluster_dbscan(
        eps=profile.cluster_tolerance_m,
        min_points=profile.cluster_min_points,
        print_progress=False), dtype=int)
    cluster_s = time.perf_counter()
    kept = np.zeros(len(filtered), dtype=bool); boxes = []; rejected = []
    for label in sorted(set(labels.tolist()) - {-1}):
        member = filtered[labels == label]
        record = _bounds(member); record["label"] = int(label)
        if len(member) < profile.minimum_cluster_voxels:
            rejected.append(record); continue
        kept[labels == label] = True
        record["object_id"] = "residual_%03d" % label
        boxes.append(record)
    clean = filtered[kept]
    box_report = None
    if box_bounds is not None:
        low, high = np.asarray(box_bounds[0]), np.asarray(box_bounds[1])
        before = voxel_points[np.all((voxel_points >= low) & (voxel_points <= high), axis=1)]
        after = clean[np.all((clean >= low) & (clean <= high), axis=1)]
        before_bounds, after_bounds = _bounds(before), _bounds(after)
        before_dims = np.asarray(before_bounds["dims_m"]) if len(before) else np.full(3, np.nan)
        after_dims = np.asarray(after_bounds["dims_m"]) if len(after) else np.full(3, np.nan)
        box_report = {"before": before_bounds, "after": after_bounds,
                      "point_retention_ratio": float(len(after) / max(1, len(before))),
                      "aabb_change_mm": ((after_dims-before_dims)*1000.0).tolist()}
    metrics = {
        "profile": profile.__dict__, "input_points": int(len(points)),
        "workspace_non_table_points": int(len(residual)), "voxel_points": int(len(voxel_points)),
        "density_removed": int(len(voxel_points)-len(filtered)),
        "cluster_noise_points": int(np.sum(labels < 0)),
        "small_cluster_removed": int(len(filtered)-np.sum(labels < 0)-np.sum(kept)),
        "clean_points": int(len(clean)), "kept_clusters": int(len(boxes)),
        "rejected_clusters": int(len(rejected)), "box_holdout": box_report,
        "timing_s": {"crop_table": crop_s-started, "voxel": voxel_s-crop_s,
                     "outlier_cleanup": outlier_s-voxel_s,
                     "cluster_aabb": time.perf_counter()-outlier_s,
                     "total": time.perf_counter()-started}}
    return clean, boxes, metrics
