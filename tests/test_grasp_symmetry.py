import unittest
import numpy as np

from ares_r.manipulation.grasp_symmetry import two_finger_grasp_rotations


class GraspSymmetryTest(unittest.TestCase):
    def test_preserves_approach_and_flips_finger_axes(self):
        rows = two_finger_grasp_rotations(np.eye(3))
        self.assertEqual([row[0] for row in rows],
                         ["EPIC_AS_REPORTED", "TWO_FINGER_ROLL_180"])
        np.testing.assert_allclose(rows[0][1][:, 2], rows[1][1][:, 2])
        np.testing.assert_allclose(rows[0][1][:, :2], -rows[1][1][:, :2])

    def test_rejects_reflection(self):
        with self.assertRaises(ValueError):
            two_finger_grasp_rotations(np.diag([1., 1., -1.]))


if __name__ == "__main__":
    unittest.main()
