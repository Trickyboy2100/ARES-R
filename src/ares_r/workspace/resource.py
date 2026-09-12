"""Immutable physical/material laboratory resource taxonomy."""

from dataclasses import dataclass
from typing import Any, Tuple

from ares_r.skills.serialization import pairs


@dataclass(frozen=True)
class Resource:
    resource_id: str
    label: str
    parent_id: str = ""
    capabilities: Tuple[str, ...] = ()
    accepts_occupant_types: Tuple[str, ...] = ()
    metadata: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id or not self.label:
            raise ValueError("stable resource_id and label are required")
        object.__setattr__(self, "capabilities", tuple(sorted(set(self.capabilities))))
        object.__setattr__(self, "accepts_occupant_types", tuple(sorted(set(self.accepts_occupant_types))))
        object.__setattr__(self, "metadata", pairs(self.metadata, "resource metadata"))

    @property
    def type_name(self) -> str:
        return type(self).__name__

    @property
    def is_physical(self) -> bool:
        return isinstance(self, PhysicalResource)


@dataclass(frozen=True)
class PhysicalResource(Resource):
    pass


@dataclass(frozen=True)
class Station(PhysicalResource): pass
@dataclass(frozen=True)
class Device(PhysicalResource): pass
@dataclass(frozen=True)
class Container(PhysicalResource): pass
@dataclass(frozen=True)
class Tool(PhysicalResource): pass
@dataclass(frozen=True)
class Fixture(PhysicalResource): pass
@dataclass(frozen=True)
class Holder(PhysicalResource): pass
@dataclass(frozen=True)
class Slot(PhysicalResource): pass
@dataclass(frozen=True)
class Port(PhysicalResource): pass
@dataclass(frozen=True)
class Zone(PhysicalResource): pass


@dataclass(frozen=True)
class MaterialResource(Resource):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.parent_id:
            raise ValueError("material location uses typed relations, not physical containment")


@dataclass(frozen=True)
class Sample(MaterialResource): pass
@dataclass(frozen=True)
class Reagent(MaterialResource): pass
@dataclass(frozen=True)
class ConsumableMaterial(MaterialResource): pass
@dataclass(frozen=True)
class Waste(MaterialResource): pass
