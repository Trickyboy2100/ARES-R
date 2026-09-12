"""Data-driven interaction affordances for generic skills."""

from dataclasses import dataclass
from typing import Any, Tuple

from ares_r.skills.serialization import pairs


@dataclass(frozen=True)
class Affordance:
    resource_id: str
    affordance_id: str
    capability_id: str
    interaction_frame: str
    parameters: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not all((self.resource_id, self.affordance_id, self.capability_id, self.interaction_frame)):
            raise ValueError("affordance identity, capability and frame are required")
        object.__setattr__(self, "parameters", pairs(self.parameters, "affordance parameters"))
