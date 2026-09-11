"""Snapshot lifecycle is mutable state outside immutable snapshots."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LifecycleState(str,Enum):
    ACTIVE="ACTIVE"
    STALE="STALE"
    EXPIRED="EXPIRED"
    LEASED="LEASED"
    INVALIDATED="INVALIDATED"


class InvalidationReason(str,Enum):
    BASE_MOVED="BASE_MOVED"
    LEFT_ARM_MOVED="LEFT_ARM_MOVED"
    RIGHT_ARM_MOVED="RIGHT_ARM_MOVED"
    OBJECT_ATTACHED_LEFT="OBJECT_ATTACHED_LEFT"
    OBJECT_ATTACHED_RIGHT="OBJECT_ATTACHED_RIGHT"
    OBJECT_DETACHED_LEFT="OBJECT_DETACHED_LEFT"
    OBJECT_DETACHED_RIGHT="OBJECT_DETACHED_RIGHT"
    NEW_OBSERVATION="NEW_OBSERVATION"
    CALIBRATION_CHANGED="CALIBRATION_CHANGED"
    SNAPSHOT_TIMEOUT="SNAPSHOT_TIMEOUT"
    ROBOT_STATE_DRIFT="ROBOT_STATE_DRIFT"
    EXTERNAL_MOTION="EXTERNAL_MOTION"
    PROCESS_RESTART="PROCESS_RESTART"
    MANUAL_INVALIDATION="MANUAL_INVALIDATION"


@dataclass(frozen=True)
class SnapshotLifecycle:
    snapshot_id: str
    state: LifecycleState
    changed_wall_unix_ns: int
    changed_monotonic_ns: int
    runtime_id: str
    reason: Optional[InvalidationReason]=None


def effective_lifecycle(lifecycle: SnapshotLifecycle,now_monotonic_ns: int,
                        runtime_id: str,ttl_ns: int) -> SnapshotLifecycle:
    if lifecycle.runtime_id!=runtime_id:
        return SnapshotLifecycle(lifecycle.snapshot_id,LifecycleState.INVALIDATED,
            lifecycle.changed_wall_unix_ns,now_monotonic_ns,runtime_id,InvalidationReason.PROCESS_RESTART)
    if lifecycle.state==LifecycleState.ACTIVE and now_monotonic_ns-lifecycle.changed_monotonic_ns>ttl_ns:
        return SnapshotLifecycle(lifecycle.snapshot_id,LifecycleState.EXPIRED,
            lifecycle.changed_wall_unix_ns,now_monotonic_ns,runtime_id,InvalidationReason.SNAPSHOT_TIMEOUT)
    return lifecycle

