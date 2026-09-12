"""Read-only semantic-to-geometric resolver with structured failures."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

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
                calibration_revision: Optional[str] = None,
                world_objects: Optional[Mapping[str, str]] = None) -> ResolutionResult:
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
        if binding is not None and calibration_revision is not None and binding.calibration_revision != calibration_revision:
            return ResolutionResult(ResolutionStatus.FAILED, resource=resource, binding=binding,
                failure_code=FailureCode.CALIBRATION_MISMATCH, message="stale calibration revision")
        if binding is not None and world_objects is not None:
            if world_objects.get(binding.object_id) != resource_id:
                return ResolutionResult(ResolutionStatus.FAILED, resource=resource, binding=binding,
                    failure_code=FailureCode.OBJECT_RESOURCE_MISMATCH,
                    message="WorldModel object/resource mismatch")
        return ResolutionResult(ResolutionStatus.RESOLVED, resource=resource, binding=binding)
