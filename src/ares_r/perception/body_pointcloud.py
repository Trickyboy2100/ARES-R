"""Canonical Pixel Pro CAMERA/mm to ARES-R BODY/m point-cloud path.

The commissioned transform is immutable input.  This module never estimates,
fits, or adjusts camera extrinsics and deliberately contains no self-filter or
planning code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

import numpy as np

from ..epic_pointcloud import capture as capture_epic


@dataclass(frozen=True)
class BodyPointCloud:
    points_body_m: np.ndarray
    colors_rgb: np.ndarray
    source_ply: str
    source_sha256: str
    source_frame: str
    source_unit: str
    frame: str
    unit: str
    transform_revision: str
    validation_revision: str
    T_body_camera: np.ndarray
    raw_point_count: int
    valid_point_count: int
    timings_s: dict


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_epic_ply_camera_mm(path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load Epic's binary XYZ-float/RGB-byte PLY without changing its units."""
    path = Path(path)
    with path.open("rb") as stream:
        header = []
        for _ in range(128):
            line = stream.readline()
            if not line:
                raise ValueError("truncated PLY header")
            header.append(line)
            if line == b"end_header\n":
                break
        else:
            raise ValueError("PLY header too long")
        text = b"".join(header).decode("ascii")
        if "format binary_little_endian 1.0" not in text:
            raise ValueError("Epic binary little-endian PLY required")
        match = re.search(r"^element vertex (\d+)$", text, re.MULTILINE)
        if not match:
            raise ValueError("PLY vertex count missing")
        count = int(match.group(1))
        expected = ("property float x", "property float y", "property float z",
                    "property uchar red", "property uchar green", "property uchar blue")
        if not all(item in text for item in expected):
            raise ValueError("expected XYZ float32 + RGB uint8 PLY")
        record = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                           ("r", "u1"), ("g", "u1"), ("b", "u1")])
        values = np.fromfile(stream, dtype=record, count=count)
    if len(values) != count:
        raise ValueError("truncated PLY payload")
    points = np.column_stack((values["x"], values["y"], values["z"]))
    colors = np.column_stack((values["r"], values["g"], values["b"]))
    return points, colors, {"vertex_count": count, "sha256": _sha256(path)}


def transform_camera_mm_to_body(points_camera_mm: np.ndarray,
                                colors_rgb: np.ndarray,
                                config: dict, *, source_ply: str = "",
                                source_sha256: str = "",
                                load_s: float = 0.0) -> BodyPointCloud:
    """Remove invalid CAMERA/mm points, convert once to metres, then apply SE(3)."""
    started = time.perf_counter()
    points = np.asarray(points_camera_mm)
    colors = np.asarray(colors_rgb)
    if points.ndim != 2 or points.shape[1] != 3 or colors.shape != points.shape:
        raise ValueError("points and RGB colors must both be shaped (n, 3)")
    section = config["epic_pointcloud"]
    if section.get("source_coordinate_unit") != "mm":
        raise ValueError("canonical input unit must be explicit mm")
    validation = section.get("T_body_camera_validation", {})
    if validation.get("state") != "COMMISSIONED":
        raise RuntimeError("T_body_camera is not COMMISSIONED")
    transform = np.asarray(section.get("T_body_camera"), dtype=np.float64)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("finite 4x4 T_body_camera required")
    invalid_started = time.perf_counter()
    valid = np.isfinite(points).all(axis=1) & np.any(points != 0.0, axis=1)
    clean_mm = points[valid].astype(np.float64, copy=False)
    clean_colors = colors[valid].astype(np.float64, copy=False) / 255.0
    invalid_s = time.perf_counter() - invalid_started
    transform_started = time.perf_counter()
    camera_m = clean_mm * 0.001
    body = camera_m @ transform[:3, :3].T + transform[:3, 3]
    transform_s = time.perf_counter() - transform_started
    return BodyPointCloud(
        points_body_m=body.astype(np.float32), colors_rgb=clean_colors.astype(np.float32),
        source_ply=str(source_ply), source_sha256=str(source_sha256),
        source_frame="CAMERA", source_unit="mm", frame="BODY", unit="m",
        transform_revision=str(section["T_body_camera_revision"]),
        validation_revision=str(validation["validation_revision"]),
        T_body_camera=transform, raw_point_count=int(len(points)),
        valid_point_count=int(len(body)),
        timings_s={"load": float(load_s), "invalid_removal": invalid_s,
                   "unit_and_rigid_transform": transform_s,
                   "canonical_total": time.perf_counter() - started + float(load_s)},
    )


def build_body_cloud(path: Path, config: dict) -> BodyPointCloud:
    started = time.perf_counter()
    points, colors, source = load_epic_ply_camera_mm(path)
    load_s = time.perf_counter() - started
    return transform_camera_mm_to_body(points, colors, config, source_ply=str(Path(path).resolve()),
                                       source_sha256=source["sha256"], load_s=load_s)


