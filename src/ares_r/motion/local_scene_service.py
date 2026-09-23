"""Lifecycle authority for the robot's local BODY-frame collision scene.

The service persists only a small control-plane record.  Immutable pointcloud,
scene and geometry artifacts continue to be produced by ``live_scene``.  This
keeps ART, the Web UI and task clients on one scene epoch without moving the
large observation payload through process-local globals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import time
from typing import Callable, Mapping, Optional
import uuid

from .live_scene import build_live_planning_scene


class SceneState(str, Enum):
    INVALID = "INVALID"
    REQUIRED = "REQUIRED"
    SCANNING = "SCANNING"
    READY = "READY"
    STALE = "STALE"
    ERROR = "ERROR"


class ScenePolicy(str, Enum):
    AUTO_FRESH = "AUTO_FRESH"
    FORCE_RESCAN = "FORCE_RESCAN"
    REUSE_IF_VALID = "REUSE_IF_VALID"


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class LocalSceneService:
    """Canonical scene state shared by every free-space arm-motion client."""

    SCHEMA_VERSION = 1

    def __init__(self, config: Mapping[str, object], *, state_path=None,
                 scene_builder: Callable = build_live_planning_scene,
                 clock: Callable[[], float] = time.time) -> None:
        self.config = config
        self.state_path = Path(state_path or "logs/local_scene_service.json")
        self.scene_builder = scene_builder
        self.clock = clock
        if not self.state_path.exists():
            self._write(self._empty(SceneState.REQUIRED, "NO_LOCAL_SCENE"))

    def _empty(self, state: SceneState, reason: str) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "state": state.value,
            "reason": reason,
            "base_pose_revision": 0,
            "scene_epoch": 0,
            "scene_snapshot_id": None,
            "scene_digest": None,
            "pointcloud_sha256": None,
            "scene_dir": None,
            "calibration_revision": None,
            "geometry_revision": None,
            "tool_revision": None,
            "created_at_unix": None,
            "updated_at_unix": self.clock(),
            "timings_s": None,
        }

    def _read(self) -> dict:
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != self.SCHEMA_VERSION:
            raise RuntimeError("unsupported LocalSceneService state schema")
        return value

    def _write(self, value: Mapping[str, object]) -> dict:
        result = dict(value)
        result["updated_at_unix"] = self.clock()
        _atomic_json(self.state_path, result)
        return result

    def status(self) -> dict:
        value = self._read()
        ttl = float(self.config.get("scene_aware_motion", {}).get("scene_ttl_s", 300.0))
        created = value.get("created_at_unix")
        if (value["state"] == SceneState.READY.value and created is not None
                and self.clock() - float(created) > ttl):
            value["state"] = SceneState.STALE.value
            value["reason"] = "SCENE_TTL_EXPIRED"
            value = self._write(value)
        value["age_s"] = (None if created is None else
                          max(0.0, self.clock() - float(created)))
        return value

    def invalidate(self, reason: str, *, required: bool = False) -> dict:
        value = self._read()
        value.update(state=(SceneState.REQUIRED if required else SceneState.INVALID).value,
                     reason=str(reason), scene_snapshot_id=None, scene_digest=None,
                     pointcloud_sha256=None, scene_dir=None, created_at_unix=None,
                     timings_s=None)
        return self._write(value)

    def base_motion_started(self) -> dict:
        return self.invalidate("BASE_MOVING")

    def base_settled(self) -> dict:
        value = self._read()
        value["base_pose_revision"] = int(value.get("base_pose_revision", 0)) + 1
        value.update(state=SceneState.REQUIRED.value, reason="BASE_SETTLED_SCENE_REQUIRED",
                     scene_snapshot_id=None, scene_digest=None, pointcloud_sha256=None,
                     scene_dir=None, created_at_unix=None, timings_s=None)
        return self._write(value)

    def scan(self, *, force: bool = False) -> dict:
        current = self.status()
        if current["state"] == SceneState.SCANNING.value:
            raise RuntimeError("local scene scan already in progress")
        if current["state"] == SceneState.READY.value and not force:
            return current
        current.update(state=SceneState.SCANNING.value, reason="FRESH_SCAN_REQUESTED")
        self._write(current)
        evidence_root = Path(self.config.get("scene_aware_motion", {}).get(
            "evidence_directory", "worklog/evidence/scene-aware-motion"))
        destination = (evidence_root /
                       ("scene_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        + "_" + uuid.uuid4().hex[:8]))
        try:
            built = self.scene_builder(self.config, destination)
            report = json.loads((Path(built["scene_dir"]) / "scene/scene_report.json").read_text())
        except Exception as exc:
            failed = self._read()
            failed.update(state=SceneState.ERROR.value,
                          reason="SCAN_FAILED:%s" % type(exc).__name__)
            self._write(failed)
            raise
        value = self._read()
        value.update(
            state=SceneState.READY.value,
            reason=None,
            scene_epoch=int(value.get("scene_epoch", 0)) + 1,
            scene_snapshot_id=built["scene_snapshot_id"],
            scene_digest=built["scene_digest"],
            pointcloud_sha256=built["pointcloud_sha256"],
            scene_dir=built["scene_dir"],
            calibration_revision=report["calibration_revision"],
            geometry_revision=report["geometry_revision"],
            tool_revision=report["tool_revision"],
            created_at_unix=self.clock(),
            timings_s=built.get("timing_s"),
        )
        return self._write(value)

    def ensure_fresh(self, reason: str, policy=ScenePolicy.AUTO_FRESH) -> dict:
        policy = ScenePolicy(policy)
        current = self.status()
        if policy is ScenePolicy.FORCE_RESCAN:
            self.invalidate("FORCE_RESCAN:%s" % reason, required=True)
            return self.scan(force=True)
        if current["state"] == SceneState.READY.value:
            return current
        if policy is ScenePolicy.REUSE_IF_VALID:
            raise RuntimeError("scene is not reusable: %s" % current["state"])
        return self.scan(force=True)

    def snapshot(self) -> dict:
        current = self.status()
        if current["state"] != SceneState.READY.value:
            raise RuntimeError("local scene is not ready: %s" % current["state"])
        return current
