"""Versioned, manipulation-only collision policy for bounded contact escapes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from ares_r.manipulation.contact_motion import _geometry_overlap,_collision_box
import numpy as np


_STAGES = {"PICK_CONTACT_ESCAPE", "PICK_APPROACH", "PICK_INITIAL_LIFT",
           "PLACE_DESCENT", "PLACE_RETREAT"}


def _digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ContactBypassPolicy:
    policy_id: str
    revision: str
    stage: str
    observation_id: str
    active_arm: str = "right"
    active_tool_world_collision: bool = False
    arm_link_world_collision: bool = True
    inactive_arm_collision: bool = True
    self_collision: bool = True
    central_exclusion: bool = True
    bounded_cartesian_only: bool = True
    automatic_expiry: bool = True
    maximum_segment_m: float = .101

    @classmethod
    def for_manipulation_skill(cls, stage, observation_id, *, central_exclusion=True):
        if stage not in _STAGES or not observation_id:
            raise ValueError("reviewed manipulation stage and observation are required")
        core={"policy_id":"CONTACT_BYPASS_V1","stage":stage,
              "observation_id":str(observation_id),"active_arm":"right",
              "active_tool_world_collision":False,"arm_link_world_collision":True,
              "inactive_arm_collision":True,"self_collision":True,
              "central_exclusion":bool(central_exclusion),"bounded_cartesian_only":True,
              "automatic_expiry":True,"maximum_segment_m":.101}
        return cls(revision=_digest(core),**core)

    def as_dict(self):return asdict(self)


class HardWorldBroadPhase:
    """Conservative BODY AABBs; every overlapping pair still uses full OBB SAT."""
    def __init__(self,world):
        self.items=list(world.items());self.centers=[];self.extents=[]
        for name,item in self.items:
            center,extent=self.bounds(item);self.centers.append(center);self.extents.append(extent)
        self.centers=np.asarray(self.centers).reshape(-1,3);self.extents=np.asarray(self.extents).reshape(-1,3)
    @staticmethod
    def bounds(item):
        box=_collision_box(item,item.get('geometry_id','world'))
        center=np.asarray(box.center_body_m);extent=np.abs(np.asarray(box.rotation_body))@np.asarray(box.half_extents_m)
        if not np.isfinite(center).all() or not np.isfinite(extent).all():raise ValueError('nonfinite hard-world geometry')
        return center,extent+1e-6+np.sum(extent)*1e-7
    def candidates(self,link):
        center,extent=self.bounds(link)
        indices=np.flatnonzero(np.all(np.abs(self.centers-center)<=self.extents+extent,axis=1))
        return [self.items[i] for i in indices]


def validate_bypass_segment(samples: Sequence[Mapping[str, object]],
                            world_obstacles: Mapping[str, Mapping[str, object]],
                            policy: ContactBypassPolicy, *,
                            expected_direction_body, joint_lower, joint_upper,
                            expire_at_end=True,check_cancelled=lambda:None):
    """Hard-check everything except active tool/gripper vs observed world."""
    if not isinstance(policy,ContactBypassPolicy) or policy.policy_id!="CONTACT_BYPASS_V1":
        raise RuntimeError("CONTACT_BYPASS_V1 manipulation policy required")
    if len(samples)<2:raise ValueError("dense bypass samples required")
    direction=[float(v) for v in expected_direction_body]
    norm=math.sqrt(sum(v*v for v in direction));direction=[v/norm for v in direction]
    start=[float(v) for v in samples[0]["tcp_position_body_m"]];prior=-1e-9
    min_central=float("inf");broadphase=HardWorldBroadPhase(world_obstacles);exact_pairs=0
    for index,sample in enumerate(samples):
        check_cancelled()
        q=[float(v) for v in sample["joints_rad"]]
        if len(q)!=6 or any(q[i]<float(joint_lower[i]) or q[i]>float(joint_upper[i]) for i in range(6)):
            raise RuntimeError("bypass joint limit violation")
        tcp=[float(v) for v in sample["tcp_position_body_m"]]
        delta=[tcp[i]-start[i] for i in range(3)];progress=sum(delta[i]*direction[i] for i in range(3))
        lateral=math.sqrt(sum((delta[i]-progress*direction[i])**2 for i in range(3)))
        if progress+1e-8<prior or progress>policy.maximum_segment_m+.003 or lateral>.002:
            raise RuntimeError("bypass must be a bounded monotonic Cartesian segment")
        prior=progress
        if policy.central_exclusion:
            min_central=min(min_central,-tcp[1]-.070)
            if min_central<=0:raise RuntimeError("bypass touches BODY central exclusion")
        links=list(sample["arm_links"])
        if len(links)<6:raise RuntimeError("Link1..Link6 geometry is required")
        for link in links:
            for obstacle_id,obstacle in broadphase.candidates(link):
                exact_pairs+=1
                if _geometry_overlap(link,obstacle):
                    raise RuntimeError("arm link contacted hard world object %s"%obstacle_id)
        # Adjacent conservative link boxes may overlap by construction.  All
        # non-adjacent pairs remain a hard independent self-collision check.
        for a in range(len(links)):
            for b in range(a+2,len(links)):
                if _geometry_overlap(links[a],links[b]):
                    raise RuntimeError("non-adjacent arm self collision")
    if prior<.025 or prior>policy.maximum_segment_m+.003:
        raise RuntimeError("bypass segment length is outside reviewed contact/escape bounds")
    return {"valid":True,"policy_id":policy.policy_id,"policy_revision":policy.revision,
            "stage":policy.stage,"samples":len(samples),"segment_length_m":prior,
            "minimum_central_margin_m":min_central,
            "ignored_collision_pair":"ACTIVE_RIGHT_GRIPPER_TOOL_VS_OBSERVED_POINTCLOUD_ONLY",
            "arm_links_world_hard":True,"inactive_left_arm_hard":True,
            "self_collision_hard":True,"automatic_expiry":True,
            "expired_at_end":bool(expire_at_end),"world_obstacles_retained":len(world_obstacles),
            "exact_obb_world_pairs":exact_pairs,"broadphase":"CONSERVATIVE_BODY_AABB_V1"}
