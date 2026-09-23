"""A/B convenience client; all scene/planner/execution ownership is below it."""

from __future__ import annotations

import json
from pathlib import Path

from .scene_aware_motion import (MotionConstraints, MotionRequest,
                                 OrientationMode, ScenePolicy)


ROOT = Path(__file__).resolve().parents[3]


class ABDemoClient:
    def __init__(self, motion_service, contract_path=None):
        self.motion_service = motion_service
        self.contract = json.loads(Path(contract_path or
            ROOT / "config/ab_demo_horizontal_forward.json").read_text())["candidates"][0]

    def request_for(self, destination: str, *, force_rescan=True):
        if destination not in ("A", "B"):
            raise ValueError("A/B destination required")
        return MotionRequest(
            arm="right",
            goal_joints_rad=self.contract[destination + "_joints_rad"],
            goal_pose_body_m_rad=self.contract[destination + "_xyz_m"],
            constraints=MotionConstraints(
                orientation=OrientationMode.BODY_FORWARD_HORIZONTAL),
            speed_profile="right_ab_demo_0_20",
            scene_policy=(ScenePolicy.FORCE_RESCAN if force_rescan
                          else ScenePolicy.AUTO_FRESH),
            request_label="AB_DEMO_TO_" + destination,
        )

    def plan(self, destination: str):
        return self.motion_service.plan(self.request_for(destination))

    def next_destination(self, actual_joints_rad, tolerance_rad=0.02):
        def close(name):
            return max(abs(float(a)-float(b)) for a,b in zip(
                actual_joints_rad,self.contract[name+"_joints_rad"]))<=tolerance_rad
        if close("A"):return "B"
        if close("B"):return "A"
        return "A"

