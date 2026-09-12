"""Structured outcomes and evidence for expected business success/failure."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from .failures import FailureCode
from .serialization import freeze, pairs


class SkillStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class SkillLifecycleState(str, Enum):
    ACCEPTED = "ACCEPTED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


@dataclass(frozen=True)
class SkillRuntimeEvent:
    invocation_id: str
    sequence: int
    previous_state: Optional[SkillLifecycleState]
    state: SkillLifecycleState
    recorded_at_unix_ns: int
    details: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.invocation_id or self.sequence < 0 or self.recorded_at_unix_ns <= 0:
            raise ValueError("runtime event identity, sequence and timestamp are required")
        previous = (None if self.previous_state is None
                    else SkillLifecycleState(self.previous_state))
        object.__setattr__(self, "previous_state", previous)
        object.__setattr__(self, "state", SkillLifecycleState(self.state))
        if previous is None:
            if self.sequence != 0 or self.state != SkillLifecycleState.ACCEPTED:
                raise ValueError("initial runtime event must be sequence 0 ACCEPTED")
        else:
            allowed = {
                SkillLifecycleState.ACCEPTED: (SkillLifecycleState.PLANNING,
                    SkillLifecycleState.REJECTED, SkillLifecycleState.CANCELLED,
                    SkillLifecycleState.TIMED_OUT, SkillLifecycleState.FAILED),
                SkillLifecycleState.PLANNING: (SkillLifecycleState.READY,
                    SkillLifecycleState.REJECTED, SkillLifecycleState.CANCELLED,
                    SkillLifecycleState.TIMED_OUT, SkillLifecycleState.FAILED),
                SkillLifecycleState.READY: (SkillLifecycleState.RUNNING,
                    SkillLifecycleState.CANCELLED, SkillLifecycleState.TIMED_OUT,
                    SkillLifecycleState.FAILED),
                SkillLifecycleState.RUNNING: (SkillLifecycleState.VERIFYING,
                    SkillLifecycleState.CANCELLED, SkillLifecycleState.TIMED_OUT,
                    SkillLifecycleState.FAILED),
                SkillLifecycleState.VERIFYING: (SkillLifecycleState.SUCCEEDED,
                    SkillLifecycleState.FAILED, SkillLifecycleState.CANCELLED,
                    SkillLifecycleState.TIMED_OUT),
            }
            if self.state not in allowed.get(previous, ()):
                raise ValueError("invalid skill lifecycle transition")
        object.__setattr__(self, "details", pairs(self.details, "runtime event details"))


@dataclass(frozen=True)
class SkillEvidence:
    evidence_id: str
    kind: str
    captured_at_unix_ns: int
    source_revision: str
    value: Any

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.kind or not self.source_revision or self.captured_at_unix_ns <= 0:
            raise ValueError("invalid skill evidence")
        object.__setattr__(self, "value", freeze(self.value))


@dataclass(frozen=True)
class SkillEffect:
    predicate: str
    subject_id: str
    value: Any
    verified: bool

    def __post_init__(self) -> None:
        if not self.predicate or not self.subject_id:
            raise ValueError("invalid skill effect")
        object.__setattr__(self, "value", freeze(self.value))


@dataclass(frozen=True)
class SkillResult:
    invocation_id: str
    plan_id: Optional[str]
    status: SkillStatus
    message: str
    started_at_unix_ns: Optional[int]
    completed_at_unix_ns: int
    failure_code: Optional[FailureCode] = None
    evidence: Tuple[SkillEvidence, ...] = ()
    effects: Tuple[SkillEffect, ...] = ()
    metadata: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.invocation_id or self.completed_at_unix_ns <= 0:
            raise ValueError("result identity and completion time are required")
        status = SkillStatus(self.status)
        object.__setattr__(self, "status", status)
        failed = (SkillStatus.FAILED, SkillStatus.REJECTED, SkillStatus.CANCELLED, SkillStatus.TIMED_OUT)
        if status == SkillStatus.SUCCEEDED and self.failure_code is not None:
            raise ValueError("successful result cannot have a failure code")
        if status in failed and self.failure_code is None:
            raise ValueError("unsuccessful terminal result requires a failure code")
        if self.failure_code is not None:
            object.__setattr__(self, "failure_code", FailureCode(self.failure_code))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "effects", tuple(self.effects))
        object.__setattr__(self, "metadata", pairs(self.metadata, "metadata"))
