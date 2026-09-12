"""Read-only semantic-to-geometric resolver with structured failures."""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Tuple

from ares_r.skills.failures import FailureCode
from .geometry_binding import GeometryBinding
from .resource import MaterialResource, Resource
from .resource_graph import ResourceGraph


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    resource: Optional[Resource] = None
    binding: Optional[GeometryBinding] = None
    failure_code: Optional[FailureCode] = None
    message: str = ""


class ResourceResolver:
    def __init__(self, graph: ResourceGraph) -> None:
        self._graph = graph

    def resolve(self, resource_id: str, motion_geometry_required: bool = False,
                active_calibrations: Optional[Iterable[Tuple[str, str]]] = None,
                scene_object_ids: Optional[Iterable[str]] = None) -> ResolutionResult:
        resource = self._graph.get(resource_id)
        if resource is None:
            return ResolutionResult(ResolutionStatus.FAILED,
                failure_code=FailureCode.RESOURCE_NOT_FOUND, message="unknown resource")
        binding = self._graph.binding(resource_id)
        if isinstance(resource, MaterialResource) and not motion_geometry_required:
            return ResolutionResult(ResolutionStatus.RESOLVED, resource=resource)
        if motion_geometry_required and binding is None:
            return ResolutionResult(ResolutionStatus.FAILED, resource=resource,
                failure_code=FailureCode.GEOMETRY_BINDING_MISSING,
                message="motion resource has no geometry binding")
        calibration_values = (getattr(active_calibrations, "revisions", active_calibrations)
                              if active_calibrations is not None else None)
        if (binding is not None and calibration_values is not None
                and not binding.calibration_satisfied_by(calibration_values)):
            return ResolutionResult(ResolutionStatus.FAILED, resource=resource, binding=binding,
                failure_code=FailureCode.CALIBRATION_MISMATCH, message="stale calibration revision")
        if binding is not None and scene_object_ids is not None:
            if binding.object_id not in set(scene_object_ids):
                return ResolutionResult(ResolutionStatus.FAILED, resource=resource, binding=binding,
                    failure_code=FailureCode.OBJECT_RESOURCE_MISMATCH,
                    message="binding object_id is absent from SceneSnapshot")
        return ResolutionResult(ResolutionStatus.RESOLVED, resource=resource, binding=binding)

    def resolve_against_snapshot(self, resource_id: str, snapshot,
                                 motion_geometry_required: bool = True) -> ResolutionResult:
        """Validate binding dependencies and object presence against one SceneSnapshot."""
        object_ids = {item.object_id for item in snapshot.environment.observation.obstacles}
        for attached in (snapshot.left_attached_object, snapshot.right_attached_object):
            if attached is not None:
                object_ids.add(attached.object_id)
        return self.resolve(resource_id, motion_geometry_required,
                            snapshot.calibration_revision, object_ids)
