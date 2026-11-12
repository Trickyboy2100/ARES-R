import math
import unittest

import numpy as np

from ares_r.motion.tcp_orientation import level_rotation, validate_level_path


class LevelYawConstraintTests(unittest.TestCase):
    def test_yaw_may_change_while_level_is_preserved(self):
        def fk(q):
            value=np.eye(4);value[:3,:3]=level_rotation(float(q[0]));return value
        result=validate_level_path(fk,[[0]*6,[math.pi/2,0,0,0,0,0]],subdivisions=8)
        self.assertTrue(result["passed"])
        self.assertGreater(result["yaw_range_deg"],80)
        self.assertLess(result["max_level_error_deg"],1e-8)

    def test_vertical_tilt_is_rejected(self):
        def fk(_q):
            value=np.eye(4);value[:3,:3]=level_rotation(0)
            angle=math.radians(5);rotation=np.array([[1,0,0],[0,math.cos(angle),-math.sin(angle)],[0,math.sin(angle),math.cos(angle)]])
            value[:3,:3]=rotation@value[:3,:3];return value
        result=validate_level_path(fk,[[0]*6,[0]*6],tolerance_deg=3)
        self.assertFalse(result["passed"])


if __name__=="__main__":unittest.main()
