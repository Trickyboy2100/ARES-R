"""Explicit physical holder/slot/port occupancy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Occupancy:
    location_id: str
    occupant_id: str

    def __post_init__(self) -> None:
        if not self.location_id or not self.occupant_id or self.location_id == self.occupant_id:
            raise ValueError("occupancy requires distinct location and occupant")
