import unittest
from ares_r.manipulation.task_parameters import load_task_parameters,gripper_percent_to_raw


class TaskParameterTests(unittest.TestCase):
    def test_versioned_demo_parameters(self):
        value=load_task_parameters()
        self.assertEqual(value["demo_scope"]["inactive_arm_policy"],"HOLD_CURRENT")
        self.assertEqual([gripper_percent_to_raw(p,value) for p in (50,40,20)],
                         [500,400,200])
        self.assertEqual(value["base_contracts"]["PLACE_BASE_POSE_V1"]["y_m"],-.40)


if __name__ == "__main__": unittest.main()
