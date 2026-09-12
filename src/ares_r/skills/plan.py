"""Immutable plan with explicit optional geometric world binding."""

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .serialization import pairs, require_digest


@dataclass(frozen=True)
class SkillPlan:
    plan_id: str
    invocation_id: str
    skill_id: str
    implementation_version: str
    created_at_unix_ns: int
    expires_at_unix_ns: int
    workspace_revision: str
    workspace_digest: str
    motion_bearing: bool
    resolved_resources: Tuple[Tuple[str, Any], ...] = ()
    steps: Tuple[Tuple[str, Any], ...] = ()
    scene_snapshot_id: Optional[str] = None
    planning_context_digest: Optional[str] = None

    def __post_init__(self) -> None:
        identity = (self.plan_id, self.invocation_id, self.skill_id,
                    self.implementation_version, self.workspace_revision)
        if not all(identity) or self.created_at_unix_ns <= 0 or self.expires_at_unix_ns <= self.created_at_unix_ns:
            raise ValueError("invalid plan identity or timestamps")
        object.__setattr__(self, "workspace_digest", require_digest(self.workspace_digest, "workspace_digest"))
        object.__setattr__(self, "resolved_resources", pairs(self.resolved_resources, "resolved_resources"))
        object.__setattr__(self, "steps", pairs(self.steps, "steps"))
        if self.motion_bearing:
            if not self.scene_snapshot_id or not self.planning_context_digest:
                raise ValueError("motion-bearing plans require a scene snapshot binding")
            object.__setattr__(self, "planning_context_digest", require_digest(self.planning_context_digest, "planning_context_digest"))
        elif self.scene_snapshot_id is not None or self.planning_context_digest is not None:
            raise ValueError("non-motion plans must not carry a partial or fake scene binding")
