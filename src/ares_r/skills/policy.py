"""LLM proposal validation. This module never resolves or calls a provider."""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping, Optional

from .contracts import (ParameterSpec, PlannerExposure, SafetyClass, SkillLayer)
from .failures import FailureCode
from .invocation import SkillInvocation
from .maturity import MaturityEvidence, SkillMaturity
from .registry import SkillRegistry
from .schema_export import assert_safe_for_llm
from ares_r.workspace.resource_graph import ResourceGraph


@dataclass(frozen=True)
class ProposalResult:
    invocation: Optional[SkillInvocation]
    failure_code: Optional[FailureCode]
    message: str = ""

    @property
    def accepted(self) -> bool:
        return self.invocation is not None


class DeploymentMode(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    MOCK = "MOCK"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class LlmProposalPolicy:
    minimum_maturity: SkillMaturity
    allowed_safety_classes: tuple
    deployment_mode: DeploymentMode
    allowlisted_skill_ids: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "minimum_maturity", SkillMaturity(self.minimum_maturity))
        object.__setattr__(self, "deployment_mode", DeploymentMode(self.deployment_mode))
        classes = tuple(sorted((SafetyClass(item) for item in self.allowed_safety_classes), key=lambda item: item.value))
        if not classes:
            raise ValueError("at least one safety class must be allowed")
        object.__setattr__(self, "allowed_safety_classes", classes)
        object.__setattr__(self, "allowlisted_skill_ids", tuple(sorted(set(self.allowlisted_skill_ids))))

    @classmethod
    def development(cls):
        return cls(SkillMaturity.SPECIFIED, tuple(SafetyClass), DeploymentMode.DEVELOPMENT)

    @classmethod
    def mock(cls):
        return cls(SkillMaturity.MOCK_VERIFIED, tuple(SafetyClass), DeploymentMode.MOCK)

    @classmethod
    def production(cls):
        return cls(SkillMaturity.REAL_COMMISSIONED, tuple(SafetyClass), DeploymentMode.PRODUCTION)


def _valid(spec: ParameterSpec, value: Any, workspace: ResourceGraph) -> bool:
    if spec.kind == "resource":
        resource = workspace.get(value) if isinstance(value, str) else None
        return resource is not None and resource.type_name in spec.resource_types
    if spec.kind == "string": return isinstance(value, str)
    if spec.kind == "boolean": return type(value) is bool
    if spec.kind == "integer": return type(value) is int
    if spec.kind == "number": return type(value) in (int, float) and math.isfinite(value)
    if spec.kind == "enum": return isinstance(value, str) and value in spec.enum_values
    if spec.kind == "quantity":
        if not isinstance(value, Mapping) or set(value) != {"value", "unit"}:
            return False
        number = value["value"]
        return type(number) in (int, float) and math.isfinite(number) and value["unit"] in spec.allowed_units
    return False


def create_llm_proposal(registry: SkillRegistry, workspace: ResourceGraph,
                        policy: LlmProposalPolicy, skill_id: str,
                        parameters: Mapping[str, Any],
                        invocation_id: str, requested_at_unix_ns: int,
                        idempotency_key: str,
                        maturity_evidence: Optional[MaturityEvidence] = None) -> ProposalResult:
    try:
        definition = registry.get(skill_id)
        assert_safe_for_llm(definition)
    except (KeyError, ValueError) as error:
        return ProposalResult(None, FailureCode.SAFETY_REJECTED, str(error))
    if definition.planner_exposure != PlannerExposure.LLM or definition.layer == SkillLayer.L0_HARDWARE:
        return ProposalResult(None, FailureCode.SAFETY_REJECTED, "skill is not LLM exposed")
    if definition.safety_class not in policy.allowed_safety_classes:
        return ProposalResult(None, FailureCode.SAFETY_REJECTED, "safety class is not allowed")
    if policy.allowlisted_skill_ids and skill_id not in policy.allowlisted_skill_ids:
        return ProposalResult(None, FailureCode.SAFETY_REJECTED, "skill is not deployment-allowlisted")
    effective_maturity = definition.maturity
    if maturity_evidence is not None:
        key = maturity_evidence.key
        if key.skill_id != definition.skill_id or key.implementation_version != definition.implementation_version:
            return ProposalResult(None, FailureCode.SAFETY_REJECTED, "maturity evidence scope mismatch")
        effective_maturity = maturity_evidence.maturity
    if effective_maturity < policy.minimum_maturity:
        return ProposalResult(None, FailureCode.SAFETY_REJECTED,
                              "deployment maturity policy is not satisfied")
    specs = {item.name: item for item in definition.parameters}
    if set(parameters) - set(specs):
        return ProposalResult(None, FailureCode.INVALID_INPUT, "unknown parameter keys")
    if any(item.required and item.name not in parameters for item in specs.values()):
        return ProposalResult(None, FailureCode.INVALID_INPUT, "required parameter missing")
    if any(not _valid(specs[key], value, workspace) for key, value in parameters.items()):
        return ProposalResult(None, FailureCode.INVALID_INPUT, "malformed or untyped parameter")
    invocation = SkillInvocation(invocation_id, definition.skill_id,
        definition.implementation_version, tuple(parameters.items()), "llm",
        requested_at_unix_ns, workspace.revision, idempotency_key)
    return ProposalResult(invocation, None)
