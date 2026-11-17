import json
import os
from pathlib import Path
import unittest

import numpy as np

from ares_r.motion.joint_mirror import JointMirrorModel
from ares_r.perception.robot_collision import transform_xyz_rpy


ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / 'config/robot_collision_model.json').read_text())
ASSETS = Path(os.environ.get('ARES_R_TEST_ASSET_ROOT', MODEL['asset_root']))


@unittest.skipUnless(ASSETS.exists(), 'pinned site assets required')
class JointMirrorTests(unittest.TestCase):
    def setUp(self):
        self.model = JointMirrorModel(ROOT, asset_root=ASSETS)
        # Actual onsite state recorded before the 2026-11-16 mirror request.
        self.live = {'arms': {
            'left': {'joints_rad': [-.7742811142, -.5016770911, 2.038272295,
                                    -4.668497789, -.7814926401, 5.845175558]},
            'right': {'joints_rad': [-2.695206721, .04630777385, -1.350556719,
                                     -4.804235012, -1.204408956, -.5236731266]}}}

    def test_left_mirrors_all_six_right_joint_centres_on_nearby_branch(self):
        plan = self.model.solve('right', 'left', self.live)
        self.assertLess(max(plan['joint_point_error_mm']), 1)
        self.assertLess(max(abs(v) for v in plan['delta_deg']), 90)

    def test_right_mirrors_left_without_moving_hardware(self):
        plan = self.model.solve('left', 'right', self.live)
        target = self.model.frames('right', plan['target_rad'])[:, :3, 3]
        source = self.model.frames('left', self.live['arms']['left']['joints_rad'])[:, :3, 3]
        self.assertLess(np.linalg.norm(target - source * [1, -1, 1], axis=1).max(), .001)

    def test_same_arm_rejected(self):
        with self.assertRaises(ValueError):
            self.model.solve('left', 'left', self.live)

    def live_tcp_fixture(self):
        states = json.loads((ROOT/'tests/fixtures/mirror_tcp_20261117.json').read_text())
        live = {'arms': {}}
        for side, value in states.items():
            self.model.audits[side]['diagnostics']['tool_data'] = dict(
                tool_id=value['tool_id'], pose_mm_rad=value['tool_mm_rad'])
            mount = self.model.world['arms'][side]
            pose = transform_xyz_rpy(mount['base_xyz_m'], mount['base_rpy_rad']) @ transform_xyz_rpy(
                np.asarray(value['tcp_mm_rad'][:3])*.001, value['tcp_mm_rad'][3:])
            live['arms'][side] = dict(joints_rad=value['actual_rad'], T_body_tcp=pose.tolist())
        return live

    def test_tool_aware_tcp_mirror_in_both_directions_retains_proper_frames(self):
        live = self.live_tcp_fixture()
        reflection = np.diag([1., -1., 1.])
        for source, destination in [('right', 'left'), ('left', 'right')]:
            plan = self.model.solve(source, destination, live, match_tcp=True)
            goal = np.asarray(plan['tcp_target_body'])
            source_pose = np.asarray(live['arms'][source]['T_body_tcp'])
            np.testing.assert_allclose(goal[:3, 3], reflection @ source_pose[:3, 3])
            np.testing.assert_allclose(goal[:3, 0], reflection @ source_pose[:3, 0])
            np.testing.assert_allclose(goal[:3, 2], reflection @ source_pose[:3, 2])
            np.testing.assert_allclose(goal[:3, 1], -reflection @ source_pose[:3, 1])
            self.assertAlmostEqual(np.linalg.det(goal[:3, :3]), 1.)
            self.assertLess(plan['tcp_predicted_position_error_mm'], .5)
            self.assertLess(plan['tcp_predicted_orientation_error_deg'], .1)
            self.assertFalse(plan['joint_centres_exact'])
            self.assertEqual(plan['tcp_source_provenance'], 'LIVE_NATIVE_ACTUAL')
            self.assertIn('tool_binding', plan)

    def test_tcp_correction_does_not_change_stored_tool_calibration(self):
        live = self.live_tcp_fixture()
        before = json.dumps(self.model.audits, sort_keys=True)
        plan = self.model.solve('right', 'left', live, match_tcp=True)
        self.assertEqual(json.dumps(self.model.audits, sort_keys=True), before)
        self.assertLess(max(abs(v) for v in plan['delta_deg']), 45)
        self.assertGreater(abs(plan['delta_deg'][5]), 20)

    def test_invalid_left_handed_source_frame_rejected(self):
        live = self.live_tcp_fixture()
        live['arms']['right']['T_body_tcp'][0][0] *= -1
        live['arms']['right']['T_body_tcp'] = np.diag([1., -1., 1., 1.]).tolist()
        with self.assertRaisesRegex(ValueError, 'right-handed'):
            self.model.solve('right', 'left', live, match_tcp=True)
