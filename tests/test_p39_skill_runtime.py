import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from ares_r.skills import default_registry, SkillRuntime
from ares_r.skills.contracts import SkillInvocation, SkillResult, SkillStatus
from ares_r.skills.events import EventStream
from ares_r.skills.evidence import AsyncEvidenceWriter
from ares_r.skills.providers import CanonicalCapabilityProvider, ReplayCapabilityProvider
from ares_r.skills.real_provider import RealCapabilityProvider, RealServiceBundle
from ares_r.skills.runtime import CancellationToken, SkillContext
from ares_r.task_runtime import SchemeRunner, SchemeStore, SchemeValidator
from ares_r.task_studio import TaskStudio


class P39RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.events=EventStream(self.root/"events.jsonl");self.registry=default_registry()
    def tearDown(self):self.temp.cleanup()

    def invocation(self,skill="manipulation.lift",parameters=None):
        return SkillInvocation(skill,parameters or {"distance_m":.1},"task","trace")

    def test_registry_has_required_vertical_slice(self):
        ids={x["skill_id"] for x in self.registry.list()}
        self.assertTrue({"observe.capture_scene","observe.detect_resource",
            "navigate.registered_relative","manipulation.move_free","manipulation.approach",
            "manipulation.grasp","manipulation.lift","manipulation.move_above_place",
            "manipulation.release","manipulation.retreat","execution.authorize",
            "execution.execute_trajectory","manipulation.pick","manipulation.place",
            "manipulation.transfer_object"}.issubset(ids))

    def test_typed_failure_does_not_leak_exception(self):
        provider=ReplayCapabilityProvider({("manipulation.lift","prepare"):"PLAN_FAILED:no IK"})
        runtime=SkillRuntime(self.registry,provider,self.events)
        ctx=SkillContext("run","lift",self.events,CancellationToken(),{})
        result=runtime.prepare(self.invocation(),ctx)
        self.assertEqual(result.status,SkillStatus.FAILED);self.assertEqual(result.failure_code,"PLAN_FAILED")

    def test_binding_mismatch_invalidates_prepared_plan(self):
        runtime=SkillRuntime(self.registry,ReplayCapabilityProvider(),self.events)
        ctx=SkillContext("run","lift",self.events,CancellationToken(),{"scene":"A"})
        inv=self.invocation();plan=runtime.prepare(inv,ctx)
        result=runtime.execute(inv,plan,ctx,live_binding={"scene":"B"})
        self.assertEqual(result.failure_code,"BINDING_MISMATCH")
        self.assertIn("PLAN_INVALIDATED",[x["event"] for x in self.events.read()])

    def test_fast_failure_routes_to_fallback(self):
        calls=[]
        def motion(phase,payload):
            calls.append((phase,payload.get("planner_profile",{}).get("name")))
            if phase=="prepare" and payload["planner_profile"]["name"].startswith("FAST"):raise RuntimeError("no fast result")
            return {"planner_profile":payload["planner_profile"],"trajectory":"T"}
        provider=CanonicalCapabilityProvider({"motion.lift":motion})
        runtime=SkillRuntime(self.registry,provider,self.events)
        ctx=SkillContext("run","lift",self.events,CancellationToken(),{})
        plan=runtime.prepare(self.invocation(),ctx)
        self.assertEqual(plan.planner_profile,"FALLBACK_8_8_GRAPH")
        self.assertEqual([x[1] for x in calls],["FAST_4_2_ONE_SOLVE","FALLBACK_8_8_GRAPH"])

    def test_async_evidence_writes_and_backpressure_is_typed(self):
        writer=AsyncEvidenceWriter(self.root/"evidence",max_queue=2)
        writer.submit_json("a.json",{"a":1},block=True);writer.close()
        self.assertEqual(json.loads((self.root/"evidence/a.json").read_text()),{"a":1})
        with self.assertRaisesRegex(RuntimeError,"closed"):writer.submit_json("b.json",{})

    def test_cancelled_token_prevents_prepare(self):
        runtime=SkillRuntime(self.registry,ReplayCapabilityProvider(),self.events)
        cancel=CancellationToken();cancel.cancel();ctx=SkillContext("run","lift",self.events,cancel,{})
        with self.assertRaisesRegex(RuntimeError,"CANCELLED"):runtime.prepare(self.invocation(),ctx)

    def test_scheme_validation_detects_cycle_and_bad_binding(self):
        scheme={"scheme_id":"bad","nodes":[
            {"id":"a","skill":"observe.verify_predicate","parameters":{"predicate":"$missing.x"},"depends_on":["b"],"resources":["SCENE_EPOCH"]},
            {"id":"b","skill":"observe.verify_predicate","parameters":{"predicate":"ok"},"depends_on":["a"],"resources":["SCENE_EPOCH"]}]}
        result=SchemeValidator(self.registry).validate(scheme)
        self.assertFalse(result["valid"]);self.assertTrue(any("cycle" in x for x in result["errors"]))
        self.assertTrue(any("binding" in x for x in result["errors"]))

    def test_runner_replay_and_gripper_fault(self):
        scheme={"scheme_id":"mini","nodes":[
            {"id":"scene","skill":"observe.capture_scene","parameters":{},"depends_on":[],"resources":["CAMERA_5000","SCENE_EPOCH"]},
            {"id":"grasp","skill":"manipulation.grasp","parameters":{"opening_percent":40},"depends_on":["scene"],"prepare_after":["scene"],"resources":["GRIPPER_RIGHT","ARM_RIGHT"]}]}
        provider=ReplayCapabilityProvider({("manipulation.grasp","execute"):"GRASP_NOT_VERIFIED"})
        runtime=SkillRuntime(self.registry,provider,self.events);runner=SchemeRunner(runtime,self.events)
        result=runner.run(scheme,binding={})
        self.assertEqual(result["status"],"FAILED");self.assertEqual(result["failure_code"],"GRASP_NOT_VERIFIED")

    def test_low_code_store_never_mutates_commissioned(self):
        store=SchemeStore(self.root/"schemes");original={"scheme_id":"source","version":"1","lifecycle":"COMMISSIONED","nodes":[]}
        (store.commissioned/"source.json").write_text(json.dumps(original))
        draft=store.clone("source","copy");draft["description"]="edited";store.save_draft(draft)
        self.assertEqual(store.load("source"),original)
        with self.assertRaisesRegex(ValueError,"cannot be mutated"):store.save_draft({**original,"lifecycle":"DRAFT"})

    def test_real_provider_delegates_and_coalesces_observation(self):
        class Service:
            def __init__(self):self.calls=[]
            def capture(self,profile):self.calls.append(profile);return {"profile":profile,"request_id":"D"}
            def __getattr__(self,name):return lambda payload:self.calls.append(name) or {"method":name}
        obs=Service();service=Service();bundle=RealServiceBundle(obs,service,service,service,service,service,service,service)
        provider=RealCapabilityProvider(bundle)
        scene=self.registry.get("observe.capture_scene");detect=self.registry.get("observe.detect_resource")
        ctx=SkillContext("run","obs",self.events,CancellationToken(),{})
        for definition in (scene,detect):
            inv=SkillInvocation(definition.skill_id,{"profile":"right_pick"},"task","trace")
            prepared=provider.prepare(definition,inv,ctx)
            class Plan:provider_plan=prepared
            provider.execute(definition,Plan(),inv,ctx)
        self.assertEqual(obs.calls,["right_pick"])


if __name__=="__main__":unittest.main()
