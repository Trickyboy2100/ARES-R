from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import time
import uuid
from typing import Any, Mapping, Optional, Sequence


class SkillStatus(str, Enum):
    PREPARED = "PREPARED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    version: str
    category: str
    description: str
    parameter_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    required_resources: Sequence[str] = ()
    maturity: str = "REPLAY_VERIFIED"
    capability: str = ""
    composite: bool = False

    def to_dict(self): return asdict(self)


@dataclass(frozen=True)
class SkillInvocation:
    skill_id: str
    parameters: Mapping[str, Any]
    task_id: str
    trace_id: str
    invocation_id: str = field(default_factory=lambda: "INV_" + uuid.uuid4().hex)
    version: str = "1.0.0"


@dataclass(frozen=True)
class SkillPlan:
    plan_id: str
    invocation_id: str
    required_locks: Sequence[str]
    provider_plan: Mapping[str, Any]
    binding: Mapping[str, Any]
    expires_at_monotonic: float
    planner_profile: Optional[str] = None

    def valid_now(self, clock=time.monotonic): return clock() <= self.expires_at_monotonic


@dataclass(frozen=True)
class SkillResult:
    status: SkillStatus
    outputs: Mapping[str, Any] = field(default_factory=dict)
    failure_code: Optional[str] = None
    message: str = ""
    timings_s: Mapping[str, float] = field(default_factory=dict)
    evidence_refs: Sequence[str] = ()

    def to_dict(self):
        value = asdict(self); value["status"] = self.status.value; return value


def validate_parameters(schema: Mapping[str, Any], value: Mapping[str, Any]) -> list[str]:
    errors = []
    for name in schema.get("required", ()):
        if name not in value: errors.append("missing required parameter %s" % name)
    properties = schema.get("properties", {})
    for name, item in value.items():
        spec = properties.get(name)
        if spec is None:
            if schema.get("additionalProperties") is False:
                errors.append("unknown parameter %s" % name)
            continue
        kind = spec.get("type")
        accepted = {"string": str, "number": (int, float), "integer": int,
                    "boolean": bool, "object": dict, "array": list}.get(kind)
        if accepted and (not isinstance(item, accepted) or
                         kind in ("number", "integer") and isinstance(item, bool)):
            errors.append("parameter %s must be %s" % (name, kind))
        if "enum" in spec and item not in spec["enum"]:
            errors.append("parameter %s must be one of %s" % (name, spec["enum"]))
        if isinstance(item, (int, float)):
            if "minimum" in spec and item < spec["minimum"]: errors.append("parameter %s below minimum" % name)
            if "maximum" in spec and item > spec["maximum"]: errors.append("parameter %s above maximum" % name)
    return errors
