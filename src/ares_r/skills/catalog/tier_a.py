"""The 14 S0 Tier-A definitions. Definitions only; no running logic."""

from typing import Tuple

from ..contracts import (CapabilityRequirement as Cap, LockIntent as Lock, LockMode,
    ObservationRequirement as Obs, ParameterSpec as Param, PlannerExposure,
    ResourceRequirement as Res, SafetyClass, SkillDefinition, SkillLayer,
    TimeoutPolicy)
from ..failures import FailureCode as F
from ..maturity import SkillMaturity
from ..registry import SkillRegistry


COMMON_FAILURES = (F.INVALID_INPUT, F.RESOURCE_NOT_FOUND, F.RESOURCE_BUSY,
                   F.PRECONDITION_FALSE, F.TIMED_OUT, F.SAFETY_REJECTED)


def _skill(skill_id: str, layer: SkillLayer, description: str,
           parameters: Tuple[Param, ...], capabilities: Tuple[str, ...],
           resources: Tuple[Res, ...], motion: bool,
           effects: Tuple[str, ...],
           exposure: PlannerExposure = PlannerExposure.LLM) -> SkillDefinition:
    lock_intents = [Lock("resource.%s" % item.selector,
        "resource_parameter:%s" % item.selector,
        LockMode.EXCLUSIVE_MOTION if motion else LockMode.EXCLUSIVE_STATE)
        for item in resources]
    if motion:
        lock_intents.append(Lock("zone.manipulation", "zone:manipulation",
                                 LockMode.EXCLUSIVE_MOTION))
    if any(item.name == "arm" for item in parameters):
        lock_intents.extend((
            Lock("arm.selected", "arm_parameter:arm", LockMode.EXCLUSIVE_MOTION),
            Lock("gripper.selected", "gripper_parameter:arm", LockMode.EXCLUSIVE_MOTION)))
    return SkillDefinition(skill_id, 1, "1.0.0", description, layer,
        skill_id.split(".")[0], parameters, tuple(Cap(item) for item in capabilities),
        resources, ("resources_resolved",), ("declared_locks_held",), effects,
        (Obs("workspace_state", 30.0),),
        tuple(lock_intents), TimeoutPolicy(10, 60, 10), COMMON_FAILURES,
        exposure, SafetyClass.S2_MOTION if motion else SafetyClass.S1_REVERSIBLE,
        SkillMaturity.SPECIFIED, motion)


