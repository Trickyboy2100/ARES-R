"""Real vertical-slice provider that delegates to canonical ARES-R services.

The bundle is deliberately dependency-injected: this layer never reimplements
scene reconstruction, cuRobo, ServoJ, gripper, AMR or contact algorithms.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import threading

from .providers import CanonicalCapabilityProvider


@dataclass
class RealServiceBundle:
    observation_v2: object
    base: object
    motion: object
    contact: object
    gripper: object
    authorization: object
    executor: object
    verification: object
    alignment: object = None
    grasp_symmetry: object = None
    transfer_chain: object = None


class RealCapabilityProvider(CanonicalCapabilityProvider):
    revision="real-existing-services-p39-v1"
    def __init__(self,bundle):
        self.bundle=bundle;self._observation={};self._guard=threading.Lock()
        super().__init__({
            "scene.capture":self._observation_call,
            "resource.detect":self._observation_call,
            "predicate.verify":self._verify,
            "base.navigate":self._base,
            "base.align_for_manipulation":self._align,
            "motion.free":self._motion,
            "manipulation.select_grasp_symmetry":self._grasp_symmetry,
            "manipulation.plan_transfer_chain":self._transfer_chain,
            "motion.lift":self._contact,
            "motion.contact":self._contact,
            "gripper.grasp":self._gripper,
            "gripper.release":self._gripper,
            "execution.authorize":self._authorize,
            "motion.execute":self._execute,
        })
    def _observation_call(self,phase,payload):
        profile=payload["parameters"].get("profile","right_pick")
        if phase=="prepare":return {"profile":profile,"coalesced_observation_v2":True}
        with self._guard:
            if profile not in self._observation:
                self._observation[profile]=self.bundle.observation_v2.capture(profile)
            return self._observation[profile]
    def _base(self,phase,payload):
        if phase=="prepare":return self.bundle.base.prepare_registered(payload)
        return self.bundle.base.execute_registered(payload)
    def _align(self,phase,payload):
        from ares_r.motion.manipulation_alignment import AlignmentBounds, AlignmentRequest
        values=payload["parameters"]
        learned_prior=None
        registry=None
        registry_path=values.get("station_registry")
        expected_station=values.get("expected_start_station")
        target_station=values.get("target_station")
        if registry_path and expected_station and target_station:
            registry=json.loads(Path(registry_path).read_text())
            transition=next((item for item in registry.get("transitions",{}).values()
                if item.get("from")==expected_station and item.get("to")==target_station),None)
            if transition is None:
                raise RuntimeError("registered station transition not found: %s -> %s" %
                                   (expected_station,target_station))
            delta=transition["body_relative_translation_m"]
            if float(transition.get("yaw_deg",0.0)) != 0.0:
                raise RuntimeError("manipulation station transition requires zero yaw")
            learned_prior=(float(delta[0]),float(delta[1]))
        request=AlignmentRequest(
            target_profile=values["target_profile"],arm=values.get("arm","right"),
            goal_kind=values["goal_kind"],
            learned_prior_xy_m=learned_prior,
            expected_start_station=expected_station,
            target_station=target_station,
            station_registry_revision=(registry.get("revision") if registry else None),
            bounds=AlignmentBounds(float(values.get("x_bound_m",.15)),
                                   float(values.get("y_bound_m",.40)),0.0,
                                   int(values.get("max_corrections",3))))
        if phase=="prepare":
            request.validate();return {"provider":"navigate.align_for_manipulation",
                                       "request":values,"physical_motion":False}
        if self.bundle.alignment is None:raise RuntimeError("alignment service unavailable")
        return self.bundle.alignment.align(request)
    def _motion(self,phase,payload):
        if phase=="prepare":
            plan=self.bundle.motion.plan(payload)
            if not isinstance(plan,dict) or plan.get("motion_contract") not in (
                    "SCENE_AWARE_FREE_SPACE_V1",None):
                raise RuntimeError("free-space Skill requires SceneAwareMotion/cuRobo plan")
            result=dict(plan);result["free_space_provider"]="SceneAwareMotionService/curobo"
            return result
        return self.bundle.motion.execute_bound(payload)
    def _grasp_symmetry(self,phase,payload):
        if self.bundle.grasp_symmetry is None:
            raise RuntimeError("whole-chain grasp symmetry service unavailable")
        if phase=="prepare":return self.bundle.grasp_symmetry.prepare(payload)
        return self.bundle.grasp_symmetry.bind(payload)
    def _transfer_chain(self,phase,payload):
        if self.bundle.transfer_chain is None:
            raise RuntimeError("atomic transfer-chain planner unavailable")
        if phase=="prepare":return self.bundle.transfer_chain.prepare(payload)
        return self.bundle.transfer_chain.bind(payload)
    def _contact(self,phase,payload):
        if phase=="prepare":return self.bundle.contact.plan(payload)
        return self.bundle.contact.execute_bound(payload)
    def _gripper(self,phase,payload):
        if phase=="prepare":return self.bundle.gripper.prepare(payload)
        return self.bundle.gripper.execute_verified(payload)
    def _authorize(self,phase,payload):
        if phase=="prepare":return self.bundle.authorization.preflight(payload)
        return self.bundle.authorization.authorize(payload)
    def _execute(self,phase,payload):
        if phase=="prepare":return self.bundle.executor.validate(payload)
        return self.bundle.executor.execute(payload)
    def _verify(self,phase,payload):
        if phase=="prepare":return self.bundle.verification.prepare(payload)
        return self.bundle.verification.verify(payload)
    def cancel(self,context):
        # Existing providers retain the authoritative stop semantics.
        for service in (self.bundle.executor,self.bundle.motion,self.bundle.contact,
                        self.bundle.gripper,self.bundle.base):
            stop=getattr(service,"stop",None)
            if stop:stop()
