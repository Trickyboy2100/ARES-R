"""Versioned join between semantic resources and WorldModel geometry."""

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class GeometryBinding:
    resource_id: str
    object_id: str
    frame_ref: str
    geometry_revision: str
    calibration_dependencies: Tuple[Tuple[str, str], ...]

    def __post_init__(self) -> None:
        dependencies = tuple(sorted((str(key), str(revision))
                                    for key, revision in self.calibration_dependencies))
        if (not all((self.resource_id, self.object_id, self.frame_ref, self.geometry_revision))
                or not dependencies or any(not key or not revision for key, revision in dependencies)
                or len(dict(dependencies)) != len(dependencies)):
            raise ValueError("complete geometry binding provenance is required")
        object.__setattr__(self, "calibration_dependencies", dependencies)

    def calibration_satisfied_by(self, active_revisions: Iterable[Tuple[str, str]]) -> bool:
        active = dict(active_revisions)
        return all(active.get(key) == revision
                   for key, revision in self.calibration_dependencies)
