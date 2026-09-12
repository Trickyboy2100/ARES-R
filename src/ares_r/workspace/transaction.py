"""Explicit compare-and-swap workspace transactions."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from .occupancy import Occupancy
from .predicates import Predicate
from .resource_graph import ResourceGraph


class TransactionStatus(str, Enum):
    COMMITTED = "COMMITTED"
    STALE_REVISION = "STALE_REVISION"
    INVALID_CHANGE = "INVALID_CHANGE"


@dataclass(frozen=True)
class TransactionResult:
    status: TransactionStatus
    graph: ResourceGraph
    message: str = ""


@dataclass(frozen=True)
class WorkspaceTransaction:
    base_revision: str
    predicate_updates: Tuple[Predicate, ...] = ()
    occupancy_updates: Tuple[Occupancy, ...] = ()

    def commit(self, current: ResourceGraph) -> TransactionResult:
        if current.revision != self.base_revision:
            return TransactionResult(TransactionStatus.STALE_REVISION, current, "stale workspace revision")
        predicates = {(item.subject_id, item.name): item for item in current.predicates}
        predicates.update({(item.subject_id, item.name): item for item in self.predicate_updates})
        occupancies = {item.location_id: item for item in current.occupancies}
        occupancies.update({item.location_id: item for item in self.occupancy_updates})
        try:
            updated = ResourceGraph.create(current.resources, current.relations,
                predicates.values(), occupancies.values(), current.geometry_bindings,
                current.affordances)
        except ValueError as error:
            return TransactionResult(TransactionStatus.INVALID_CHANGE, current, str(error))
        return TransactionResult(TransactionStatus.COMMITTED, updated)
