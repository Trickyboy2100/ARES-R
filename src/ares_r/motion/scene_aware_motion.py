"""Generic scene-aware free-space arm motion contracts and hard validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Callable, Mapping, Optional, Sequence
import uuid

from .local_scene_service import LocalSceneService, ScenePolicy, _atomic_json


class OrientationMode(str, Enum):
    FREE = "FREE"
    CURRENT = "CURRENT"
    BODY_FORWARD_HORIZONTAL = "BODY_FORWARD_HORIZONTAL"
    EXPLICIT = "EXPLICIT"


class StartClearanceState(str, Enum):
    START_COLLISION = "START_COLLISION"
    START_NEAR_OBSTACLE = "START_NEAR_OBSTACLE"
    NORMAL = "NORMAL"


@dataclass(frozen=True)
class MotionConstraints:
    orientation: OrientationMode = OrientationMode.FREE
    explicit_rotation: Optional[Sequence[Sequence[float]]] = None
    central_exclusion: bool = True
    keepout_ids: tuple = ()
    attached_object_revision: Optional[str] = None


@dataclass(frozen=True)
class MotionRequest:
    arm: str
    goal_joints_rad: Sequence[float]
    goal_pose_body_m_rad: Optional[Sequence[float]] = None
    constraints: MotionConstraints = field(default_factory=MotionConstraints)
    speed_profile: str = "slow"
    scene_policy: ScenePolicy = ScenePolicy.AUTO_FRESH
    request_label: str = "free_space_motion"

    def validate(self) -> None:
        if self.arm not in ("left", "right"):
            raise ValueError("arm must be left or right")
        if (len(self.goal_joints_rad) != 6 or
                not all(math.isfinite(float(v)) for v in self.goal_joints_rad)):
            raise ValueError("six finite goal joints required")
        if self.constraints.orientation is OrientationMode.EXPLICIT:
            rotation = self.constraints.explicit_rotation
            if rotation is None or len(rotation) != 3 or any(len(row) != 3 for row in rotation):
                raise ValueError("EXPLICIT orientation requires a 3x3 rotation")


@dataclass(frozen=True)
class ClearancePolicy:
    revision: str
    preferred_clearance_m: float
    hard_collision_floor_m: float = 0.0
    escape_dip_tolerance_m: float = 0.002

    def validate(self) -> None:
        if not (0 <= self.hard_collision_floor_m < self.preferred_clearance_m <= 0.10):
            raise ValueError("invalid planner clearance policy")
        if not 0 <= self.escape_dip_tolerance_m <= 0.01:
            raise ValueError("invalid near-start escape tolerance")


def evaluate_hard_validity(plan: Mapping[str, object], policy: ClearancePolicy) -> dict:
    """Validate penetration/binding semantics without imposing preferred margin.

    The preferred clearance is planner policy.  This check only rejects modeled
    penetration or an escape that moves materially deeper toward an obstacle.
    """
    policy.validate()
    independent = plan.get("independent_dense_validation") or {}
    start = float(plan.get("clearance_m", {}).get("start", -math.inf))
    goal = float(plan.get("clearance_m", {}).get("goal", -math.inf))
    minimum = float(independent.get("min_clearance_m", -math.inf))
    trace = [float(v) for v in plan.get("planner_clearance_trace_m", [])]
    collision_free = bool(independent.get("collision_free")) and minimum > policy.hard_collision_floor_m
    if start <= policy.hard_collision_floor_m:
        state = StartClearanceState.START_COLLISION
    elif start < policy.preferred_clearance_m:
        state = StartClearanceState.START_NEAR_OBSTACLE
    else:
        state = StartClearanceState.NORMAL
    escape_ok = True
    recovery = None
    if state is StartClearanceState.START_NEAR_OBSTACLE:
        observed = trace or [start, minimum, goal]
        escape_ok = min(observed) >= max(
            policy.hard_collision_floor_m,
            start - policy.escape_dip_tolerance_m)
        recovery_target = min(policy.preferred_clearance_m, max(start, goal))
        recovery = max(observed) >= recovery_target - 1e-9
        escape_ok = escape_ok and recovery
    hard_valid = (plan.get("observed_result") == "SUCCESS" and collision_free and
                  state is not StartClearanceState.START_COLLISION and escape_ok)
    return {
        "hard_valid": hard_valid,
        "start_clearance_state": state.value,
        "start_gap_m": start,
        "goal_gap_m": goal,
        "hard_min_gap_m": minimum,
        "preferred_clearance_m": policy.preferred_clearance_m,
        "preferred_clearance_achieved": minimum >= policy.preferred_clearance_m,
        "escape_non_decreasing": escape_ok,
        "escape_recovery_achieved": recovery,
        "planner_policy_revision": policy.revision,
        "validator_role": "HARD_COLLISION_AND_BINDING_ONLY",
    }


class SceneAwareMotionService:
    """One task-level entry point for all collision-aware free-space motion."""

    def __init__(self, config: Mapping[str, object], local_scene: LocalSceneService,
                 planner: Callable[[MotionRequest, Mapping[str, object], Path], Mapping[str, object]],
                 *, state_path="logs/scene_aware_motion.json",
                 clearance_policy: Optional[ClearancePolicy] = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.config = config
        self.local_scene = local_scene
        self.planner = planner
        self.state_path = Path(state_path)
        self.clock = clock
        self.clearance_policy = clearance_policy or ClearancePolicy(
            revision="scene-aware-clearance-v1", preferred_clearance_m=0.030)
        if not self.state_path.exists():
            self._write({"state": "IDLE", "execution_state": "IDLE", "plan_id": None})

    def _read(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write(self, value):
        result = dict(value, updated_at_unix=self.clock())
        _atomic_json(self.state_path, result)
        return result

    def status(self):
        value = self._read()
        value["scene"] = self.local_scene.status()
        return value

    def invalidate_plans(self, reason: str):
        value = self._read()
        value.update(state="STALE", execution_state="STOPPED", reason=str(reason), plan_id=None)
        return self._write(value)

    def plan(self, request: MotionRequest) -> dict:
        request.validate()
        scene = self.local_scene.ensure_fresh(
            "MOTION_REQUEST:%s" % request.request_label, request.scene_policy,
            active_arm=request.arm)
        if scene["state"] != "READY":
            raise RuntimeError("fresh local scene required")
        plan_id = "PLAN_" + uuid.uuid4().hex
        output = Path("worklog/evidence/scene-aware-motion") / plan_id
        self._write({"state": "PLANNING", "execution_state": "IDLE",
                     "plan_id": plan_id, "scene_epoch": scene["scene_epoch"],
                     "scene_snapshot_id": scene["scene_snapshot_id"]})
        try:
            plan = dict(self.planner(request, scene, output))
            validity = evaluate_hard_validity(plan, self.clearance_policy)
            if not validity["hard_valid"]:
                raise RuntimeError("hard trajectory validation failed: %s" % validity)
        except Exception as exc:
            self._write({"state": "FAILED", "execution_state": "IDLE",
                         "plan_id": None, "reason": "%s:%s" % (type(exc).__name__, exc)})
            raise
        trajectory = plan.get("trajectory_points_rad") or []
        digest = hashlib.sha256(json.dumps(trajectory, separators=(",", ":")).encode()).hexdigest()
        request_payload = asdict(request)
        request_payload["scene_policy"] = request.scene_policy.value
        request_payload["constraints"]["orientation"] = request.constraints.orientation.value
        handle = {
            "schema_version": 1,
            "plan_id": plan_id,
            "arm": request.arm,
            "request": request_payload,
            "scene_epoch": scene["scene_epoch"],
            "scene_snapshot_id": scene["scene_snapshot_id"],
            "scene_digest": scene["scene_digest"],
            "pointcloud_sha256": scene["pointcloud_sha256"],
            "base_pose_revision": scene["base_pose_revision"],
            "trajectory_hash": "sha256:" + digest,
            "planner_clearance_policy": asdict(self.clearance_policy),
            "hard_validity": validity,
            "plan_artifact": str(output),
            "created_at_unix": self.clock(),
        }
        output.mkdir(parents=True, exist_ok=True)
        _atomic_json(output / "plan_handle.json", handle)
        self._write({"state": "READY", "execution_state": "ARMED", "plan_id": plan_id,
                     "plan_handle": str(output / "plan_handle.json"),
                     "scene_epoch": scene["scene_epoch"],
                     "scene_snapshot_id": scene["scene_snapshot_id"],
                     "planner_timing_s": plan.get("timing_s")})
        return handle

    def preview(self, plan_id: Optional[str] = None) -> dict:
        current = self._read()
        if current.get("state") != "READY" or not current.get("plan_handle"):
            raise RuntimeError("no ready scene-aware plan")
        handle = json.loads(Path(current["plan_handle"]).read_text())
        if plan_id is not None and handle["plan_id"] != plan_id:
            raise RuntimeError("plan handle mismatch")
        scene = self.local_scene.snapshot()
        if (scene["scene_epoch"] != handle["scene_epoch"] or
                scene["scene_snapshot_id"] != handle["scene_snapshot_id"]):
            self.invalidate_plans("SCENE_CHANGED")
            raise RuntimeError("plan is stale after scene change")
        return handle

    def execute(self, plan_id: str):
        """Execution is supplied by the native route in the hardware adapter phase."""
        handle = self.preview(plan_id)
        raise RuntimeError("generic native executor not installed for %s" % handle["plan_id"])

    def stop(self):
        return self.invalidate_plans("OPERATOR_STOP")


def build_services(config: Mapping[str, object], *, scene_state_path=None,
                   motion_state_path=None):
    """Construct the shared backend used by ART, scripts and the Web UI."""
    from .scene_aware_planner import PersistentCuroboPlanner, load_profile
    profile = load_profile()
    merged = dict(config)
    merged["scene_aware_motion"] = {
        "scene_ttl_s": profile["scene_ttl_s"],
        "evidence_directory": "worklog/evidence/scene-aware-motion",
    }
    scene = LocalSceneService(merged, state_path=scene_state_path)
    values = profile["planner"]
    clearance = ClearancePolicy(
        revision=values["profile_revision"],
        preferred_clearance_m=float(values["preferred_clearance_m"]),
        hard_collision_floor_m=float(values["hard_collision_floor_m"]),
        escape_dip_tolerance_m=float(values["escape_dip_tolerance_m"]),
    )
    motion = SceneAwareMotionService(
        merged, scene, PersistentCuroboPlanner(config, profile),
        state_path=motion_state_path or "logs/scene_aware_motion.json",
        clearance_policy=clearance)
    return scene, motion
