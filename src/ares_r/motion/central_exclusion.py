"""Versioned BODY-centre virtual exclusion policy.

This policy controls only the artificial BODY ``Y`` slab.  It never disables
robot/self/world collision geometry or any controller protection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class CentralExclusionPolicy:
    enabled: bool = True
    half_width_m: float = 0.070
    revision: str = "CENTRAL_EXCLUSION_V1"

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("central exclusion enabled must be boolean")
        if not 0.0 < float(self.half_width_m) <= 0.20:
            raise ValueError("central exclusion half-width must be 0..0.20 m")

    @classmethod
    def from_config(cls, config: Mapping[str, object]):
        value = (config.get("central_exclusion") or
                 (config.get("scene_aware_motion") or {}).get("central_exclusion") or {})
        return cls(enabled=bool(value.get("enabled", True)),
                   half_width_m=float(value.get("half_width_m", 0.070)),
                   revision=str(value.get("revision", "CENTRAL_EXCLUSION_V1")))

    def margin(self, arm: str, body_y_m: float) -> float:
        if arm not in ("left", "right"):
            raise ValueError("arm must be left or right")
        if not self.enabled:
            return float("inf")
        y = float(body_y_m)
        return y - self.half_width_m if arm == "left" else -y - self.half_width_m

    def gate(self, arm: str, body_y_m: float) -> bool:
        return self.margin(arm, body_y_m) > 0.0

    def to_dict(self):
        return asdict(self)
