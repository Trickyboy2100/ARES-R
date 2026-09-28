"""Real vertical-slice provider that delegates to canonical ARES-R services.

The bundle is deliberately dependency-injected: this layer never reimplements
scene reconstruction, cuRobo, ServoJ, gripper, AMR or contact algorithms.
"""

from dataclasses import dataclass
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


class RealCapabilityProvider(CanonicalCapabilityProvider):
    revision="real-existing-services-p39-v1"
    def __init__(self,bundle):
        self.bundle=bundle;self._observation={};self._guard=threading.Lock()
        super().__init__({
            "scene.capture":self._observation_call,
            "resource.detect":self._observation_call,
            "predicate.verify":self._verify,
            "base.navigate":self._base,
            "motion.free":self._motion,
            "motion.lift":self._motion,
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
    def _motion(self,phase,payload):
        if phase=="prepare":return self.bundle.motion.plan(payload)
        return self.bundle.motion.execute_bound(payload)
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
