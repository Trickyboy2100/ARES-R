"""Shared command dispatcher for ART and the scene-aware Web UI."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from .motion.ab_client import ABDemoClient
from .motion.local_scene_service import ScenePolicy
from .motion.scene_aware_motion import (MotionConstraints, MotionGoal, MotionRequest,
                                        OrientationMode, build_services)
from .demos import DemoRegistry
from .task_studio import TaskStudio
from .runtime_identity import runtime_identity


def _motion_request(payload, default_central_exclusion=True):
    arbitrary = "position_m" in payload or "goal" in payload
    orientation = OrientationMode(payload.get(
        "orientation", "LEVEL_YAW_FREE" if arbitrary else "FREE"))
    constraints = MotionConstraints(
        orientation=orientation,
        explicit_rotation=payload.get("explicit_rotation"),
        central_exclusion=payload.get("central_exclusion", default_central_exclusion),
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
        self._studio = TaskStudio(Path.cwd())

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
        _, motion = self.services()
        profile_path=Path(__file__).resolve().parents[2]/"config/scene_aware_motion.json"
        policy=(json.loads(profile_path.read_text()).get("central_exclusion") or {})
        return motion.plan(_motion_request(payload, bool(policy.get("enabled", True))))

    def motion_preview(self, plan_id=None):
        _, motion = self.services();return motion.preview(plan_id)

    def motion_stop(self):
        scene, motion = self.services()
        result = motion.stop();scene.invalidate("MOTION_STOP", required=True)
        return result

    def ab_plan_next(self, destination):
        _, motion = self.services();return ABDemoClient(motion).plan(destination)

    def demo_list(self): return DemoRegistry().list()

    def demo_status(self): return DemoRegistry().status()

    def demo_inspect(self, demo_id=None): return DemoRegistry().selected(demo_id)

    def demo_select(self, demo_id): return DemoRegistry().select(demo_id)

    def demo_prepare(self, demo_id=None): return DemoRegistry().prepare(demo_id)

    def demo_stop(self): return DemoRegistry().stop()

    def studio(self): return self._studio

    def skill_list(self): return self.studio().skill_list()
    def skill_show(self, skill_id): return self.studio().skill_show(skill_id)
    def scheme_list(self): return self.studio().scheme_list()
    def scheme_show(self, scheme_id): return self.studio().scheme_show(scheme_id)
    def scheme_clone(self, source, new_id): return self.studio().scheme_clone(source, new_id)
    def scheme_validate(self, scheme): return self.studio().scheme_validate(scheme)
    def scheme_preview(self, scheme): return self.studio().scheme_preview(scheme)
    def scheme_save(self, scheme): return self.studio().scheme_save_draft(scheme)
    def task_list(self): return self.studio().task_list()
    def task_show(self, task_id): return self.studio().task_show(task_id)
    def task_prepare(self, task_id): return self.studio().prepare(task_id)
    def task_replay(self, task_id): return self.studio().start_replay(task_id)
    def task_status(self): return self.studio().status()
    def task_stop(self): return self.studio().stop()

    def system_info(self):
        task=self.task_status()
        return runtime_identity(Path.cwd(),active_scheme=task.get("scheme_id"))

    def dispatch(self, text):
        args = shlex.split(text)
        if args in (["version"],["system","info"]): return self.system_info()
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
        if args == ["demo", "list"]: return self.demo_list()
        if args == ["demo", "status"]: return self.demo_status()
        if args[:2] == ["demo", "show"] and len(args) in (2, 3):
            return self.demo_inspect(args[2] if len(args) == 3 else None)
        if args[:2] == ["demo", "select"] and len(args) == 3:
            return self.demo_select(args[2])
        if args[:2] == ["demo", "prepare"] and len(args) in (2, 3):
            return self.demo_prepare(args[2] if len(args) == 3 else None)
        if args == ["demo", "stop"]: return self.demo_stop()
        if args == ["skill", "list"]: return self.skill_list()
        if args[:2] == ["skill", "show"] and len(args) == 3: return self.skill_show(args[2])
        if args == ["scheme", "list"]: return self.scheme_list()
        if args[:2] == ["scheme", "show"] and len(args) == 3: return self.scheme_show(args[2])
        if args[:2] == ["scheme", "clone"] and len(args) == 4: return self.scheme_clone(args[2],args[3])
        if args[:2] == ["scheme", "validate"] and len(args) == 3: return self.scheme_validate(args[2])
        if args[:2] == ["scheme", "preview"] and len(args) == 3: return self.scheme_preview(args[2])
        if args[:2] == ["scheme", "save-draft"] and len(args) == 3:
            return self.scheme_save(self.scheme_show(args[2]))
        if args == ["task", "list"]: return self.task_list()
        if args[:2] == ["task", "show"] and len(args) == 3: return self.task_show(args[2])
        if args[:2] == ["task", "prepare"] and len(args) == 3: return self.task_prepare(args[2])
        if args[:2] == ["task", "preview"] and len(args) == 3:
            return self.scheme_preview(self.task_show(args[2])["scheme_id"])
        if args[:2] == ["task", "replay"] and len(args) == 3: return self.task_replay(args[2])
        if args[:2] == ["task", "status"]: return self.task_status()
        if args[:2] == ["task", "stop"]: return self.task_stop()
        if args[:2] == ["task", "run"]: raise RuntimeError("physical task run locked in P3.9")
        raise ValueError("unsupported scene-aware command")


def shared_dispatcher(config):
    """Return the canonical backend client when deployed, local owner in tests."""
    import os
    url=os.environ.get("ARES_R_BACKEND_URL")
    if url:
        from .canonical_backend import CanonicalBackendClient
        return CanonicalBackendClient(url)
    return SceneAwareDispatcher(config)
