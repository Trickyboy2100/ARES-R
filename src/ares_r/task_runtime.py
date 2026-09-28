"""Declarative Scheme store, low-code validation and native replay runner."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from .skills.contracts import SkillInvocation, SkillResult, SkillStatus, validate_parameters
from .skills.events import EventStream
from .skills.runtime import CancellationToken, SkillContext


def canonical_digest(value):
    return "sha256:"+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8");tmp.replace(path)


class SchemeStore:
    def __init__(self,root="schemes"):
        self.root=Path(root);self.commissioned=self.root/"commissioned";self.drafts=self.root/"drafts"
        self.commissioned.mkdir(parents=True,exist_ok=True);self.drafts.mkdir(parents=True,exist_ok=True)
    def _files(self):return list(self.commissioned.glob("*.json"))+list(self.drafts.glob("*.json"))
    def list(self):
        return [{"scheme_id":v["scheme_id"],"version":v["version"],"lifecycle":v["lifecycle"],
                 "path":str(p)} for p in self._files() for v in [json.loads(p.read_text())]]
    def load(self,scheme_id):
        matches=[p for p in self._files() if json.loads(p.read_text()).get("scheme_id")==scheme_id]
        if not matches:raise KeyError("unknown scheme %s"%scheme_id)
        matches.sort(key=lambda p:(p.parent==self.drafts,p.stat().st_mtime),reverse=True)
        return json.loads(matches[0].read_text())
    def clone(self,source,new_id):
        value=json.loads(json.dumps(self.load(source)));value.update(scheme_id=new_id,version="0.1.0-draft",
            lifecycle="DRAFT",derived_from=source,draft_revision="DRAFT_"+uuid.uuid4().hex)
        path=self.drafts/(new_id+".json")
        if path.exists():raise FileExistsError("draft exists")
        atomic_json(path,value);return value
    def save_draft(self,value):
        if value.get("lifecycle") not in ("DRAFT","VALIDATED","REPLAY_VERIFIED"):
            raise ValueError("only drafts can be saved")
        if any(json.loads(p.read_text()).get("scheme_id")==value.get("scheme_id") for p in self.commissioned.glob("*.json")):
            raise ValueError("commissioned Scheme cannot be mutated in place")
        result=json.loads(json.dumps(value));result["draft_revision"]="DRAFT_"+uuid.uuid4().hex
        result["saved_at_unix"]=time.time();atomic_json(self.drafts/(result["scheme_id"]+".json"),result);return result


class SchemeValidator:
    def __init__(self,registry):self.registry=registry
    def validate(self,scheme):
        errors=[];warnings=[];nodes=scheme.get("nodes",[]);ids=[n.get("id") for n in nodes]
        if len(ids)!=len(set(ids)):errors.append("duplicate node id")
        by_id={n.get("id"):n for n in nodes}
        for node in nodes:
            try:definition=self.registry.get(node.get("skill"))
            except KeyError as exc:errors.append(str(exc));continue
            for dep in node.get("depends_on",[])+node.get("prepare_after",[]):
                if dep not in by_id:errors.append("%s references unknown dependency %s"%(node.get("id"),dep))
            params=node.get("parameters",{})
            literal={k:v for k,v in params.items() if not (isinstance(v,str) and v.startswith("$"))}
            errors.extend("%s: %s"%(node.get("id"),e) for e in validate_parameters(definition.parameter_schema,literal)
                          if not e.startswith("missing required parameter") or
                          e.rsplit(" ",1)[-1] not in params)
            for value in params.values():
                if isinstance(value,str) and value.startswith("$"):
                    source=value[1:].split(".",1)[0]
                    if source not in by_id:errors.append("%s binding source %s missing"%(node.get("id"),source))
            declared=set(node.get("resources",definition.required_resources))
            if not set(definition.required_resources).issubset(declared):
                errors.append("%s omits required resource lock"%node.get("id"))
        visiting=set();done=set()
        def visit(node_id):
            if node_id in visiting:errors.append("dependency cycle at %s"%node_id);return
            if node_id in done or node_id not in by_id:return
            visiting.add(node_id)
            for dep in by_id[node_id].get("depends_on",[]):visit(dep)
            visiting.remove(node_id);done.add(node_id)
        for node_id in ids:visit(node_id)
        return {"valid":not errors,"errors":sorted(set(errors)),"warnings":warnings,
                "scheme_id":scheme.get("scheme_id"),"node_count":len(nodes),
                "dag_digest":canonical_digest(nodes)}
    def preview(self,scheme):
        validation=self.validate(scheme)
        return {**validation,"nodes":[{"id":n["id"],"skill":n["skill"],
            "depends_on":n.get("depends_on",[]),"prepare_after":n.get("prepare_after",[]),
            "bindings":{k:v for k,v in n.get("parameters",{}).items()
                        if isinstance(v,str) and v.startswith("$")},
            "resources":n.get("resources",self.registry.get(n["skill"]).required_resources),
            "timeout_s":n.get("timeout_s",120),"on_failure":n.get("on_failure","STOP")}
            for n in scheme.get("nodes",[])]}


class SchemeRunner:
    def __init__(self,runtime,events,evidence_writer=None,clock=time.monotonic):
        self.runtime=runtime;self.events=events;self.evidence_writer=evidence_writer;self.clock=clock
        self.cancel=CancellationToken();self.status={"state":"IDLE"};self._guard=threading.Lock()
    @staticmethod
    def _resolve(value,outputs):
        if not (isinstance(value,str) and value.startswith("$")):return value
        parts=value[1:].split(".");current=outputs[parts.pop(0)]
        for part in parts:current=current[part]
        return current
    def stop(self):
        self.cancel.cancel();self.runtime.provider.cancel(None)
        with self._guard:self.status.update(state="CANCELLED",next_stage=None,prepared=[])
        self.events.emit("STOP",task_run_id=self.status.get("run_id"),reason="OPERATOR_STOP")
        return dict(self.status)
    def run(self,scheme,task_id="task.tray_to_groove",binding=None):
        run_id="RUN_"+uuid.uuid4().hex;trace_id="TRACE_"+uuid.uuid4().hex;started=self.clock()
        self.cancel=CancellationToken();outputs={};plans={};futures={};nodes={n["id"]:n for n in scheme["nodes"]}
        order=[n["id"] for n in scheme["nodes"]];pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix="scheme-prepare")
        with self._guard:self.status={"state":"RUNNING","run_id":run_id,"current_skill":None,
            "next_stage":None,"prepared":[],"started_monotonic_s":started,"scene_epoch":(binding or {}).get("scene_snapshot_id"),
            "planner_mode":None,"cycle_elapsed_s":0.0}
        self.events.emit("TASK_ACCEPTED",task_run_id=run_id,trace_id=trace_id,task_id=task_id)
        def prepare(node_id):
            node=nodes[node_id];params={k:self._resolve(v,outputs) for k,v in node.get("parameters",{}).items()}
            inv=SkillInvocation(node["skill"],params,task_id,trace_id,version=self.runtime.registry.get(node["skill"]).version)
            ctx=SkillContext(run_id,node_id,self.events,self.cancel,dict(binding or {}))
            return inv,ctx,self.runtime.prepare(inv,ctx,ttl_s=node.get("timeout_s",120)+180)
        def eligible(node,keys):return all(x in keys for x in node.get("prepare_after",node.get("depends_on",[])))
        try:
            for node_id in order:
                self.cancel.raise_if_cancelled()
                for candidate in order:
                    if candidate not in futures and candidate not in plans and eligible(nodes[candidate],outputs):
                        futures[candidate]=pool.submit(prepare,candidate)
                if node_id not in futures:futures[node_id]=pool.submit(prepare,node_id)
                with self._guard:self.status.update(current_skill=nodes[node_id]["skill"],next_stage=node_id,
                    cycle_elapsed_s=self.clock()-started)
                inv,ctx,plan=futures.pop(node_id).result()
                if isinstance(plan,SkillResult):result=plan
                else:
                    plans[node_id]=plan
                    with self._guard:self.status.update(prepared=sorted(plans),planner_mode=plan.planner_profile)
                    if not all(dep in outputs for dep in nodes[node_id].get("depends_on",[])):
                        result=SkillResult(SkillStatus.FAILED,failure_code="DEPENDENCY_NOT_SUCCEEDED")
                    else:result=self.runtime.execute(inv,plan,ctx,live_binding=binding or {},timeout_s=nodes[node_id].get("timeout_s",120))
                plans.pop(node_id,None)
                if result.status!=SkillStatus.SUCCEEDED:
                    with self._guard:self.status.update(state=result.status.value,failure_code=result.failure_code)
                    return {"run_id":run_id,"status":result.status.value,"failure_code":result.failure_code,"outputs":outputs}
                outputs[node_id]=dict(result.outputs)
                if self.evidence_writer:self.evidence_writer.submit_json("stages/%s.json"%node_id,result.to_dict())
            with self._guard:self.status.update(state="SUCCEEDED",current_skill=None,next_stage=None,prepared=[],cycle_elapsed_s=self.clock()-started)
            self.events.emit("TASK_SUCCEEDED",task_run_id=run_id,elapsed_s=self.clock()-started)
            return {"run_id":run_id,"status":"SUCCEEDED","outputs":outputs,"elapsed_s":self.clock()-started}
        except Exception as exc:
            with self._guard:self.status.update(state="CANCELLED" if self.cancel.cancelled else "FAILED",failure_code=str(exc))
            self.events.emit("FAULT",task_run_id=run_id,failure_code=str(exc));return {"run_id":run_id,"status":self.status["state"],"failure_code":str(exc),"outputs":outputs}
        finally:
            for future in futures.values():future.cancel()
            pool.shutdown(wait=True,cancel_futures=True)
            if self.evidence_writer:self.evidence_writer.flush()


def compile_runtime_package(scheme,registry,parameters,provider_revision,performance):
    body={"schema_version":1,"package_type":"TRAY_TO_GROOVE_RUNTIME_PACKAGE",
        "immutable":True,"execution_allowed":False,"scheme":scheme,
        "skill_versions":{n["skill"]:registry.get(n["skill"]).version for n in scheme["nodes"]},
        "provider_revision":provider_revision,"task_parameters":parameters,
        "planner_profiles":{"FAST":"4_2_ONE_SOLVE_NO_GRAPH","FALLBACK":"8_8_GRAPH"},
        "scene_policy":{"pickup_full_scans":1,"placement_full_scans":1,"post_grasp_normal":0},
        "contact_policy":"CONTACT_BYPASS_V1","speed_profiles":"UNCHANGED_COMMISSIONED",
        "required_authorization":"UNCHANGED_SPEED_FULL_SUPERVISED_CYCLE",
        "performance_model":performance}
    body["package_digest"]=canonical_digest(body);return body
