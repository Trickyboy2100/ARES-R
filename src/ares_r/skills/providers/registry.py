"""Deterministic capability metadata resolution."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..contracts import CapabilityRequirement
from ..maturity import SkillMaturity
from .base import CapabilityProvider, ProviderHealth, ProviderMode


@dataclass(frozen=True)
class CapabilityResolution:
    providers: Tuple[CapabilityProvider, ...]
    missing_capabilities: Tuple[str, ...]

    @property
    def successful(self) -> bool:
        return not self.missing_capabilities


class CapabilityRegistry:
    def __init__(self) -> None:
        self._providers = {}  # type: Dict[Tuple[str, str], CapabilityProvider]

    def register(self, provider: CapabilityProvider) -> None:
        descriptor = provider.descriptor
        key = (descriptor.provider_id, descriptor.implementation_version)
        if key in self._providers:
            raise ValueError("duplicate provider registration: %s@%s" % key)
        self._providers[key] = provider

    def resolve(self, requirements: Tuple[CapabilityRequirement, ...], mode: ProviderMode,
                maturity: SkillMaturity = SkillMaturity.SPECIFIED) -> CapabilityResolution:
        mode, maturity = ProviderMode(mode), SkillMaturity(maturity)
        selected, missing = [], []
        for requirement in sorted(requirements, key=lambda item: item.capability_id):
            candidates = [provider for provider in self._providers.values()
                if provider.descriptor.mode == mode
                and provider.descriptor.health == ProviderHealth.READY
                and provider.descriptor.maturity_ceiling >= maturity
                and requirement.capability_id in provider.descriptor.capabilities
                and provider.descriptor.protocol_version >= requirement.minimum_protocol_version]
            candidates.sort(key=lambda item: (item.descriptor.provider_id,
                                               item.descriptor.implementation_version))
            if not candidates:
                missing.append(requirement.capability_id)
            elif candidates[0] not in selected:
                selected.append(candidates[0])
        return CapabilityResolution(tuple(selected), tuple(missing))

    def get(self, provider_id: str, version: str) -> Optional[CapabilityProvider]:
        return self._providers.get((provider_id, version))