R = Param
ARM = Param("arm", "enum", False, enum_values=("left", "right", "auto"))
TIER_A_SKILLS = (
    _skill("observe.capture_scene", SkillLayer.L1_BASIC, "Capture a coherent scene observation.",
           (R("station", "resource", False, resource_types=("Station",)),),
           ("scene.capture",), (), False, ("observation_epoch_committed",), PlannerExposure.PLANNER),
    _skill("observe.detect_resource", SkillLayer.L1_BASIC, "Detect a named resource in the current observation.",
           (R("resource", "resource", resource_types=("Container", "Device", "Fixture", "Tool")),),
           ("scene.detect",), (Res("resource", ("Container", "Device", "Fixture", "Tool")),), False,
           ("detection_evidence_recorded",), PlannerExposure.PLANNER),
    _skill("observe.verify_predicate", SkillLayer.L1_BASIC, "Verify a semantic predicate using configured evidence.",
           (R("subject", "resource", resource_types=("Container", "Device", "Fixture", "Holder", "Slot", "Port")),
            R("predicate", "string")), ("predicate.verify",),
           (Res("subject", ("Container", "Device", "Fixture", "Holder", "Slot", "Port")),), False,
           ("predicate_evidence_recorded",), PlannerExposure.PLANNER),
    _skill("navigate.go_to_station", SkillLayer.L1_BASIC, "Navigate to a named station docking pose.",
           (R("station", "resource", resource_types=("Station",)),), ("base.navigate",),
           (Res("station", ("Station",)),), True, ("base_at_station",)),
    _skill("manipulation.grasp", SkillLayer.L1_BASIC, "Grasp and verify attachment of a physical resource.",
           (R("object", "resource", resource_types=("Container", "Tool")), ARM),
           ("motion.plan", "motion.execute", "gripper.command", "grasp.verify"),
           (Res("object", ("Container", "Tool")),), True, ("object_attached",), PlannerExposure.PLANNER),
    _skill("manipulation.release", SkillLayer.L1_BASIC, "Release an attached resource at a named destination.",
           (R("object", "resource", resource_types=("Container", "Tool")),
            R("destination", "resource", resource_types=("Holder", "Slot", "Port"))),
           ("motion.plan", "motion.execute", "gripper.command", "release.verify"),
           (Res("object", ("Container", "Tool")), Res("destination", ("Holder", "Slot", "Port"))), True,
           ("object_detached",), PlannerExposure.PLANNER),
    _skill("manipulation.pick", SkillLayer.L2_MANIPULATION, "Pick a physical resource.",
           (R("object", "resource", resource_types=("Container", "Tool")), ARM),
           ("scene.observe", "motion.plan", "motion.execute", "gripper.command", "grasp.verify"),
           (Res("object", ("Container", "Tool")),), True, ("object_attached", "source_vacated")),
    _skill("manipulation.place", SkillLayer.L2_MANIPULATION, "Place a held resource into a named location.",
           (R("object", "resource", resource_types=("Container", "Tool")),
            R("destination", "resource", resource_types=("Holder", "Slot", "Port"))),
           ("motion.plan", "motion.execute", "gripper.command", "placement.verify"),
           (Res("object", ("Container", "Tool")), Res("destination", ("Holder", "Slot", "Port"))), True,
           ("object_located_at_destination",)),
    _skill("manipulation.transfer_object", SkillLayer.L2_MANIPULATION, "Transfer a resource between named locations.",
           (R("object", "resource", resource_types=("Container", "Tool")),
            R("destination", "resource", resource_types=("Holder", "Slot", "Port"))),
           ("motion.plan", "motion.execute", "gripper.command", "placement.verify"),
           (Res("object", ("Container", "Tool")), Res("destination", ("Holder", "Slot", "Port"))), True,
           ("object_located_at_destination",)),
    _skill("manipulation.press", SkillLayer.L2_MANIPULATION, "Press a named control affordance.",
           (R("control", "resource", resource_types=("Fixture", "Device")),),
           ("motion.plan", "motion.execute", "control.verify"),
           (Res("control", ("Fixture", "Device")),), True, ("control_state_changed",), PlannerExposure.PLANNER),
    _skill("manipulation.turn", SkillLayer.L2_MANIPULATION, "Turn a named rotary control to a typed setting.",
           (R("control", "resource", resource_types=("Fixture", "Device")),
            R("target", "quantity", allowed_units=("rad", "deg", "percent"))),
           ("motion.plan", "motion.execute", "control.verify"),
           (Res("control", ("Fixture", "Device")),), True, ("control_setting_verified",), PlannerExposure.PLANNER),
    _skill("device.load", SkillLayer.L2_MANIPULATION, "Load a payload into a named device slot or port.",
           (R("device", "resource", resource_types=("Device",)),
            R("payload", "resource", resource_types=("Container", "Tool")),
            R("destination", "resource", resource_types=("Slot", "Port"))),
           ("motion.plan", "motion.execute", "loading.verify"),
           (Res("device", ("Device",)), Res("payload", ("Container", "Tool")),
            Res("destination", ("Slot", "Port"))), True, ("payload_loaded",)),
    _skill("device.start", SkillLayer.L2_MANIPULATION, "Start an approved configured device program.",
           (R("device", "resource", resource_types=("Device",)), R("program", "string"),
            R("duration", "quantity", False, allowed_units=("s", "min"))),
           ("device.start", "device.status"), (Res("device", ("Device",)),), False,
           ("device_run_started",)),
    _skill("lab.measure", SkillLayer.L3_LABORATORY, "Acquire a traceable measurement for a material or container.",
           (R("subject", "resource", resource_types=("Sample", "Container")),
            R("instrument", "resource", resource_types=("Device",)), R("method", "string")),
           ("device.measure", "measurement.verify"),
           (Res("subject", ("Sample", "Container")), Res("instrument", ("Device",))), False,
           ("measurement_recorded",)),
)


def build_tier_a_registry() -> SkillRegistry:
    registry = SkillRegistry()
    for definition in TIER_A_SKILLS:
        registry.register(definition)
    return registry
