"""Shared ART/WebUI low-code Task Studio backend."""

from __future__ import annotations

import json
from pathlib import Path
import threading

from .skills import default_registry, SkillRuntime
from .skills.events import EventStream
from .skills.evidence import AsyncEvidenceWriter
from .skills.providers import ReplayCapabilityProvider
from .task_runtime import (SchemeRunner, SchemeStore, SchemeValidator, atomic_json,
                           compile_runtime_package)


class TaskStudio:
    def __init__(self,root="."):
        self.root=Path(root);self.registry=default_registry();self.store=SchemeStore(self.root/"schemes")
        self.state_root=self.root/"worklog/runtime/p39";self.state_root.mkdir(parents=True,exist_ok=True)
        self.state_path=self.state_root/"runtime_status.json";self._runner=None;self._thread=None
    def skill_list(self):return self.registry.list()
    def skill_show(self,skill_id):return self.registry.get(skill_id).to_dict()
    def scheme_list(self):return self.store.list()
    def scheme_show(self,scheme_id):return self.store.load(scheme_id)
    def scheme_clone(self,source,new_id):return self.store.clone(source,new_id)
    def scheme_validate(self,scheme_or_id):
        value=self.store.load(scheme_or_id) if isinstance(scheme_or_id,str) else scheme_or_id
        return SchemeValidator(self.registry).validate(value)
    def scheme_preview(self,scheme_or_id):
        value=self.store.load(scheme_or_id) if isinstance(scheme_or_id,str) else scheme_or_id
        return SchemeValidator(self.registry).preview(value)
    def scheme_save_draft(self,value):
        validation=SchemeValidator(self.registry).validate(value)
        if not validation["valid"]:raise ValueError("invalid draft: "+"; ".join(validation["errors"]))
        result=dict(value);result["lifecycle"]="VALIDATED";return self.store.save_draft(result)
    def task_list(self):
        result=[]
        for path in sorted((self.root/"tasks").glob("*.json")):
            value=json.loads(path.read_text());result.append({**value,"path":str(path)})
        return result
    def task_show(self,task_id):
        for value in self.task_list():
            if value.get("task_id")==task_id:return value
        raise KeyError("unknown task %s"%task_id)
    def prepare(self,task_id):
        task=self.task_show(task_id);scheme=self.store.load(task["scheme_id"])
        validation=SchemeValidator(self.registry).validate(scheme)
        if not validation["valid"]:raise ValueError("invalid Scheme")
        package=compile_runtime_package(scheme,self.registry,task.get("parameters",{}),
            "canonical-services-p39-v1",{"phase1_modeled_total_cycle_s":395.0})
        path=self.state_root/"packages"/(package["package_digest"].replace(":","_")+".json")
        atomic_json(path,package);state={"state":"PREPARED_REPLAY_ONLY","task_id":task_id,
            "package":str(path),"package_digest":package["package_digest"],"execution_enabled":False}
        atomic_json(self.state_path,state);return state
    def replay(self,task_id,failures=None):
        task=self.task_show(task_id);scheme=self.store.load(task["scheme_id"])
        validation=SchemeValidator(self.registry).validate(scheme)
        if not validation["valid"]:raise ValueError(validation["errors"])
        run_root=self.state_root/"runs";run_root.mkdir(parents=True,exist_ok=True)
        events=EventStream(run_root/(task_id.replace(".","_")+"_events.jsonl"))
        evidence=AsyncEvidenceWriter(run_root/(task_id.replace(".","_")+"_evidence"))
        provider=ReplayCapabilityProvider(failures=failures);runtime=SkillRuntime(self.registry,provider,events)
        runner=SchemeRunner(runtime,events,evidence);self._runner=runner
        result=runner.run(scheme,task_id,binding={"scene_snapshot_id":"FROZEN_PICK_PLACE",
            "tool_revision":"FROZEN_TOOL","attachment_revision":"FROZEN_ATTACHMENT"})
        evidence.close();result["provider_calls"]=provider.calls;atomic_json(self.state_path,{**runner.status,"result":result})
        return result
    def start_replay(self,task_id):
        if self._thread and self._thread.is_alive():raise RuntimeError("task replay already running")
        holder={}
        def target():
            try:holder["result"]=self.replay(task_id)
            except Exception as exc:
                atomic_json(self.state_path,{"state":"FAILED","failure_code":"%s: %s"%(type(exc).__name__,exc)})
        self._thread=threading.Thread(target=target,name="p39-replay",daemon=True);self._thread.start()
        return {"state":"REPLAY_STARTED","task_id":task_id,"execution_enabled":False}
    def status(self):
        if self._runner:return dict(self._runner.status)
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else {"state":"IDLE"}
    def stop(self):
        if self._runner:return self._runner.stop()
        value={"state":"STOPPED","reason":"OPERATOR_STOP","execution_enabled":False};atomic_json(self.state_path,value);return value
