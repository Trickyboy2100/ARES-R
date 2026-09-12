"""Dependency contracts only. S1A deliberately contains no SkillRuntime."""

from dataclasses import dataclass
from typing import Any, Protocol


class WorldModelView(Protocol):
    def require_active_snapshot(self) -> Any: ...


class WorkspaceView(Protocol):
    @property
    def revision(self) -> str: ...


@dataclass(frozen=True)
class SkillContext:
    world_model: WorldModelView
    workspace: WorkspaceView
    capability_registry: Any
    policy: Any


SKILL_RUNTIME_IMPLEMENTED = False
EXECUTION_LEASE_IMPLEMENTED = False
