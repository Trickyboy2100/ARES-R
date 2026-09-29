import unittest
from ares_r.named_poses import load_named_poses,pose_report

class NamedPoseTest(unittest.TestCase):
 def test_repository_library(self):
  data=load_named_poses("config/named_poses.json")
  self.assertEqual(set(data["poses"]),{"zero","ready","forward","up","side","folded","center"})
  self.assertNotIn("EXECUTION BLOCKED",pose_report(data,"ready","right"))
  self.assertNotIn("EXECUTION BLOCKED",pose_report(data,"folded","right"))
  self.assertNotIn("EXECUTION BLOCKED",pose_report(data,"center","right"))
  self.assertTrue(all(p["commissioning"]=="commissioned" for p in data["poses"].values()))
 def test_center_route_does_not_unlock_an_uncommissioned_planner(self):
  # `center` was commissioned through production_scene_worker -> supervised_path.
  # `pose go ... curobo` dispatches to obstacle_demo.run_named_right and
  # `pose go ... direct` to a controller MoveJ; neither was exercised for this pose,
  # so the recorded route must not match either token or `pose go` would silently
  # run an uncommissioned planner.
  data=load_named_poses("config/named_poses.json")
  route=data["poses"]["center"]["commissioned_routes"]["right"]
  self.assertNotIn("curobo_plan_cspace_to_supervised_servoj",route)
  self.assertNotIn("direct_movej",route)
 def test_list(self): self.assertIn("zero",pose_report(load_named_poses("config/named_poses.json")))
