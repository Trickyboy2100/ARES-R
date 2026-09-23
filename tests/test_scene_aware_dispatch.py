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


if __name__=="__main__":unittest.main()
