"""Bounded closed-loop AMR alignment for manipulation reachability.

The aligner owns no hardware algorithm.  Detection, IK scoring, AMR motion,
truthful settle observation, atomic observation and cuRobo feasibility are all
dependency-injected canonical services.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import time
from typing import Mapping, Optional, Sequence


@dataclass(frozen=True)
class AlignmentBounds:
    x_m: float = 0.15
    y_m: float = 0.40
    yaw_deg: float = 0.0
    max_corrections: int = 3

    def validate(self):
        if not 0 < self.x_m <= .15 or not 0 < self.y_m <= .40:
            raise ValueError("P3.9B alignment bounds exceed +/-0.15 X / +/-0.40 Y")
        if self.yaw_deg != 0:
            raise ValueError("P3.9B alignment yaw must be zero")
        if not 1 <= self.max_corrections <= 4:
            raise ValueError("alignment corrections must be 1..4")


@dataclass(frozen=True)
class AlignmentRequest:
    target_profile: str
    goal_kind: str
    arm: str = "right"
    bounds: AlignmentBounds = field(default_factory=AlignmentBounds)
    learned_prior_xy_m: Optional[Sequence[float]] = None
    expected_start_station: Optional[str] = None
    target_station: Optional[str] = None
    station_registry_revision: Optional[str] = None
    preferred_target_body_m: Sequence[float] = (0.70, -0.25, 1.0)

    def validate(self):
        self.bounds.validate()
        if self.arm != "right":
            raise ValueError("P3.9B first slice commissions right arm only")
        if self.goal_kind not in ("PICK_PREGRASP", "PLACE_PREPLACE"):
            raise ValueError("unknown manipulation goal kind")
        if not self.target_profile:
            raise ValueError("target profile is required")
        if bool(self.expected_start_station) != bool(self.target_station):
            raise ValueError("registered alignment requires both start and target station")


def _atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _target_xyz(detection):
    if "target_body_m" in detection:
        value = detection["target_body_m"]
    elif "pose_body_m_rad" in detection:
        value = detection["pose_body_m_rad"][:3]
    elif "position_m" in detection:
        value = detection["position_m"]
    else:
        raise ValueError("5700 detection lacks BODY target coordinates")
    xyz = tuple(float(v) for v in value)
    if len(xyz) != 3 or not all(math.isfinite(v) for v in xyz):
        raise ValueError("finite BODY target xyz required")
    return xyz


class ManipulationAlignmentService:
    revision = "NAVIGATE_ALIGN_FOR_MANIPULATION_P39B_V1"

    def __init__(self, *, detect, score_ik, base, observer, observation_v2,
                 plan_feasibility, invalidate_scene=None,
                 prior_path="worklog/runtime/p39b/alignment_priors.json",
                 evidence_root="worklog/evidence/2026-09-29-p3-9b/alignment",
                 clock=time.time):
        self.detect=detect; self.score_ik=score_ik; self.base=base
        self.observer=observer; self.observation_v2=observation_v2
        self.plan_feasibility=plan_feasibility; self.invalidate_scene=invalidate_scene
        self.prior_path=Path(prior_path); self.evidence_root=Path(evidence_root)
        self.clock=clock

    @staticmethod
    def _predict(target_xyz, cumulative_xy):
        return [target_xyz[0]-cumulative_xy[0],
                target_xyz[1]-cumulative_xy[1], target_xyz[2]]

    def _candidates(self, request, target_xyz, cumulative):
        preferred = request.preferred_target_body_m
        desired = (target_xyz[0]-float(preferred[0]),
                   target_xyz[1]-float(preferred[1]))
        seeds = [desired, (desired[0], cumulative[1]), (cumulative[0], desired[1]),
                 tuple(cumulative), (0.0, 0.0)]
        if request.learned_prior_xy_m is not None:
            seeds.insert(0, tuple(float(v) for v in request.learned_prior_xy_m))
        # Small deterministic corrections around the best geometry prediction;
        # total offsets are always from the episode origin, never incremental bounds.
        for dx,dy in ((.04,0),(-.04,0),(0,.06),(0,-.06)):
            seeds.append((desired[0]+dx, desired[1]+dy))
        unique=[]
        for x,y in seeds:
            row=(max(-request.bounds.x_m,min(request.bounds.x_m,float(x))),
                 max(-request.bounds.y_m,min(request.bounds.y_m,float(y))))
            if row not in unique: unique.append(row)
        scored=[]
        for x,y in unique:
            predicted=self._predict(target_xyz,(x,y))
            score=dict(self.score_ik(predicted,request.goal_kind) or {})
            feasible=bool(score.get("feasible",False))
            joint_margin=float(score.get("joint_margin",0.0))
            singularity=float(score.get("singularity_penalty",1e6))
            displacement=math.hypot(x,y)
            target_error=math.hypot(predicted[0]-float(preferred[0]),
                                    predicted[1]-float(preferred[1]))
            score_value=((1000.0 if feasible else 0.0)+100.0*joint_margin-
                         10.0*singularity-100.0*target_error-displacement)
            scored.append({"total_offset_xy_m":[x,y],"predicted_target_body_m":predicted,
                           "ik":score,"target_xy_error_m":target_error,"score":score_value})
        return sorted(scored,key=lambda row:(-row["score"],math.hypot(*row["total_offset_xy_m"])))

    def align(self, request: AlignmentRequest):
        request.validate(); started=self.clock(); detection=self.detect(request.target_profile)
        initial_xyz=_target_xyz(detection); cumulative=[0.0,0.0]; corrections=[]
        rejected=set()
        episode_id="ALIGN_%d"%int(started*1000)
        evidence=self.evidence_root/episode_id
        for attempt in range(request.bounds.max_corrections):
            candidates=self._candidates(request,initial_xyz,cumulative)
            candidate=next((row for row in candidates if row["ik"].get("feasible") and
                            tuple(row["total_offset_xy_m"]) not in rejected),None)
            if candidate is None:
                result={"result":"FAILED","failure_code":"NO_BOUNDED_IK_CANDIDATE",
                        "episode_id":episode_id,"candidates":candidates}
                _atomic_json(evidence/"alignment.json",result); return result
            target_total=candidate["total_offset_xy_m"]
            delta=[target_total[0]-cumulative[0],target_total[1]-cumulative[1]]
            baseline=self.observer.capture()
            if math.hypot(*delta) > .001:
                if self.invalidate_scene:self.invalidate_scene("BASE_ALIGNMENT_MOVING")
                command=self.base.move_relative(delta[0],delta[1],0.0)
                settle=self.observer.wait(baseline,expected_translation_m=math.hypot(*delta),
                                          expected_yaw_deg=0.0)
            else:
                command={"accepted":False,"reason":"ALREADY_AT_CANDIDATE"}
                settle={"result":"SETTLED","method":"zero correction; live baseline captured"}
            cumulative=list(target_total)
            epoch=self.observation_v2.capture(request.target_profile)
            fresh_xyz=_target_xyz(epoch)
            feasibility=dict(self.plan_feasibility(epoch,request.goal_kind) or {})
            row={"attempt":attempt+1,"commanded_delta_xy_m":delta,
                 "cumulative_xy_m":list(cumulative),"command_response":command,
                 "settle":settle,"target_body_before_m":initial_xyz,
                 "target_body_after_m":fresh_xyz,"observation_epoch":epoch,
                 "curobo_feasibility":feasibility}
            corrections.append(row)
            if feasibility.get("success") is True:
                result={"result":"ALIGNED","revision":self.revision,
                        "episode_id":episode_id,"target_profile":request.target_profile,
                        "goal_kind":request.goal_kind,"bounds":asdict(request.bounds),
                        "expected_start_station":request.expected_start_station,
                        "target_station":request.target_station,
                        "station_registry_revision":request.station_registry_revision,
                        "total_offset_xy_m":list(cumulative),"corrections":corrections,
                        "target_body_final_m":fresh_xyz,"fresh_epoch":epoch,
                        "curobo_feasibility":feasibility,"elapsed_s":self.clock()-started}
                _atomic_json(evidence/"alignment.json",result)
                priors={}
                if self.prior_path.exists():priors=json.loads(self.prior_path.read_text())
                priors[request.target_profile]={"offset_xy_m":list(cumulative),
                    "evidence":str(evidence/"alignment.json"),"revision":self.revision,
                    "recorded_at_unix":self.clock()}
                _atomic_json(self.prior_path,priors)
                return result
            rejected.add(tuple(cumulative))
            initial_xyz=fresh_xyz
        result={"result":"FAILED","failure_code":"BOUNDED_CORRECTIONS_EXHAUSTED",
                "episode_id":episode_id,"total_offset_xy_m":cumulative,
                "corrections":corrections,"bounds":asdict(request.bounds)}
        _atomic_json(evidence/"alignment.json",result);return result
