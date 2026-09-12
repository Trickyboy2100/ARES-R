"""Immutable, revision-addressed LabWorkspace ResourceGraph."""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from ares_r.skills.serialization import digest
from .affordance import Affordance
from .geometry_binding import GeometryBinding
from .occupancy import Occupancy
from .predicates import Predicate, TruthValue
from .relations import Relation, RelationType
from .resource import (Container, Holder, MaterialResource, PhysicalResource,
                       Port, Resource, Slot)


@dataclass(frozen=True)
class ResourceGraph:
    revision: str
    resources: Tuple[Resource, ...]
    relations: Tuple[Relation, ...] = ()
    predicates: Tuple[Predicate, ...] = ()
    occupancies: Tuple[Occupancy, ...] = ()
    geometry_bindings: Tuple[GeometryBinding, ...] = ()
    affordances: Tuple[Affordance, ...] = ()

    @staticmethod
    def _revision_for(values):
        return "WORKSPACE_" + digest(values)

    @classmethod
    def create(cls, resources: Iterable[Resource], relations: Iterable[Relation] = (),
               predicates: Iterable[Predicate] = (), occupancies: Iterable[Occupancy] = (),
               geometry_bindings: Iterable[GeometryBinding] = (),
               affordances: Iterable[Affordance] = ()) -> "ResourceGraph":
        values = {
            "resources": tuple(sorted(resources, key=lambda item: item.resource_id)),
            "relations": tuple(sorted(relations, key=lambda item: (item.relation.value, item.subject_id, item.object_id))),
            "predicates": tuple(sorted(predicates, key=lambda item: (item.subject_id, item.name))),
            "occupancies": tuple(sorted(occupancies, key=lambda item: item.location_id)),
            "geometry_bindings": tuple(sorted(geometry_bindings, key=lambda item: item.resource_id)),
            "affordances": tuple(sorted(affordances, key=lambda item: (item.resource_id, item.affordance_id))),
        }
        return cls(cls._revision_for(values), **values)

    def __post_init__(self) -> None:
        resources = tuple(sorted(self.resources, key=lambda item: item.resource_id))
        relations = tuple(sorted(self.relations, key=lambda item: (item.relation.value, item.subject_id, item.object_id)))
        predicates = tuple(sorted(self.predicates, key=lambda item: (item.subject_id, item.name)))
        occupancies = tuple(sorted(self.occupancies, key=lambda item: item.location_id))
        bindings = tuple(sorted(self.geometry_bindings, key=lambda item: item.resource_id))
        affordances = tuple(sorted(self.affordances, key=lambda item: (item.resource_id, item.affordance_id)))
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "predicates", predicates)
        object.__setattr__(self, "occupancies", occupancies)
        object.__setattr__(self, "geometry_bindings", bindings)
        object.__setattr__(self, "affordances", affordances)
        index = {item.resource_id: item for item in resources}
        if len(index) != len(resources):
            raise ValueError("duplicate resource ID")
        self._validate_parents(index)
        self._validate_relations(index, relations)
        self._validate_predicates(index, predicates)
        self._validate_occupancy(index, occupancies)
        self._validate_bindings(index, bindings)
        self._validate_affordances(index, affordances)
        values = {"resources": resources, "relations": relations,
            "predicates": predicates, "occupancies": occupancies,
            "geometry_bindings": bindings, "affordances": affordances}
        expected = self._revision_for(values)
        if self.revision != expected:
            raise ValueError("workspace revision does not match canonical content")

    @staticmethod
    def _validate_parents(index: Dict[str, Resource]) -> None:
        for item in index.values():
            if item.parent_id:
                if item.parent_id not in index:
                    raise ValueError("invalid parent: %s" % item.parent_id)
                if not isinstance(item, PhysicalResource) or not isinstance(index[item.parent_id], PhysicalResource):
                    raise ValueError("physical containment only accepts physical resources")
            seen = set()
            cursor = item
            while cursor.parent_id:
                if cursor.resource_id in seen:
                    raise ValueError("resource containment cycle")
                seen.add(cursor.resource_id)
                cursor = index[cursor.parent_id]

    @staticmethod
    def _validate_relations(index: Dict[str, Resource], relations: Iterable[Relation]) -> None:
        seen = set()
        for relation in relations:
            key = (relation.relation, relation.subject_id, relation.object_id)
            if key in seen:
                raise ValueError("duplicate relation")
            seen.add(key)
            if relation.subject_id not in index or relation.object_id not in index:
                raise ValueError("relation references unknown resource")
            if relation.relation == RelationType.CONTAINS_MATERIAL:
                if not isinstance(index[relation.subject_id], Container) or not isinstance(index[relation.object_id], MaterialResource):
                    raise ValueError("contains_material requires Container -> MaterialResource")

    @staticmethod
    def _validate_occupancy(index: Dict[str, Resource], occupancies: Iterable[Occupancy]) -> None:
        locations, occupants = set(), set()
        for occupancy in occupancies:
            if occupancy.location_id in locations or occupancy.occupant_id in occupants:
                raise ValueError("occupancy collision")
            locations.add(occupancy.location_id); occupants.add(occupancy.occupant_id)
            if occupancy.location_id not in index or occupancy.occupant_id not in index:
                raise ValueError("occupancy references unknown resource")
            location, occupant = index[occupancy.location_id], index[occupancy.occupant_id]
            if not isinstance(location, (Holder, Slot, Port)) or not isinstance(occupant, PhysicalResource):
                raise ValueError("occupancy is physical Holder/Slot/Port -> PhysicalResource")
            if location.accepts_occupant_types and occupant.type_name not in location.accepts_occupant_types:
                raise ValueError("incompatible placement")

    @staticmethod
    def _validate_predicates(index: Dict[str, Resource], predicates: Iterable[Predicate]) -> None:
        keys = set()
        for predicate in predicates:
            key = (predicate.subject_id, predicate.name)
            if predicate.subject_id not in index or key in keys:
                raise ValueError("predicate references unknown resource or is duplicated")
            keys.add(key)

    @staticmethod
    def _validate_affordances(index: Dict[str, Resource], affordances: Iterable[Affordance]) -> None:
        keys = set()
        for affordance in affordances:
            key = (affordance.resource_id, affordance.affordance_id)
            if affordance.resource_id not in index or key in keys:
                raise ValueError("affordance references unknown resource or is duplicated")
            keys.add(key)

    @staticmethod
    def _validate_bindings(index: Dict[str, Resource], bindings: Iterable[GeometryBinding]) -> None:
        resource_ids, object_ids = set(), set()
        for binding in bindings:
            if binding.resource_id in resource_ids or binding.object_id in object_ids:
                raise ValueError("geometry binding must be one-to-one")
            resource_ids.add(binding.resource_id); object_ids.add(binding.object_id)
            if binding.resource_id not in index or not isinstance(index[binding.resource_id], PhysicalResource):
                raise ValueError("only known physical resources may have geometry")

    def get(self, resource_id: str) -> Optional[Resource]:
        return next((item for item in self.resources if item.resource_id == resource_id), None)

    def require(self, resource_id: str) -> Resource:
        item = self.get(resource_id)
        if item is None:
            raise KeyError(resource_id)
        return item

    def children(self, resource_id: str) -> Tuple[Resource, ...]:
        return tuple(item for item in self.resources if item.parent_id == resource_id)

    def relation_exists(self, relation: RelationType, subject_id: str, object_id: str) -> bool:
        return Relation(relation, subject_id, object_id) in self.relations

    def predicate(self, subject_id: str, name: str) -> TruthValue:
        item = next((value for value in self.predicates
                     if value.subject_id == subject_id and value.name == name), None)
        return item.value if item is not None else TruthValue.UNKNOWN

    def occupant(self, location_id: str) -> Optional[Resource]:
        item = next((value for value in self.occupancies if value.location_id == location_id), None)
        return None if item is None else self.require(item.occupant_id)

    def binding(self, resource_id: str) -> Optional[GeometryBinding]:
        return next((item for item in self.geometry_bindings if item.resource_id == resource_id), None)
