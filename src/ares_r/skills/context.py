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


CONTRACT_V1 = "FROZEN"
SKILL_RUNTIME_IMPLEMENTED = False
LOCK_MANAGER_IMPLEMENTED = False
MOCK_SKILL_EXECUTION_IMPLEMENTED = False
PRODUCTION_EXECUTION_LEASE_IMPLEMENTED = False
ISAAC_PROVIDER_IMPLEMENTED = False
REAL_PROVIDER_IMPLEMENTED = False
