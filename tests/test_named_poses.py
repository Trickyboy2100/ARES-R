import unittest
from ares_r.named_poses import load_named_poses,pose_report

class NamedPoseTest(unittest.TestCase):
 def test_repository_library(self):
  data=load_named_poses("config/named_poses.json")
  self.assertEqual(set(data["poses"]),{"zero","ready","forward","up","side"})
  self.assertIn("EXECUTION BLOCKED",pose_report(data,"ready","right"))
 def test_list(self): self.assertIn("zero",pose_report(load_named_poses("config/named_poses.json")))
