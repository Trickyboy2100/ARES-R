from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time

from .contracts import SkillResult, SkillStatus


class CapabilityProvider(ABC):
    revision="provider:unknown"
    @abstractmethod
    def prepare(self, definition, invocation, context): ...
    @abstractmethod
    def execute(self, definition, plan, invocation, context): ...
    def cancel(self, context): return None
    def health(self): return {"ready":True,"revision":self.revision}


class CanonicalCapabilityProvider(CapabilityProvider):
    """Thin adapter: injected callables remain the authoritative algorithms."""
    revision="canonical-services-p39-v1"
    FAST={"ik_seeds":4,"trajopt_seeds":2,"graph_attempt":False,"max_attempts":1}
    FALLBACK={"ik_seeds":8,"trajopt_seeds":8,"graph_attempt":True}
    def __init__(self, capabilities): self.capabilities=dict(capabilities)
    def _call(self, capability, phase, payload):
        fn=self.capabilities.get(capability)
        if fn is None: raise RuntimeError("PROVIDER_UNAVAILABLE:%s"%capability)
        return fn(phase,payload)
    def prepare(self, definition, invocation, context):
        payload={"parameters":dict(invocation.parameters),"binding":dict(context.binding)}
        if definition.capability in ("motion.free","motion.lift"):
            payload["planner_profile"]={"name":"FAST_4_2_ONE_SOLVE","parameters":self.FAST}
            try:return self._call(definition.capability,"prepare",payload)
            except Exception as first:
                payload["planner_profile"]={"name":"FALLBACK_8_8_GRAPH","parameters":self.FALLBACK,
                                            "fast_failure":str(first)}
        return self._call(definition.capability,"prepare",payload)
    def execute(self, definition, plan, invocation, context):
        result=self._call(definition.capability,"execute",{
            "parameters":dict(invocation.parameters),"plan":plan.provider_plan,
            "binding":dict(context.binding)})
        return result if isinstance(result,SkillResult) else SkillResult(SkillStatus.SUCCEEDED,outputs=result or {})


class ReplayCapabilityProvider(CapabilityProvider):
    revision="frozen-replay-p39-v1"
    def __init__(self, failures=None, durations=None):
        self.failures=dict(failures or {});self.durations=dict(durations or {})
        self.calls=[]
    def prepare(self, definition, invocation, context):
        self.calls.append(("prepare",definition.skill_id))
        code=self.failures.get((definition.skill_id,"prepare"))
        if code: raise RuntimeError(code)
        return {"skill_id":definition.skill_id,"parameters":dict(invocation.parameters),
                "binding":dict(context.binding),"mode":"FROZEN_REPLAY",
                "predicted_duration_s":float(self.durations.get(definition.skill_id,1.0)),
                "planner_profile":"FAST_4_2_ONE_SOLVE" if definition.capability.startswith("motion.") else None}
    def execute(self, definition, plan, invocation, context):
        self.calls.append(("execute",definition.skill_id))
        code=self.failures.get((definition.skill_id,"execute"))
        if code:return SkillResult(SkillStatus.FAILED,failure_code=code)
        outputs={"node":context.stage_id,
            "skill_id":definition.skill_id,"artifact_id":"REPLAY_"+context.stage_id,
            "scene_snapshot_id":context.binding.get("scene_snapshot_id"),
            "trajectory_hash":"sha256:replay-"+context.stage_id}
        if definition.skill_id=="manipulation.plan_transfer_chain":
            outputs.update({"selected_grasp_symmetry_id":"FLIPPED_180",
                "selected_chain":{"pregrasp":"REPLAY_PREGRASP_IK"},
                "selected_center_ik":"REPLAY_CENTER_IK",
                "transfer_chain_selection":"sha256:replay-transfer-chain"})
        return SkillResult(SkillStatus.SUCCEEDED,outputs=outputs)
