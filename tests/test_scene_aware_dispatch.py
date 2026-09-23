import unittest
from unittest.mock import patch

from ares_r.scene_aware_dispatch import SceneAwareDispatcher


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


if __name__=="__main__":unittest.main()
