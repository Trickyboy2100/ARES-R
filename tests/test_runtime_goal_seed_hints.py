import unittest
from ares_r.motion.scene_aware_motion import MotionGoal
from ares_r.scene_aware_dispatch import _motion_request

class SeedHintTests(unittest.TestCase):
    def test_explicit_seed_is_hint_not_replacement_start_or_goal(self):
        seed=[[.1]*6]
        request=_motion_request({'arm':'right','position_m':[.3,-.08,1.03],'ik_seed_joints_rad':seed})
        request.validate()
        self.assertEqual(request.goal.ik_seed_joints_rad,seed)
        self.assertIsNone(request.start_joints_rad)
        self.assertEqual(request.goal.position_m,[.3,-.08,1.03])
    def test_bounded_finite_seed_budget(self):
        for seeds in ([[0]*6]*5,[[float('nan')]*6],[[0]*5]):
            with self.assertRaises(ValueError):MotionGoal([.3,-.08,1.03],ik_seed_joints_rad=seeds).validate()