def fit_support_table(cloud: BodyPointCloud, expected_z_m: float = 0.750,
                      search_half_width_m: float = 0.10,
                      inlier_half_width_m: float = 0.012) -> dict:
    """Validate the fixed transform with a horizontal table; never alter it."""
    started = time.perf_counter()
    points = np.asarray(cloud.points_body_m, dtype=np.float64)
    candidates = points[np.abs(points[:, 2] - expected_z_m) <= search_half_width_m]
    if len(candidates) < 100:
        raise ValueError("too few points near expected table height")
    edges = np.arange(expected_z_m - search_half_width_m,
                      expected_z_m + search_half_width_m + 0.0025, 0.0025)
    counts, edges = np.histogram(candidates[:, 2], bins=edges)
    peak = float((edges[int(np.argmax(counts))] + edges[int(np.argmax(counts)) + 1]) / 2.0)
    inliers = candidates[np.abs(candidates[:, 2] - peak) <= inlier_half_width_m]
    sample = inliers[::max(1, len(inliers) // 200000)]
    centre = sample.mean(axis=0)
    _, _, vectors = np.linalg.svd(sample - centre, full_matrices=False)
    normal = vectors[-1]
    if normal[2] < 0.0:
        normal = -normal
    distances = (sample - centre) @ normal
    tilt = float(np.degrees(np.arccos(np.clip(normal[2], -1.0, 1.0))))
    return {
        "expected_table_z_m": expected_z_m,
        "mean_z_m": float(inliers[:, 2].mean()),
        "median_z_m": float(np.median(inliers[:, 2])),
        "height_error_mm": float((np.median(inliers[:, 2]) - expected_z_m) * 1000.0),
        "normal_body": normal.tolist(), "normal_to_body_up_deg": tilt,
        "rms_plane_mm": float(np.sqrt(np.mean(distances * distances)) * 1000.0),
        "inlier_count": int(len(inliers)),
        "xy_bounds_m": [[float(inliers[:, 0].min()), float(inliers[:, 1].min())],
                         [float(inliers[:, 0].max()), float(inliers[:, 1].max())]],
        "fit_elapsed_s": time.perf_counter() - started,
        "method": "BODY z histogram near known 0.750 m followed by PCA; validation only",
    }


def _metadata(cloud: BodyPointCloud, table: dict, npz_path: Path) -> dict:
    return {
        "schema_version": 1, "kind": "canonical_body_pointcloud",
        "frame": cloud.frame, "unit": cloud.unit,
        "source": {"path": cloud.source_ply, "sha256": cloud.source_sha256,
                   "frame": cloud.source_frame, "unit": cloud.source_unit},
        "raw_point_count": cloud.raw_point_count,
        "valid_point_count": cloud.valid_point_count,
        "T_body_camera": cloud.T_body_camera.tolist(),
        "transform_revision": cloud.transform_revision,
        "validation_revision": cloud.validation_revision,
        "timings_s": cloud.timings_s, "table_validation": table,
        "artifact_npz": str(npz_path.resolve()),
        "pipeline": ["CAMERA/mm raw", "remove invalid", "mm->m exactly once",
                     "fixed commissioned T_body_camera", "BODY/m"],
        "extrinsic_estimation": "NONE", "self_filter": "NOT_RUN",
        "curobo": "NOT_RUN",
    }


def save_artifact(cloud: BodyPointCloud, table: dict, directory: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    npz_path = directory / "body_cloud.npz"
    np.savez_compressed(npz_path, points_body_m=cloud.points_body_m,
                        colors_rgb=cloud.colors_rgb, T_body_camera=cloud.T_body_camera)
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps(_metadata(cloud, table, npz_path), indent=2) + "\n",
                        encoding="utf-8")
    return manifest

def load_artifact(manifest_path: Path) -> tuple[BodyPointCloud, dict]:
    manifest_path = Path(manifest_path)
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    values = np.load(metadata["artifact_npz"])
    cloud = BodyPointCloud(
        points_body_m=values["points_body_m"], colors_rgb=values["colors_rgb"],
        source_ply=metadata["source"]["path"], source_sha256=metadata["source"]["sha256"],
        source_frame=metadata["source"]["frame"], source_unit=metadata["source"]["unit"],
        frame=metadata["frame"], unit=metadata["unit"],
        transform_revision=metadata["transform_revision"],
        validation_revision=metadata["validation_revision"],
        T_body_camera=values["T_body_camera"], raw_point_count=metadata["raw_point_count"],
        valid_point_count=metadata["valid_point_count"], timings_s=metadata["timings_s"])
    return cloud, metadata


def artifact_root(config: dict) -> Path:
    return Path(config["logging"]["directory"]) / "body_cloud"


def latest_manifest(config: dict) -> Path:
    pointer = artifact_root(config) / "latest.json"
    if not pointer.is_file():
        raise FileNotFoundError("no BODY cloud artifact; run scene body-cloud capture")
    target = Path(json.loads(pointer.read_text(encoding="utf-8"))["manifest"])
    if not target.is_file():
        raise FileNotFoundError("BODY cloud latest pointer is stale: %s" % target)
    return target


def capture_body_cloud(config: dict) -> Path:
    """One camera scan followed by the canonical transform; no other device I/O."""
    root = artifact_root(config)
    capture_manifest = capture_epic(config, root / "captures")
    capture_data = json.loads(capture_manifest.read_text(encoding="utf-8"))
    cloud = build_body_cloud(capture_manifest.parent / "pointcloud.ply", config)
    table = fit_support_table(cloud)
    run_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    manifest = save_artifact(cloud, table, root / "artifacts" / run_id)
    pointer = root / "latest.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({"manifest": str(manifest.resolve()),
                                   "capture_manifest": str(capture_manifest.resolve()),
                                   "camera_capture_elapsed_s": capture_data.get("elapsed_s")}, indent=2) + "\n")
    return manifest
