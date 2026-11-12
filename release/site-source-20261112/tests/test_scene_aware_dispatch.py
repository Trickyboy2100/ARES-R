import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

from ares_r.scene_aware_dispatch import (
    RIGHT_CENTER_BODY_M,
    RIGHT_CENTER_YAW_RAD,
    SceneAwareDispatcher,
)


class Scene:
    def status(self): return {"state": "READY"}
    def scan(self, **kwargs): return {"state": "READY", **kwargs}
    def invalidate(self, reason, required=False): return {"state": "REQUIRED", "reason": reason}


class Motion:
    def __init__(self): self.request = None
    def status(self): return {"state": "IDLE"}
    def plan(self, request): self.request=request;return {"plan_id":"P"}
    def preview(self, plan_id=None): return {"plan_id": plan_id or "P"}
    def stop(self): return {"state":"STOPPED"}
    def invalidate_plans(self, reason): return {"reason": reason}


class DispatcherTests(unittest.TestCase):
    def test_center_shortcut_uses_shared_scene_aware_motion(self):
        dispatcher = SceneAwareDispatcher.__new__(SceneAwareDispatcher)
        calls = []
        dispatcher.motion_plan = lambda payload: calls.append(payload) or {"ok": True}
        result = dispatcher.motion_plan_right_center()
        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arm"], "right")
        self.assertEqual(calls[0]["position_m"], list(RIGHT_CENTER_BODY_M))
        self.assertEqual(calls[0]["orientation"], "LEVEL_YAW_TARGET")
        self.assertEqual(calls[0]["yaw_target_rad"], RIGHT_CENTER_YAW_RAD)
        self.assertEqual(calls[0]["scene_policy"], "FORCE_RESCAN")

    def test_art_and_ui_use_same_service_methods(self):
        scene,motion=Scene(),Motion();dispatcher=SceneAwareDispatcher({})
        with patch("ares_r.scene_aware_dispatch.build_services",return_value=(scene,motion)):
            self.assertEqual(dispatcher.dispatch("scene status")["state"],"READY")
            result=dispatcher.motion_plan({"arm":"right","goal_joints_rad":[0]*6,
                "orientation":"FREE","scene_policy":"AUTO_FRESH"})
            self.assertEqual(result["plan_id"],"P")
            self.assertEqual(motion.request.arm,"right")

    def test_art_runtime_xyz_builds_level_yaw_free_goal(self):
        scene,motion=Scene(),Motion();dispatcher=SceneAwareDispatcher({})
        with patch("ares_r.scene_aware_dispatch.build_services",return_value=(scene,motion)):
            dispatcher.dispatch("motion plan right --xyz 0.68 -0.55 1.02")
            self.assertEqual(list(motion.request.goal.position_m),[.68,-.55,1.02])
            self.assertEqual(motion.request.goal.orientation.value,"LEVEL_YAW_FREE")
            self.assertIsNone(motion.request.goal_joints_rad)

    def test_art_target_yaw_is_degrees_at_boundary(self):
        scene,motion=Scene(),Motion();dispatcher=SceneAwareDispatcher({})
        with patch("ares_r.scene_aware_dispatch.build_services",return_value=(scene,motion)):
            dispatcher.dispatch("motion plan right --xyz .7 -.5 1 --orientation LEVEL_YAW_TARGET --yaw 90")
            self.assertAlmostEqual(motion.request.goal.yaw_target_rad,3.141592653589793/2)

    def test_low_code_commands_share_dispatcher_backend(self):
        dispatcher=SceneAwareDispatcher({})
        skills=dispatcher.dispatch("skill list")
        self.assertIn("manipulation.move_free",{x["skill_id"] for x in skills})
        self.assertTrue(dispatcher.dispatch("scheme validate tray_to_groove_v1")["valid"])
        self.assertEqual(dispatcher.dispatch("task show task.tray_to_groove")["scheme_id"],"tray_to_groove_v1")
        with self.assertRaisesRegex(RuntimeError,"locked"):
            dispatcher.dispatch("task run task.tray_to_groove")


    def test_carried_payload_geometry_reaches_the_planner_constraints(self):
        # Regression: _motion_request used to drop attached_object_geometry, so
        # every Web UI / ART plan ran with the held tray invisible to collision
        # checking even though the planner and the independent validator both
        # honour the field.
        from ares_r.manipulation.attached_collision import (
            attach_scene_object, build_attached_collision)
        from ares_r.world import PoseSE3, SceneObject, SceneObjectRole
        target=SceneObject("tray",SceneObjectRole.TARGET,"cuboid",
            PoseSE3("body",(.7,-.3,.9),(1,0,0,0)),(.20,.10,.04),0,"OBS")
        attached=attach_scene_object(target,[[1,0,0,.1],[0,1,0,0],[0,0,1,.2],[0,0,0,1]],
                                     side="right",source_revision="GRASP_OBS")
        geometry=build_attached_collision(attached,[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        scene,motion=Scene(),Motion();dispatcher=SceneAwareDispatcher({})
        with patch("ares_r.scene_aware_dispatch.build_services",return_value=(scene,motion)):
            dispatcher.motion_plan({"arm":"right","position_m":[.6,-.09,1.22],
                "orientation":"LEVEL_YAW_TARGET","yaw_target_rad":.0448,
                "attached_object_geometry":geometry})
        constraints=motion.request.constraints
        self.assertEqual(constraints.attached_object_geometry["object_id"],"tray")
        self.assertEqual(constraints.attached_object_revision,geometry["revision"])
        motion.request.validate()

    def test_tampered_payload_geometry_is_rejected_before_planning(self):
        from ares_r.manipulation.attached_collision import build_attached_collision
        from ares_r.world import AttachedObject, PoseSE3, SceneObject, SceneObjectRole
        geometry=SceneObject("tray",SceneObjectRole.TARGET,"cuboid",
            PoseSE3("body",(.7,-.3,.9),(1,0,0,0)),(.20,.10,.04),0,"OBS")
        attached=AttachedObject("tray","right",PoseSE3("tcp",(.03,0,.08),(1,0,0,0)),
                                geometry,"GRASP_OBS")
        value=build_attached_collision(attached,[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        value["link6_aabb"]["dims_m"][0]+=.05
        scene,motion=Scene(),Motion();dispatcher=SceneAwareDispatcher({})
        with patch("ares_r.scene_aware_dispatch.build_services",return_value=(scene,motion)):
            with self.assertRaisesRegex(ValueError,"revision mismatch"):
                dispatcher.motion_plan({"arm":"right","position_m":[.6,-.09,1.22],
                    "attached_object_geometry":value})


if __name__=="__main__":unittest.main()
