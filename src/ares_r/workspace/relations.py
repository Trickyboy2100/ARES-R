"""Closed semantic relation vocabulary."""

from dataclasses import dataclass
from enum import Enum


class RelationType(str, Enum):
    CONTAINS_MATERIAL = "CONTAINS_MATERIAL"
    LOCATED_AT = "LOCATED_AT"
    LOADED_IN = "LOADED_IN"
    MOUNTED_AT = "MOUNTED_AT"
    CONNECTED_TO = "CONNECTED_TO"
    COMPATIBLE_WITH = "COMPATIBLE_WITH"
    REQUIRES_TOOL = "REQUIRES_TOOL"


@dataclass(frozen=True)
class Relation:
    relation: RelationType
    subject_id: str
    object_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation", RelationType(self.relation))
        if not self.subject_id or not self.object_id or self.subject_id == self.object_id:
            raise ValueError("relation endpoints must be distinct stable IDs")
