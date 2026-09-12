"""Three-valued semantic facts."""

from dataclasses import dataclass
from enum import Enum


class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Predicate:
    subject_id: str
    name: str
    value: TruthValue
    evidence_revision: str = ""

    def __post_init__(self) -> None:
        if not self.subject_id or not self.name:
            raise ValueError("predicate subject and name are required")
        object.__setattr__(self, "value", TruthValue(self.value))
