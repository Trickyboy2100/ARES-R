"""Shared command dispatcher for ART and the scene-aware Web UI."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from .motion.ab_client import ABDemoClient
from .motion.local_scene_service import ScenePolicy
from .motion.scene_aware_motion import (MotionConstraints, MotionGoal, MotionRequest,
                                        OrientationMode, build_services)


def _motion_request(payload):
    arbitrary = "position_m" in payload or "goal" in payload
    orientation = OrientationMode(payload.get(
        "orientation", "LEVEL_YAW_FREE" if arbitrary else "FREE"))
    constraints = MotionConstraints(
        orientation=orientation,
        explicit_rotation=payload.get("explicit_rotation"),
        central_exclusion=payload.get("central_exclusion", True),
        keepout_ids=tuple(payload.get("keepout_ids", ())),
        attached_object_revision=payload.get("attached_object_revision"))
    goal_payload = payload.get("goal")
    if goal_payload is None and "position_m" in payload:
        goal_payload = {
            "position_m": payload["position_m"], "orientation": orientation.value,
            "yaw_target_rad": payload.get("yaw_target_rad"),
            "explicit_rotation": payload.get("explicit_rotation"),
            "source": payload.get("source", "runtime"),
        }
    goal = (None if goal_payload is None else MotionGoal(
        position_m=goal_payload["position_m"],
        frame=goal_payload.get("frame", "BODY"),
        orientation=OrientationMode(goal_payload.get("orientation", orientation.value)),
        yaw_target_rad=goal_payload.get("yaw_target_rad"),
        explicit_rotation=goal_payload.get("explicit_rotation"),
        position_tolerance_m=float(goal_payload.get("position_tolerance_m", .003)),
        orientation_tolerance_deg=float(goal_payload.get("orientation_tolerance_deg", 3.0)),
        source=goal_payload.get("source", payload.get("source", "runtime"))))
    return MotionRequest(
        arm=payload["arm"], goal_joints_rad=payload.get("goal_joints_rad"), goal=goal,
        goal_pose_body_m_rad=payload.get("goal_pose_body_m_rad"),
        constraints=constraints,
        speed_profile=payload.get("speed_profile", "slow"),
        scene_policy=ScenePolicy(payload.get("scene_policy", "AUTO_FRESH")),
        request_label=payload.get("request_label", "free_space_motion"))


class SceneAwareDispatcher:
    def __init__(self, config):
        self.config = config

    def services(self):
        return build_services(self.config)

    def scene_status(self):
        scene, _ = self.services();return scene.status()

    def scene_scan(self, force=True, active_arm="right"):
        scene, _ = self.services();return scene.scan(force=force, active_arm=active_arm)

    def scene_invalidate(self, reason="OPERATOR_INVALIDATION"):
        scene, motion = self.services()
        motion.invalidate_plans("SCENE_INVALIDATED:" + reason)
        return scene.invalidate(reason, required=True)

    def motion_status(self):
        _, motion = self.services();return motion.status()

    def motion_plan(self, payload):
        _, motion = self.services();return motion.plan(_motion_request(payload))

    def motion_preview(self, plan_id=None):
        _, motion = self.services();return motion.preview(plan_id)

    def motion_stop(self):
        scene, motion = self.services()
        result = motion.stop();scene.invalidate("MOTION_STOP", required=True)
        return result

    def ab_plan_next(self, destination):
        _, motion = self.services();return ABDemoClient(motion).plan(destination)

    def dispatch(self, text):
        args = shlex.split(text)
        if args == ["scene", "status"]: return self.scene_status()
        if args == ["scene", "scan"]: return self.scene_scan(True)
        if args[:2] == ["scene", "invalidate"]:
            return self.scene_invalidate(" ".join(args[2:]) or "ART_INVALIDATION")
        if args == ["motion", "status"]: return self.motion_status()
        if args[:2] == ["motion", "preview"]:
            return self.motion_preview(args[2] if len(args) == 3 else None)
        if args == ["motion", "stop"]: return self.motion_stop()
        if args[:2] == ["motion", "plan"] and "--xyz" in args:
            if len(args) < 7:
                raise ValueError("usage: motion plan SIDE --xyz X Y Z [--orientation MODE] [--yaw DEG]")
            side = args[2];xyz_at = args.index("--xyz")
            xyz = [float(value) for value in args[xyz_at + 1:xyz_at + 4]]
            mode = "LEVEL_YAW_FREE"
            if "--orientation" in args:
                mode = args[args.index("--orientation") + 1]
            payload = {"arm": side, "position_m": xyz, "orientation": mode,
                       "scene_policy": "AUTO_FRESH",
                       "speed_profile": "right_scene_aware_0_20",
                       "source": "ART_RUNTIME_XYZ", "request_label": "ART_RUNTIME_TARGET"}
            if "--yaw" in args:
                payload["yaw_target_rad"] = float(args[args.index("--yaw") + 1]) * 3.141592653589793 / 180.0
            return self.motion_plan(payload)
        if len(args) == 4 and args[:3] == ["demo", "ab", "plan-next"]:
            return self.ab_plan_next(args[3].upper())
        raise ValueError("unsupported scene-aware command")
