import importlib.util
from pathlib import Path
import unittest
import numpy as np
from ares_r.perception.robot_collision import transform_xyz_rpy

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tcp_arrival_runner', ROOT/'scripts/run_joint_mirror.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class TcpArrivalTests(unittest.TestCase):
    def setUp(self):
        self.world = {'arms': {'left': {'base_xyz_m': [0., .2, 1.2], 'base_rpy_rad': [0., 0., 2.35619449]}}}
        self.actual = [120., -250., 400., .1, -.2, .3]
        mount = self.world['arms']['left']
        goal = transform_xyz_rpy(mount['base_xyz_m'], mount['base_rpy_rad']) @ transform_xyz_rpy(
            np.asarray(self.actual[:3])*.001, self.actual[3:])
        self.plan = dict(tcp_target_body=goal.tolist(), tcp_position_tolerance_mm=3., tcp_orientation_tolerance_deg=1.)

    def test_native_controller_tcp_is_converted_to_body_before_comparison(self):
        result = RUNNER.tcp_arrival_verification(self.world, 'left', self.plan, {'tcp_mm_rad': self.actual})
        self.assertTrue(result['tcp_mirror_verified'])
        self.assertLess(result['tcp_position_error_mm'], 1e-8)
        self.assertLess(result['tcp_orientation_error_deg'], 1e-8)

    def test_joint_arrival_without_tcp_proof_is_not_tcp_success(self):
        result = RUNNER.tcp_arrival_verification(self.world, 'left', self.plan, {'completed': True})
        self.assertFalse(result['tcp_mirror_verified'])
        self.assertEqual(result['reason'], 'MIRROR_TCP_ARRIVAL_PROOF_MISSING')

    def test_position_and_orientation_errors_are_independent_gates(self):
        for index, change in [(0, 4.), (5, .03)]:
            actual = self.actual.copy()
            actual[index] += change
            result = RUNNER.tcp_arrival_verification(self.world, 'left', self.plan, {'tcp_mm_rad': actual})
            self.assertFalse(result['tcp_mirror_verified'])
            self.assertEqual(result['reason'], 'MIRROR_TCP_ARRIVAL_MISMATCH')

    def test_nonfinite_or_truncated_feedback_is_rejected(self):
        for values in [[0.]*5, [float('nan')]*6]:
            result = RUNNER.tcp_arrival_verification(self.world, 'left', self.plan, {'tcp_mm_rad': values})
            self.assertFalse(result['tcp_mirror_verified'])
            self.assertEqual(result['reason'], 'MIRROR_TCP_ARRIVAL_PROOF_INVALID')
