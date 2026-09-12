"""Immutable definitions forming the public Skill Library ABI."""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Tuple

from .failures import FailureCode
from .maturity import SkillMaturity
from .serialization import pairs


class SkillLayer(str, Enum):
    L0_HARDWARE = "L0_HARDWARE"
    L1_BASIC = "L1_BASIC"
    L2_MANIPULATION = "L2_MANIPULATION"
    L3_LABORATORY = "L3_LABORATORY"
    L4_PROTOCOL = "L4_PROTOCOL"


class PlannerExposure(str, Enum):
    INTERNAL = "INTERNAL"
    PLANNER = "PLANNER"
    LLM = "LLM"


class SafetyClass(str, Enum):
    S0_INFORMATIONAL = "S0_INFORMATIONAL"
    S1_REVERSIBLE = "S1_REVERSIBLE"
    S2_MOTION = "S2_MOTION"
    S3_PROCESS = "S3_PROCESS"


class LockMode(str, Enum):
    SHARED_READ = "SHARED_READ"
    EXCLUSIVE_STATE = "EXCLUSIVE_STATE"
    EXCLUSIVE_MOTION = "EXCLUSIVE_MOTION"


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    kind: str
    required: bool = True
    description: str = ""
    resource_types: Tuple[str, ...] = ()
    enum_values: Tuple[str, ...] = ()
    allowed_units: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        valid = ("resource", "string", "boolean", "integer", "number", "quantity", "enum")
        if not self.name or self.kind not in valid:
            raise ValueError("invalid parameter specification")
        object.__setattr__(self, "resource_types", tuple(sorted(set(self.resource_types))))
        object.__setattr__(self, "enum_values", tuple(sorted(set(self.enum_values))))
        object.__setattr__(self, "allowed_units", tuple(sorted(set(self.allowed_units))))
        if self.kind == "resource" and not self.resource_types:
            raise ValueError("resource parameters require resource_types")
        if self.kind == "enum" and not self.enum_values:
            raise ValueError("enum parameters require enum_values")
        if self.kind == "quantity" and not self.allowed_units:
            raise ValueError("quantity parameters require explicit allowed_units")


@dataclass(frozen=True)
class ResourceRequirement:
    selector: str
    resource_types: Tuple[str, ...]
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.selector or not self.resource_types:
            raise ValueError("resource requirement must be typed")
        object.__setattr__(self, "resource_types", tuple(sorted(set(self.resource_types))))


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: str
    minimum_protocol_version: int = 1

    def __post_init__(self) -> None:
        if not self.capability_id or type(self.minimum_protocol_version) is not int or self.minimum_protocol_version < 1:
            raise ValueError("capability requirement identity is required")


@dataclass(frozen=True)
class ObservationRequirement:
    modality: str
    max_age_s: float
    minimum_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.modality or not math.isfinite(self.max_age_s) or self.max_age_s <= 0:
            raise ValueError("invalid observation requirement")
        if not math.isfinite(self.minimum_confidence) or not 0 <= self.minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be in 0..1")


@dataclass(frozen=True)
class LockIntent:
    intent_id: str
    selector: str
    mode: LockMode

    def __post_init__(self) -> None:
        if not self.intent_id or not self.selector or ":" not in self.selector:
            raise ValueError("lock intent identity and typed selector are required")
        object.__setattr__(self, "mode", LockMode(self.mode))


@dataclass(frozen=True)
class TimeoutPolicy:
    planning_s: float
    execution_s: float
    verification_s: float

    def __post_init__(self) -> None:
        values = (self.planning_s, self.execution_s, self.verification_s)
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("timeout values must be finite and positive")


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    schema_version: int
    implementation_version: str
    description: str
    layer: SkillLayer
    category: str
    parameters: Tuple[ParameterSpec, ...]
    required_capabilities: Tuple[CapabilityRequirement, ...]
    required_resources: Tuple[ResourceRequirement, ...]
    preconditions: Tuple[str, ...]
    invariants: Tuple[str, ...]
    expected_effects: Tuple[str, ...]
    observation_requirements: Tuple[ObservationRequirement, ...]
    lock_intents: Tuple[LockIntent, ...]
    timeout: TimeoutPolicy
    failure_codes: Tuple[FailureCode, ...]
    planner_exposure: PlannerExposure
    safety_class: SafetyClass
    maturity: SkillMaturity = SkillMaturity.SPECIFIED
    motion_bearing: bool = False

    def __post_init__(self) -> None:
        if not self.skill_id or "." not in self.skill_id or self.schema_version < 1:
            raise ValueError("skill_id namespace and positive schema_version are required")
        if not self.implementation_version or not self.description or not self.category:
            raise ValueError("skill version, description and category are required")
        object.__setattr__(self, "layer", SkillLayer(self.layer))
        object.__setattr__(self, "planner_exposure", PlannerExposure(self.planner_exposure))
        object.__setattr__(self, "safety_class", SafetyClass(self.safety_class))
        object.__setattr__(self, "maturity", SkillMaturity(self.maturity))
        parameters = tuple(self.parameters)
        if len({item.name for item in parameters}) != len(parameters):
            raise ValueError("parameter names must be unique")
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))
        object.__setattr__(self, "required_resources", tuple(self.required_resources))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(self, "invariants", tuple(self.invariants))
        object.__setattr__(self, "expected_effects", tuple(self.expected_effects))
        object.__setattr__(self, "observation_requirements", tuple(self.observation_requirements))
        lock_intents = tuple(self.lock_intents)
        if len({item.intent_id for item in lock_intents}) != len(lock_intents):
            raise ValueError("lock intent IDs must be unique")
        object.__setattr__(self, "lock_intents", lock_intents)
        object.__setattr__(self, "failure_codes", tuple(FailureCode(item) for item in self.failure_codes))


def immutable_parameters(value: Any) -> Tuple[Tuple[str, Any], ...]:
    return pairs(value, "parameters")
