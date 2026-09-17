#!/usr/bin/env python3.11
"""Memory-only Pixel Pro -> SceneSnapshot/SceneCompiler latency benchmark.

Only the final aggregate JSON is written.  No EpicRaw, PLY, PNG, or per-frame
JSON is materialised, so debug/evidence I/O is excluded from the measurement.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import epiceye

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ares_r.world import (
    CalibrationSet, PointCloudRef, PoseSE3, RobotState, SceneObject,
    SceneObjectRole, WorldModel, compile_snapshot,
)


def rigid(xyz, rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    value = np.eye(4)
    value[:3, :3] = [
        [cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
        [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr+cy*sr],
        [-sp, cp*sr, cp*cr],
    ]
    value[:3, 3] = xyz
    return value


def capsule(a, b, radius, spacing=.045):
    a, b = np.asarray(a), np.asarray(b)
    count = max(2, int(math.ceil(np.linalg.norm(b-a)/spacing))+1)
    return [(a+(b-a)*fraction, radius) for fraction in np.linspace(0, 1, count)]


def percentile(values, q):
    return float(np.percentile(np.asarray(values, dtype=float), q))


def summarize(values):
    values = [float(value) for value in values]
    p50 = percentile(values, 50)
    return {
        "count": len(values), "mean_ms": statistics.fmean(values), "p50_ms": p50,
        "p90_ms": percentile(values, 90), "p95_ms": percentile(values, 95),
        "max_ms": max(values), "hz_from_p50": 1000.0/p50 if p50 else None,
    }


def voxelize(points, size):
    keys = np.floor(points / size).astype(np.int32)
    _, indices = np.unique(keys, axis=0, return_index=True)
    return points[np.sort(indices)]


def connected_aabbs(points, cell_size=.035, min_points=10, inflation=.025):
    """Fast deterministic occupied-cell connected components; no sklearn I/O."""
    cells = np.floor(points/cell_size).astype(np.int32)
    buckets = {}
    for index, cell in enumerate(map(tuple, cells)):
        buckets.setdefault(cell, []).append(index)
    remaining = set(buckets)
    boxes = []
    neighbours = [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)]
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        indices = []
        while stack:
            cell = stack.pop()
            indices.extend(buckets[cell])
            for delta in neighbours:
                candidate = (cell[0]+delta[0], cell[1]+delta[1], cell[2]+delta[2])
                if candidate in remaining:
                    remaining.remove(candidate)
                    stack.append(candidate)
        if len(indices) < min_points:
            continue
        group = points[np.asarray(indices)]
        low, high = group.min(0)-inflation, group.max(0)+inflation
        if np.prod(np.maximum(high-low, .001)) > 1.0:
            continue
        boxes.append((low, high, len(indices)))
    return boxes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="192.168.99.199:5000")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--robot-geometry", type=Path, required=True)
    parser.add_argument("--robot-state", type=Path, required=True)
    parser.add_argument("--robot-world", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--pointcloud-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 3 or args.frames < 20:
        raise ValueError("work order requires >=3 warm-up and >=20 measured frames")
    calibration = json.loads(args.calibration.read_text())
    if calibration["state"] != "DEMO_ONLY_UNCOMMISSIONED" or calibration["execution_allowed"] is not False:
        raise RuntimeError("demo-only execution-blocked calibration required")
    geometry = json.loads(args.robot_geometry.read_text())
    saved = json.loads(args.robot_state.read_text()).get("arms")
    world = json.loads(args.robot_world.read_text())
    tools = json.loads(args.tools.read_text())
    point_cfg = json.loads(args.pointcloud_config.read_text())
    transform = np.asarray(calibration["T_body_camera"], dtype=float)
    calibration_revision = "DEMO_ONLY:" + hashlib.sha256(args.calibration.read_bytes()).hexdigest()
    table_z = float(calibration["support_height_body_m"])
    roi = point_cfg["roi_candidates"]["global"]
    low, high = np.asarray(roi["min_m"]), np.asarray(roi["max_m"])

    spheres = [(np.asarray(item["center_body_m"]), float(item["radius_m"])) for item in geometry["spheres"]]
    right_base = rigid(world["arms"]["right"]["base_xyz_m"], world["arms"]["right"]["base_rpy_rad"])
    right_tcp = (right_base @ np.r_[np.asarray(saved["right"]["tcp_position_mm_rad"][:3])/1000, 1])[:3]
    anchor = min(spheres, key=lambda item: np.linalg.norm(item[0]-right_tcp))[0]
    spheres.extend(capsule(anchor, right_tcp, .055))
    left_base = rigid(world["arms"]["left"]["base_xyz_m"], world["arms"]["left"]["base_rpy_rad"])
    left_tcp = (left_base @ np.r_[np.asarray(saved["left"]["tcp_position_mm_rad"][:3])/1000, 1])[:3]
    spheres.extend(capsule(world["arms"]["left"]["base_xyz_m"], left_tcp, .11))

    def acquire_and_process(commit):
        timings = {}
        total_at = time.perf_counter()
        at = time.perf_counter(); frame_id = epiceye.trigger_frame(args.ip, pointcloud=True); timings["camera_trigger_ms"] = (time.perf_counter()-at)*1000
        if not frame_id: raise RuntimeError("trigger_frame failed")
        at = time.perf_counter(); raw = epiceye.get_frame_in_epicraw(args.ip, frame_id); timings["frame_fetch_ms"] = (time.perf_counter()-at)*1000
        if raw is None: raise RuntimeError("get_frame_in_epicraw failed")
        at = time.perf_counter(); document = epiceye.try_load_epic_raw_document_from_bytes(raw); timings["epicraw_decode_ms"] = (time.perf_counter()-at)*1000
        if document is None: raise RuntimeError("EpicRaw document decode failed")
        at = time.perf_counter(); points, width, height = epiceye.decode_point_cloud_from_epicraw(document); camera = np.asarray(points, dtype=float).reshape(-1, 3); camera = camera[np.isfinite(camera).all(1)&(np.abs(camera).sum(1)>0)]/1000; timings["pointcloud_build_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); body = (np.c_[camera, np.ones(len(camera))] @ transform.T)[:, :3]; timings["camera_to_body_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); body = body[np.all((body>=low)&(body<=high), axis=1)]; timings["roi_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); keep = np.ones(len(body), dtype=bool)
        for center, radius in spheres:
            keep &= np.linalg.norm(body-center, axis=1) > radius+.025
        filtered = body[keep]; timings["self_filter_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); residual = filtered[np.abs(filtered[:, 2]-table_z)>.035]; timings["support_remove_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); voxel = voxelize(residual, .01); timings["voxel_ms"] = (time.perf_counter()-at)*1000
        at = time.perf_counter(); boxes = connected_aabbs(voxel); timings["cluster_aabb_ms"] = (time.perf_counter()-at)*1000
        counts = {"camera_valid": len(camera), "roi": len(body), "self_filtered": len(filtered), "residual": len(residual), "voxel": len(voxel), "aabbs": len(boxes)}
        if commit:
            wall, monotonic = time.time_ns(), time.monotonic_ns()
            model = WorldModel(runtime_id="FAST_"+hashlib.sha256(str(frame_id).encode()).hexdigest()[:16], snapshot_ttl_s=60, environment_ttl_s=60)
            state = RobotState(wall, monotonic, model.runtime_id, left_joints_rad=tuple(saved["left"]["joint_position_rad"]), right_joints_rad=tuple(saved["right"]["joint_position_rad"]), source_revisions=(("scope", "DEMO_OFFLINE_ONLY"),))
            model.update_robot_state(state)
            observation = model.begin_observation("OBS_"+str(frame_id), wall, monotonic)
            cloud_ref = PointCloudRef(str(frame_id), hashlib.sha256(raw).hexdigest(), "body_demo_candidate")
            model.register_pointcloud(observation, cloud_ref)
            objects = []
            table_low, table_high = np.array([low[0], low[1], table_z-.05]), np.array([high[0], high[1], table_z])
            objects.append(SceneObject("known_support_table", SceneObjectRole.FIXED, "cuboid", PoseSE3("body", tuple((table_low+table_high)/2), (1,0,0,0)), tuple(table_high-table_low), 0, observation))
            for index, (box_low, box_high, _) in enumerate(boxes):
                objects.append(SceneObject("unknown_%03d"%index, SceneObjectRole.OBSTACLE, "cuboid", PoseSE3("body", tuple((box_low+box_high)/2), (1,0,0,0)), tuple(box_high-box_low), .025, observation))
            at = time.perf_counter(); model.register_obstacles(observation, objects, cloud_ref.pointcloud_id, cloud_ref.sha256); model.register_calibration(observation, CalibrationSet((("T_body_camera", calibration_revision), ("planning_scope", "DEMO_OFFLINE_ONLY")))); model.commit_observation(observation); snapshot = model.freeze_snapshot(geometry["robot_model_sha256"], tools["arms"]["right"]["revision"]); timings["world_commit_ms"] = (time.perf_counter()-at)*1000
            at = time.perf_counter(); compiled = compile_snapshot(snapshot, "right", geometry["T_body_model"]); timings["scene_compile_ms"] = (time.perf_counter()-at)*1000
            counts.update(scene_snapshot_id=snapshot.snapshot_id, scene_digest=compiled["digest"])
        timings["perception_scene_total_ms"] = (time.perf_counter()-total_at)*1000
        return timings, counts

    for _ in range(args.warmup):
        acquire_and_process(False)
    samples, counts = [], []
    for _ in range(args.frames):
        timing, count = acquire_and_process(True)
        samples.append(timing); counts.append(count)
    fields = sorted(samples[0])
    report = {
        "schema_version": 1, "mode": "FAST_MEMORY_ONLY", "execution_allowed": False,
        "camera": args.ip, "warmup_frames": args.warmup, "measured_frames": args.frames,
        "calibration_revision": calibration_revision,
        "timing": {field: summarize([sample[field] for sample in samples]) for field in fields},
        "point_counts_last": counts[-1], "raw_samples_ms": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "perception_scene_total": report["timing"]["perception_scene_total_ms"]}, indent=2))


if __name__ == "__main__":
    main()
