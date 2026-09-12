"""Versioned join between semantic resources and WorldModel geometry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeometryBinding:
    resource_id: str
    object_id: str
    frame_ref: str
    geometry_revision: str
    calibration_revision: str

    def __post_init__(self) -> None:
        if not all((self.resource_id, self.object_id, self.frame_ref,
                    self.geometry_revision, self.calibration_revision)):
            raise ValueError("complete geometry binding provenance is required")
