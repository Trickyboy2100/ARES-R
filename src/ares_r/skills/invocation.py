"""Immutable user/planner intent; an invocation is never execution authority."""

from dataclasses import dataclass
from typing import Any, Tuple

from .serialization import pairs


@dataclass(frozen=True)
class SkillInvocation:
    invocation_id: str
    skill_id: str
    implementation_version: str
    parameters: Tuple[Tuple[str, Any], ...]
    requested_by: str
    requested_at_unix_ns: int
    workspace_revision: str
    idempotency_key: str

    def __post_init__(self) -> None:
        values = (self.invocation_id, self.skill_id, self.implementation_version,
                  self.requested_by, self.workspace_revision, self.idempotency_key)
        if not all(values) or self.requested_at_unix_ns <= 0:
            raise ValueError("invocation identity, revision and timestamp are required")
        object.__setattr__(self, "parameters", pairs(self.parameters, "parameters"))
