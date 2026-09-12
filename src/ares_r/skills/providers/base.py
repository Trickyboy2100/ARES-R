"""Capability provider metadata contracts; no execution runtime is defined here."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Tuple

from ..maturity import SkillMaturity


class ProviderMode(str, Enum):
    MOCK = "MOCK"
    ISAAC = "ISAAC"
    REAL_DRYRUN = "REAL_DRYRUN"
    REAL = "REAL"


class ProviderHealth(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    version: str
    mode: ProviderMode
    capabilities: Tuple[str, ...]
    maturity_ceiling: SkillMaturity
    supports_cancel: bool
    health: ProviderHealth

    def __post_init__(self) -> None:
        if not self.provider_id or not self.version or not self.capabilities:
            raise ValueError("provider identity, version and capabilities are required")
        object.__setattr__(self, "mode", ProviderMode(self.mode))
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))
        object.__setattr__(self, "maturity_ceiling", SkillMaturity(self.maturity_ceiling))
        object.__setattr__(self, "health", ProviderHealth(self.health))


class CapabilityProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...
