import unittest

from ares_r.motion.ab_demo_state import (ABPlanningSession, ABState,
                                         classify_reference_corridor, validate_curobo_only_policy)


class ABPlanningSessionTests(unittest.TestCase):
    def test_latest_override_forbids_waypoints(self):
        policy = {"motion_policy": "CUROBO_ONLY_FOR_EVERY_POINT_TO_POINT_LEG",
                  "planner_mode": "CUROBO_DIRECT", "explicit_waypoints": []}
        validate_curobo_only_policy(policy)
        with self.assertRaises(ValueError):
            validate_curobo_only_policy(dict(policy, waypoint_joints_rad=[0]*6))
        with self.assertRaises(ValueError):
            validate_curobo_only_policy(dict(policy, planner_mode="CUROBO_OVERHEAD"))
    def test_swept_corridor_contract(self):
        self.assertEqual(classify_reference_corridor({"box": .05}, .04),
                         ("STRAIGHT_CLEAR", []))
        self.assertEqual(classify_reference_corridor({"box": -.01}, .04),
                         ("STRAIGHT_BLOCKED", ["box"]))
        self.assertEqual(classify_reference_corridor({"box": .05}, -.01),
                         ("SCENE_INVALID", []))
    def test_fresh_scan_and_scene_binding_and_hard_execution_lock(self):
        session = ABPlanningSession()
        session.at_endpoint("A")
        session.begin_scan()
        session.scene_ready("SCENE_FRESH")
        session.classified("STRAIGHT_BLOCKED")
        session.planned("TRAJ_ONE", "SCENE_FRESH")
        session.preview()
        with self.assertRaises(PermissionError):
            session.execute_next()
        self.assertEqual(session.state, ABState.AWAITING_CONFIRMATION)
        session.stop()
        self.assertIsNone(session.scene_snapshot_id)
        self.assertIsNone(session.trajectory_id)
        with self.assertRaises(ValueError):
            session.planned("TRAJ_OLD", "SCENE_FRESH")

    def test_each_new_leg_requires_fresh_scene(self):
        session = ABPlanningSession()
        session.at_endpoint("B")
        with self.assertRaises(ValueError):
            session.planned("TRAJ", "SCENE_OLD")
        session.begin_scan()
        session.scene_ready("SCENE_NEW")
        session.classified("STRAIGHT_CLEAR")
        with self.assertRaises(ValueError):
            session.planned("TRAJ", "SCENE_OLD")
        session.planned("TRAJ", "SCENE_NEW")
        session.fault()
        self.assertEqual(session.state, ABState.FAULT)
        self.assertIsNone(session.trajectory_id)


if __name__ == "__main__":
    unittest.main()
