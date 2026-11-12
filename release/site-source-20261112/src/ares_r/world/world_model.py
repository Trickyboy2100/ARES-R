"""World-state authority for coherent observation epochs and immutable snapshots."""

import json
from pathlib import Path
import time
from typing import Dict, Optional, Sequence
import uuid

from .robot_state import RobotState
from .scene_snapshot import (AttachedObject,CalibrationSet,EnvironmentRevision,
    ObservationEpoch,PointCloudRef,SafetyConstraint,SceneObject,SceneSnapshot,
    digest,snapshot_dict)
from .validity import (InvalidationReason,LifecycleState,SnapshotLifecycle,
    effective_lifecycle)


class WorldModel:
    def __init__(self,event_log=None,snapshot_ttl_s: float=5.0,environment_ttl_s: float=30.0,
                 runtime_id: Optional[str]=None) -> None:
        if snapshot_ttl_s<=0 or environment_ttl_s<=0: raise ValueError("world TTLs must be positive")
        self.runtime_id=runtime_id or uuid.uuid4().hex
        self.snapshot_ttl_ns=int(snapshot_ttl_s*1e9);self.environment_ttl_ns=int(environment_ttl_s*1e9);self.event_log=event_log
        self.robot_state=None  # type: Optional[RobotState]
        self.environment=None  # type: Optional[EnvironmentRevision]
        self.left_attached_object=None  # type: Optional[AttachedObject]
        self.right_attached_object=None  # type: Optional[AttachedObject]
        self.current=None  # type: Optional[SceneSnapshot]
        self.lifecycle=None  # type: Optional[SnapshotLifecycle]
        self._pending=None  # type: Optional[Dict[str,object]]

    def _emit(self,event: str,**data) -> None:
        if self.event_log is not None: self.event_log.write(event,**data)

    def update_robot_state(self,state: RobotState) -> None:
        if state.runtime_id!=self.runtime_id: raise ValueError("robot state belongs to another runtime")
        self.robot_state=state;self._emit("world.robot_state_updated",robot_state_digest=digest(state))

    def begin_observation(self,observation_id: Optional[str]=None,wall_unix_ns: Optional[int]=None,
                          monotonic_ns: Optional[int]=None) -> str:
        if self._pending is not None: raise RuntimeError("an observation epoch is already open")
        observation_id=observation_id or ("OBS_"+uuid.uuid4().hex)
        self._pending={"observation_id":observation_id,"wall":wall_unix_ns or time.time_ns(),
            "mono":time.monotonic_ns() if monotonic_ns is None else monotonic_ns,
            "pointcloud":None,"obstacles":None,"calibration":None,"detection_ids":()}
        if self.environment is not None: self.invalidate(InvalidationReason.NEW_OBSERVATION,environment=True)
        self._emit("world.observation_started",observation_id=observation_id)
        return observation_id

    def _require_epoch(self,observation_id: str) -> Dict[str,object]:
        if self._pending is None or self._pending["observation_id"]!=observation_id:
            raise RuntimeError("observation epoch mismatch")
        return self._pending

    def register_pointcloud(self,observation_id: str,pointcloud: PointCloudRef) -> None:
        pending=self._require_epoch(observation_id);pending["pointcloud"]=pointcloud
        self._emit("world.pointcloud_registered",observation_id=observation_id,
            pointcloud_id=pointcloud.pointcloud_id,pointcloud_sha256=pointcloud.sha256)

    def register_obstacles(self,observation_id: str,obstacles: Sequence[SceneObject],
                           pointcloud_id: str,pointcloud_sha256: str) -> None:
        pending=self._require_epoch(observation_id);pointcloud=pending["pointcloud"]
        if pointcloud is None or pointcloud.pointcloud_id!=pointcloud_id or pointcloud.sha256!=pointcloud_sha256:
            raise RuntimeError("ATOM obstacle provenance does not match the epoch pointcloud")
        values=tuple(obstacles)
        if any(item.source_observation_id!=observation_id for item in values):
            raise RuntimeError("ATOM obstacles belong to another observation epoch")
        pending["obstacles"]=values

    def register_calibration(self,observation_id: str,calibration: CalibrationSet) -> None:
        self._require_epoch(observation_id)["calibration"]=calibration

    def register_detections(self,observation_id: str,detection_ids: Sequence[str]) -> None:
        values=tuple(str(value) for value in detection_ids)
        if any(not value for value in values): raise ValueError("detection IDs must be non-empty")
        self._require_epoch(observation_id)["detection_ids"]=values

    def commit_observation(self,observation_id: str) -> EnvironmentRevision:
        pending=self._require_epoch(observation_id)
        if pending["pointcloud"] is None or pending["obstacles"] is None or pending["calibration"] is None:
            raise RuntimeError("pointcloud, matching obstacles and calibration are required")
        epoch=ObservationEpoch(observation_id,int(pending["wall"]),int(pending["mono"]),self.runtime_id,
            pending["calibration"],pending["pointcloud"],pending["obstacles"],pending["detection_ids"])
        obstacle_digest=digest(epoch.obstacles)
        environment=EnvironmentRevision("ENV_"+uuid.uuid4().hex,epoch,obstacle_digest,
            digest({"observation":epoch,"obstacle_digest":obstacle_digest}))
        self.environment=environment;self._pending=None
        self._emit("world.observation_committed",observation_id=observation_id,
            environment_revision_id=environment.environment_revision_id,scene_digest=environment.scene_digest)
        return environment

    def freeze_snapshot(self,robot_model_revision: str,tool_revision: str,
                        constraints: Sequence[SafetyConstraint]=(),artifact_dir=None) -> SceneSnapshot:
        if self.environment is None: raise RuntimeError("no committed environment revision")
        now_mono=time.monotonic_ns()
        observation=self.environment.observation
        if observation.runtime_id!=self.runtime_id or now_mono-observation.captured_monotonic_ns>self.environment_ttl_ns:
            self.invalidate(InvalidationReason.SNAPSHOT_TIMEOUT,environment=True)
            raise RuntimeError("environment observation is expired or from another runtime")
        if self.robot_state is None: raise RuntimeError("robot state is unavailable")
        if self.robot_state.runtime_id!=self.runtime_id: raise RuntimeError("robot state is from another runtime")
        robot_digest=digest(self.robot_state)
        attachments={"left":self.left_attached_object,"right":self.right_attached_object}
        attachment_digest=digest(attachments)
        constraints=tuple(constraints)
        context={"scene_digest":self.environment.scene_digest,"robot_state_digest":robot_digest,
            "attachment_digest":attachment_digest,"robot_model_revision":robot_model_revision,
            "tool_revision":tool_revision,"calibration":self.environment.observation.calibration,
            "constraints":constraints}
        now_wall=time.time_ns()
        snapshot=SceneSnapshot(1,"SCENE_"+uuid.uuid4().hex,now_wall,now_mono,self.runtime_id,
            self.environment,self.robot_state,self.left_attached_object,self.right_attached_object,
            constraints,str(robot_model_revision),str(tool_revision),robot_digest,
            attachment_digest,digest(context))
        if self.current is not None: self.invalidate(InvalidationReason.MANUAL_INVALIDATION)
        self.current=snapshot;self.lifecycle=SnapshotLifecycle(snapshot.snapshot_id,LifecycleState.ACTIVE,
            now_wall,now_mono,self.runtime_id)
        if artifact_dir is not None:
            directory=Path(artifact_dir);directory.mkdir(parents=True,exist_ok=True)
            target=directory/(snapshot.snapshot_id+".json");temporary=target.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(snapshot_dict(snapshot),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            temporary.replace(target)
        self._emit("world.snapshot_created",snapshot_id=snapshot.snapshot_id,
            planning_context_digest=snapshot.planning_context_digest)
        return snapshot

    def invalidate(self,reason: InvalidationReason,environment: bool=False,
                   state: LifecycleState=LifecycleState.INVALIDATED) -> None:
        if self.current is not None and self.lifecycle is not None:
            now_wall,now_mono=time.time_ns(),time.monotonic_ns()
            self.lifecycle=SnapshotLifecycle(self.current.snapshot_id,state,
                now_wall,now_mono,self.runtime_id,reason)
            self._emit("world.snapshot_invalidated",snapshot_id=self.current.snapshot_id,reason=reason.value)
        if environment: self.environment=None

    def robot_moved(self,side: str) -> None:
        reason=InvalidationReason.LEFT_ARM_MOVED if side=="left" else (
            InvalidationReason.RIGHT_ARM_MOVED if side=="right" else None)
        if reason is None: raise ValueError("side must be left or right")
        self.invalidate(reason,state=LifecycleState.STALE)

    def base_moved(self) -> None: self.invalidate(InvalidationReason.BASE_MOVED,environment=True)

    def calibration_changed(self) -> None:
        self.invalidate(InvalidationReason.CALIBRATION_CHANGED,environment=True)

    def attach(self,side: str,item: AttachedObject) -> None:
        if item.attached_to!=side: raise ValueError("attachment side mismatch")
        if side=="left": self.left_attached_object=item;reason=InvalidationReason.OBJECT_ATTACHED_LEFT
        elif side=="right": self.right_attached_object=item;reason=InvalidationReason.OBJECT_ATTACHED_RIGHT
        else: raise ValueError("side must be left or right")
        self.invalidate(reason,state=LifecycleState.STALE)

    def detach(self,side: str) -> None:
        if side=="left": self.left_attached_object=None;reason=InvalidationReason.OBJECT_DETACHED_LEFT
        elif side=="right": self.right_attached_object=None;reason=InvalidationReason.OBJECT_DETACHED_RIGHT
        else: raise ValueError("side must be left or right")
        self.invalidate(reason,state=LifecycleState.STALE)

    def require_active_snapshot(self) -> SceneSnapshot:
        lifecycle=self.lifecycle_now()
        if self.current is None or lifecycle is None or lifecycle.state!=LifecycleState.ACTIVE:
            reason=lifecycle.reason.value if lifecycle and lifecycle.reason else "NO_SNAPSHOT"
            raise RuntimeError("no active planning snapshot: %s"%reason)
        return self.current

    def lifecycle_now(self,now_monotonic_ns: Optional[int]=None) -> Optional[SnapshotLifecycle]:
        if self.lifecycle is None:return None
        current=effective_lifecycle(self.lifecycle,time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns,
            self.runtime_id,self.snapshot_ttl_ns)
        if current is not self.lifecycle:
            self.lifecycle=current;self._emit("world.snapshot_invalidated",snapshot_id=current.snapshot_id,
                reason=current.reason.value if current.reason else None)
        return current

    def status(self) -> Dict[str,object]:
        lifecycle=self.lifecycle_now()
        environment_state="EMPTY"
        if self.environment is not None:
            observation=self.environment.observation
            environment_state="ACTIVE" if observation.runtime_id==self.runtime_id and time.monotonic_ns()-observation.captured_monotonic_ns<=self.environment_ttl_ns else "EXPIRED"
        return {"runtime_id":self.runtime_id,"observation_open":self._pending["observation_id"] if self._pending else None,
            "environment_revision_id":self.environment.environment_revision_id if self.environment else None,
            "environment_state":environment_state,
            "robot_state_available":self.robot_state is not None,
            "snapshot_id":self.current.snapshot_id if self.current else None,
            "snapshot_lifecycle":lifecycle.state.value if lifecycle else "EMPTY",
            "invalid_reason":lifecycle.reason.value if lifecycle and lifecycle.reason else None,
            "planning_context_digest":self.current.planning_context_digest if self.current else None,
            "trajectory_v2_binding":"PENDING_W7","scene_compiler":"PENDING_W6"}
