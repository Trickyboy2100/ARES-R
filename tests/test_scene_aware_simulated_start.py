import unittest

from ares_r.motion.scene_aware_motion import MotionRequest


class SimulatedStartTests(unittest.TestCase):
    def test_simulated_start_requires_truthful_state_label(self):
        with self.assertRaisesRegex(ValueError,"explicit simulated rehearsal"):
            MotionRequest("right",goal_joints_rad=[0]*6,start_joints_rad=[0]*6).validate()

    def test_simulated_start_is_valid_for_scheme_rehearsal(self):
        MotionRequest("right",goal_joints_rad=[0]*6,start_joints_rad=[0]*6,
                      physical_state="SIMULATED_FOR_SCHEME_REHEARSAL").validate()


if __name__ == "__main__": unittest.main()
