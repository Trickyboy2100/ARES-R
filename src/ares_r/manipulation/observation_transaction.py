"""Atomic Epic detection + Pixel Pro scene + read-only robot-state binding."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Callable, Mapping

from ..world_geometry import base_tcp_to_world


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def detection_dict(detection) -> dict:
    pose = None if detection.pose is None else {
        "frame_id": detection.pose.frame_id, "values": detection.pose.values()}
    return {
        "schema_version": 1, "success": bool(detection.success),
        "request_id": str(detection.request_id), "kind": str(detection.kind),
        "timestamp": float(detection.timestamp), "pose": pose,
        "candidates": [{"frame_id": item.frame_id, "values": item.values()}
                       for item in detection.candidates],
        "raw_response": detection.raw_response, "error": detection.error,
        "meta": dict(detection.meta),
    }


def _joints(state: Mapping[str, object], side: str):
    value = state[side]
    if "diagnostics" in value:
        value = value["diagnostics"]
    joints = tuple(float(item) for item in value["joint_position_rad"])
    if len(joints) != 6 or not all(math.isfinite(item) for item in joints):
        raise RuntimeError("%s read-only state is not six finite joints" % side)
    return joints


class ManipulationObservationTransaction:
    """Create one immutable epoch; partial detection/cloud results never commit."""

    SCHEMA_VERSION = 1

    def __init__(self, config: Mapping[str, object], *, detect: Callable,
                 read_robot_state: Callable, scene_builder: Callable,
                 clock: Callable[[], float] = time.time,
                 joint_stability_rad: float = math.radians(.25)) -> None:
        self.config = config
        self.detect = detect
        self.read_robot_state = read_robot_state
        self.scene_builder = scene_builder
        self.clock = clock
        self.joint_stability_rad = float(joint_stability_rad)

    def capture(self, destination: Path, *, profile: str = "right_pick") -> dict:
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError("refusing to overwrite manipulation observation")
        destination.mkdir(parents=True)
        started = self.clock()
        before = self.read_robot_state("before")
        detection = self.detect(profile)
        serialized = detection_dict(detection)
        detection_path = destination / "epic_5700_detection.json"
        _atomic_json(detection_path, serialized)
        if not detection.success or detection.pose is None:
            raise RuntimeError("Epic detection failed; pointcloud transaction not committed")
        meta = detection.meta
        if profile != "right_pick" or meta.get("epic_profile") != "right_pick":
            raise RuntimeError("P3.8 first demo requires the commissioned right_pick profile")
        if meta.get("profile_state") != "COMMISSIONED":
            raise RuntimeError("right_pick Epic profile is not commissioned")
        scene = self.scene_builder(self.config, destination / "live_scene",
                                   active_arm="right",
                                   detection_artifact=detection_path)
        after = self.read_robot_state("after")
        maximum_delta = max(abs(a-b) for side in ("left", "right")
                            for a, b in zip(_joints(before, side), _joints(after, side)))
        if maximum_delta > self.joint_stability_rad:
            raise RuntimeError("robot moved during manipulation observation epoch")
        snapshot_path = Path(scene["scene_dir"]) / "scene/snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        epoch = snapshot["environment"]["observation"]
        if serialized["request_id"] not in epoch.get("detection_ids", []):
            raise RuntimeError("Epic detection was not registered in SceneSnapshot epoch")
        if epoch["pointcloud"]["sha256"] != scene["pointcloud_sha256"]:
            raise RuntimeError("pointcloud provenance differs inside the transaction")
        world = json.loads(Path("config/robot_world.json").read_text(encoding="utf-8"))
        pose = detection.pose.values()
        body_pose = base_tcp_to_world(world["arms"]["right"],
                                      [value * 1000.0 for value in pose[:3]] + pose[3:])
        artifact = {
            "schema_version": self.SCHEMA_VERSION,
            "transaction_state": "COMMITTED", "arm": "right", "purpose": "pick",
            "observation_id": epoch["observation_id"],
            "scene_snapshot_id": scene["scene_snapshot_id"],
            "scene_digest": scene["scene_digest"],
            "pointcloud_sha256": scene["pointcloud_sha256"],
            "detection_id": serialized["request_id"],
            "detection_raw_sha256": hashlib.sha256(
                detection.raw_response.encode("utf-8")).hexdigest(),
            "target": {"frame": "BODY", "pose_m_rad": body_pose,
                       "source_profile": "right_pick"},
            "robot_state_before": before, "robot_state_after": after,
            "maximum_joint_delta_rad": maximum_delta,
            "calibration_revision": meta.get("calibration_revision"),
            "tool_revision": meta.get("tool_revision"),
            "captured_at_unix": started,
            "completed_at_unix": self.clock(),
        }
        _atomic_json(destination / "manipulation_observation.json", artifact)
        return artifact
