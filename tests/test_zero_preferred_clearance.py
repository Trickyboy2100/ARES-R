import unittest

from ares_r.motion.scene_aware_motion import ClearancePolicy, evaluate_hard_validity


class ZeroPreferredClearanceTests(unittest.TestCase):
    def test_zero_preference_preserves_hard_collision(self):
        policy = ClearancePolicy('ZERO_PREFERRED_ONLY', 0.0)
        policy.validate()
        for gap, expected in ((.0001, True), (0.0, False), (-.001, False)):
            plan = {'observed_result': 'SUCCESS',
                    'clearance_m': {'start': .01, 'goal': gap},
                    'independent_dense_validation': {
                        'collision_free': gap > 0, 'min_clearance_m': gap}}
            self.assertEqual(evaluate_hard_validity(plan, policy)['hard_valid'], expected)

    def test_negative_preference_rejected(self):
        with self.assertRaises(ValueError):
            ClearancePolicy('INVALID', -.001).validate()
