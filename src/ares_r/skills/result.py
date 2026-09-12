"""Structured outcomes and evidence for expected business success/failure."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from .failures import FailureCode
from .serialization import freeze, pairs


class SkillStatus(str, Enum):
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
