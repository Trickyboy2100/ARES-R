"""Safe JSON/function schemas derived from approved semantic definitions."""

from typing import Any, Dict, Tuple

from .contracts import ParameterSpec, PlannerExposure, SkillDefinition, SkillLayer


FORBIDDEN_TOKENS = ("servo", "joint", "tcp", "base_velocity", "shell", "ros_command",
                    "safety_reset", "provider_command", "provider_id")


def _parameter_schema(spec: ParameterSpec) -> Dict[str, Any]:
    if spec.kind == "resource":
        return {"type": "string", "x-resource-types": list(spec.resource_types)}
    if spec.kind == "string": return {"type": "string"}
    if spec.kind == "boolean": return {"type": "boolean"}
    if spec.kind == "integer": return {"type": "integer"}
    if spec.kind == "number": return {"type": "number"}
    if spec.kind == "enum": return {"type": "string", "enum": list(spec.enum_values)}
    if spec.kind == "quantity":
        return {"type": "object", "additionalProperties": False,
            "required": ["value", "unit"], "properties": {
                "value": {"type": "number"},
                "unit": {"type": "string", "enum": list(spec.allowed_units)}}}
    raise ValueError("unsupported parameter kind")


def assert_safe_for_llm(definition: SkillDefinition) -> None:
    if definition.layer == SkillLayer.L0_HARDWARE:
        raise ValueError("L0 skills cannot be exported")
    searchable = [definition.skill_id]
    searchable.extend(item.name for item in definition.parameters)
    searchable.extend(item.capability_id for item in definition.required_capabilities)
    text = " ".join(searchable).lower()
    if any(token in text for token in FORBIDDEN_TOKENS):
        raise ValueError("raw control/provider surface cannot be exported")


def export_function_schema(definition: SkillDefinition) -> Dict[str, Any]:
    assert_safe_for_llm(definition)
    properties = {item.name: _parameter_schema(item) for item in definition.parameters}
    required = [item.name for item in definition.parameters if item.required]
    return {"name": definition.skill_id.replace(".", "__"),
        "description": definition.description,
        "parameters": {"type": "object", "additionalProperties": False,
                       "properties": properties, "required": required},
        "x-skill-id": definition.skill_id,
        "x-implementation-version": definition.implementation_version}


def export_registry_schemas(definitions: Tuple[SkillDefinition, ...]) -> Tuple[Dict[str, Any], ...]:
    result = []
    for definition in definitions:
        if definition.planner_exposure != PlannerExposure.LLM:
            continue
        try:
            result.append(export_function_schema(definition))
        except ValueError:
            continue
    return tuple(result)
