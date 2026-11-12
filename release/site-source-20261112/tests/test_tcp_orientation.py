import math
import unittest

import numpy as np

from ares_r.motion.tcp_orientation import (HORIZONTAL_FORWARD_R_BODY,
    level_rotation,nearest_level_roll_branch,validate_path)


class TcpOrientationTests(unittest.TestCase):
    def test_horizontal_forward_passes(self):
        def fk(_):
            value = np.eye(4)
            value[:3, :3] = HORIZONTAL_FORWARD_R_BODY
            return value
        result = validate_path(fk, np.zeros((3, 6)))
        self.assertTrue(result["passed"])
        self.assertEqual(result["dense_samples"], 9)

    def test_dip_between_endpoints_fails(self):
        def fk(q):
            value = np.eye(4)
            tilt = .2 * math.sin(math.pi * float(q[0]))
            c, s = math.cos(tilt), math.sin(tilt)
            value[:3, :3] = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]) @ HORIZONTAL_FORWARD_R_BODY
            return value
        rows = np.zeros((2, 6))
        rows[1, 0] = 1.0
        result = validate_path(fk, rows, subdivisions=8)
        self.assertFalse(result["passed"])
        self.assertGreater(result["max_forward_tilt_deg"], 10)

    def test_old_downward_pose_fails(self):
        old = np.array([[-.510742795, .337120202, .790880374],
                        [.584681584, .810629809, .032043053],
                        [-.630308846, .478778948, -.611131308]])
        def fk(_):
            value = np.eye(4)
            value[:3, :3] = old
            return value
        self.assertFalse(validate_path(fk, np.zeros((2, 6)))["passed"])

    def test_level_roll_symmetry_preserves_approach_axis(self):
        normal=level_rotation(.7,0);flipped=level_rotation(.7,1)
        np.testing.assert_allclose(normal[:,2],flipped[:,2])
        np.testing.assert_allclose(normal[:,:2],-flipped[:,:2])
        self.assertEqual(nearest_level_roll_branch(normal),0)
        self.assertEqual(nearest_level_roll_branch(flipped),1)


if __name__ == "__main__":
    unittest.main()
