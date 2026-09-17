"""Named arm speed profiles bounded by the site motion ceiling."""

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpeedProfile:
    name: str
    max_velocity_rad_s: float
    max_acceleration_rad_s2: float
    use: str
    state: str


def load_speed_profiles(path, limits_path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    limits = json.loads(Path(limits_path).read_text(encoding="utf-8"))
    velocity_ceiling = min(float(v) for v in limits["max_velocity_rad_s"])
    acceleration_ceiling = min(float(v) for v in limits["max_acceleration_rad_s2"])
    profiles = {}
    for name, values in raw["profiles"].items():
        velocity = float(values["max_velocity_rad_s"])
        acceleration = float(values["max_acceleration_rad_s2"])
        if not all(math.isfinite(v) and v > 0 for v in (velocity, acceleration)):
            raise ValueError("speed profile %s has invalid limits" % name)
        if velocity > velocity_ceiling or acceleration > acceleration_ceiling:
            raise ValueError("speed profile %s exceeds site ceiling" % name)
        profiles[name] = SpeedProfile(name, velocity, acceleration, str(values["use"]),
                                      str(values.get("state", "UNCOMMISSIONED")))
    return profiles
