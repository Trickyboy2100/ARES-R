import unittest

import numpy as np

from ares_r.motion.constrained_manifold_seed import _resample, _shortest_angle_delta
from ares_r.motion.tcp_orientation import level_rotation, nearest_level_roll_branch


class ConstrainedManifoldSeedTest(unittest.TestCase):
    def test_shortest_angle_crosses_wrap(self):
        self.assertAlmostEqual(_shortest_angle_delta(np.deg2rad(170), np.deg2rad(-170)),
                               np.deg2rad(20))

    def test_resample_keeps_endpoints(self):
        source = np.array([[0., 1.], [2., 3.], [4., 5.]])
        result = _resample(source, 7)
        np.testing.assert_allclose(result[0], source[0])
        np.testing.assert_allclose(result[-1], source[-1])
        self.assertEqual(result.shape, (7, 2))

    def test_preserves_nearest_roll_branch(self):
        self.assertEqual(nearest_level_roll_branch(level_rotation(.7, 0)), 0)
        self.assertEqual(nearest_level_roll_branch(level_rotation(.7, 1)), 1)


if __name__ == "__main__":
    unittest.main()
