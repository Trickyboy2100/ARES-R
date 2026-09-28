from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
import uuid

from .contracts import SkillPlan, SkillResult, SkillStatus, validate_parameters
from .locks import ResourceLockManager


class CancellationToken:
    def __init__(self):self._event=threading.Event()
    def cancel(self):self._event.set()
    @property
    def cancelled(self):return self._event.is_set()
    def raise_if_cancelled(self):
        if self.cancelled:raise RuntimeError("CANCELLED")


@dataclass
class SkillContext:
    run_id:str;stage_id:str;events:object;cancel:CancellationToken
    binding:dict=field(default_factory=dict)


class SkillRuntime:
    def __init__(self,registry,provider,events,locks=None,clock=time.monotonic):
        self.registry=registry;self.provider=provider;self.events=events
        self.locks=locks or ResourceLockManager();self.clock=clock
    def prepare(self,invocation,context,ttl_s=300):
        definition=self.registry.get(invocation.skill_id)
        errors=validate_parameters(definition.parameter_schema,invocation.parameters)
        if errors:return SkillResult(SkillStatus.FAILED,failure_code="INPUT_SCHEMA",message="; ".join(errors))
        context.cancel.raise_if_cancelled();started=self.clock()
        context.events.emit("STAGE_PREPARING",task_run_id=context.run_id,stage_id=context.stage_id,skill_id=definition.skill_id)
        try:payload=self.provider.prepare(definition,invocation,context)
        except Exception as exc:
            return SkillResult(SkillStatus.FAILED,failure_code=str(exc).split(":",1)[0],message=str(exc))
        profile=payload.get("planner_profile")
        plan=SkillPlan("PLAN_"+uuid.uuid4().hex,invocation.invocation_id,
            tuple(definition.required_resources),payload,dict(context.binding),self.clock()+ttl_s,
            profile if isinstance(profile,str) else (profile or {}).get("name"))
        context.events.emit("STAGE_PREPARED",task_run_id=context.run_id,stage_id=context.stage_id,
                            skill_id=definition.skill_id,plan_id=plan.plan_id,
                            planner_profile=plan.planner_profile,elapsed_s=self.clock()-started)
        return plan
    def execute(self,invocation,plan,context,live_binding=None,timeout_s=120):
        definition=self.registry.get(invocation.skill_id)
        if not plan.valid_now(self.clock):return SkillResult(SkillStatus.FAILED,failure_code="PLAN_EXPIRED")
        if live_binding is not None and dict(live_binding)!=dict(plan.binding):
            context.events.emit("PLAN_INVALIDATED",task_run_id=context.run_id,stage_id=context.stage_id,
                                skill_id=definition.skill_id,reason="BINDING_MISMATCH")
            return SkillResult(SkillStatus.FAILED,failure_code="BINDING_MISMATCH")
        if context.cancel.cancelled:return SkillResult(SkillStatus.CANCELLED,failure_code="CANCELLED")
        started=self.clock()
        try:
            with self.locks.acquire(plan.required_locks,timeout_s):
                context.events.emit("LOCK_ACQUIRED",task_run_id=context.run_id,stage_id=context.stage_id,
                                    skill_id=definition.skill_id,resources=list(plan.required_locks))
                context.events.emit("STAGE_EXECUTING",task_run_id=context.run_id,stage_id=context.stage_id,
                                    skill_id=definition.skill_id)
                result=self.provider.execute(definition,plan,invocation,context)
        except TimeoutError as exc:result=SkillResult(SkillStatus.FAILED,failure_code="RESOURCE_BUSY",message=str(exc))
        except Exception as exc:result=SkillResult(SkillStatus.FAILED,failure_code="INTERNAL",message=str(exc))
        finally:
            context.events.emit("LOCK_RELEASED",task_run_id=context.run_id,stage_id=context.stage_id,
                                skill_id=definition.skill_id,resources=list(plan.required_locks))
        event="STAGE_SUCCEEDED" if result.status==SkillStatus.SUCCEEDED else "STAGE_FAILED"
        context.events.emit(event,task_run_id=context.run_id,stage_id=context.stage_id,
                            skill_id=definition.skill_id,failure_code=result.failure_code,
                            elapsed_s=self.clock()-started)
        return result
