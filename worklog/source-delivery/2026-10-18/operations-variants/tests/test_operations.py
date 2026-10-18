import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ares_r.operations import OperationsRegistry, planning_world
from ares_r.scene_aware_dispatch import _motion_request


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = OperationsRegistry(self.temp.name)

    def write(self, action, **body):
        return self.registry.update(action, dict(body, expected_revision=self.registry.read()['revision']))

    def test_unknown_not_selected(self):
        self.assertEqual(len(self.registry.read()['dryer']['slots']), 6)
        with self.assertRaises(ValueError): self.registry.select('PLACE')

    def test_reservation_completion_not_detection(self):
        self.write('slot', slot_id='lower_left', occupancy='EMPTY')
        result = self.write('reserve', operation='PLACE')['result']
        with self.assertRaises(ValueError): self.registry.select('PLACE')
        with self.assertRaises(ValueError):
            self.write('complete', slot_id='lower_left', token=result['token'])
        self.assertEqual(self.registry.read()['dryer']['slots']['lower_left']['occupancy'], 'EMPTY')
        self.write('complete', slot_id='lower_left', token=result['token'], evidence_id='verified-1')
        self.assertEqual(self.registry.select('PICK')['slot_id'], 'lower_left')

    def test_concurrent_revision_conflict(self):
        def edit(_):
            try:
                self.registry.update('slot', {'expected_revision': 0,
                    'slot_id': 'lower_middle', 'occupancy': 'EMPTY'})
                return True
            except ValueError: return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(edit, range(2))), 1)

    def test_rotated_anchor_uses_local_not_body_offsets(self):
        self.write('slot', slot_id='upper_right', offset_m_rad=[.1, 0, .2, 0, 0, 0])
        t = [[0,-1,0,.5],[1,0,0,-.2],[0,0,1,1],[0,0,0,1]]
        self.write('anchor', T_body_corner=t, profile='dryer_place_corner',
                   observation_epoch=5, base_pose_revision=3, captured_at_unix=time.time())
        goal = self.registry.target('upper_right', 3, 5)
        np.testing.assert_allclose(goal['position_m'], [.5,-.1,1.2])
        for base, epoch in [(4,5),(3,6)]:
            with self.assertRaises(ValueError): self.registry.target('upper_right', base, epoch)

    def test_stale_reflected_or_wrong_profile_anchor_rejected(self):
        for t, stamp, profile in [(np.eye(4).tolist(), time.time()-400,'dryer_place_corner'),
                (np.diag([-1,1,1,1]).tolist(),time.time(),'dryer_place_corner'),
                (np.eye(4).tolist(),time.time(),'rightmost')]:
            with self.assertRaises(ValueError):
                self.write('anchor', T_body_corner=t, profile=profile,
                    observation_epoch=1, base_pose_revision=1, captured_at_unix=stamp)

    def test_off_preserves_robot_and_unclassified_protection(self):
        compiled = {'cuboids': {key: {} for key in ('camera_box','left_arm','chassis','unknown')},
                    'provenance': [{'object_id': 'camera_box','category':'OBSERVED_ENVIRONMENT'},
                                   {'object_id':'left_arm','category':'ROBOT'}]}
        result = planning_world(compiled, 'OFF')
        self.assertEqual(set(result['cuboids']), {'left_arm','chassis','unknown'})
        self.assertIn('camera_box', compiled['cuboids'])
        self.assertNotEqual(result['digest'], planning_world(compiled, 'ON')['digest'])

    def test_defaults_central_off_environment_auto(self):
        p = self.registry.read()['policy']
        self.assertIs(p['central_exclusion'], False)
        self.assertEqual(p['environment_avoidance'], 'AUTO')

    def test_nan_and_infinite_offset_rejected(self):
        for value in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                self.write('slot', slot_id='lower_left', offset_m_rad=[value,0,0,0,0,0])
        self.assertEqual(self.registry.read()['revision'], 0)

    def test_speed_edit_does_not_claim_commissioned(self):
        p = self.write('speed', name='custom', max_velocity_rad_s=.2,
                       max_acceleration_rad_s2=.3, state='COMMISSIONED')['result']
        self.assertEqual(p['state'], 'UNCOMMISSIONED')

    def test_request_override_roundtrip(self):
        request = _motion_request({'arm':'right','position_m':[.5,-.2,1],
            'environment_avoidance':'OFF','central_exclusion':False})
        request.validate()
        self.assertEqual(request.constraints.environment_avoidance, 'OFF')
        self.assertIs(request.constraints.central_exclusion, False)

    def test_software_limits_can_be_disabled_without_modifying_site(self):
        self.write('software_limits', joint_lower_rad=[-1]*6, joint_upper_rad=[1]*6,
                   max_joint_delta_rad=.5)
        self.write('software_limits', joint_lower_rad=None, joint_upper_rad=None,
                   max_joint_delta_rad=None)
        self.assertIsNone(self.registry.read()['software_limits']['max_joint_delta_rad'])

    def test_backend_execution_requires_exact_preview_hash(self):
        from ares_r.canonical_backend import CanonicalBackend
        backend = CanonicalBackend.__new__(CanonicalBackend)
        backend.dispatcher = Mock()
        backend.dispatcher.motion_preview.return_value = {'arm':'right',
            'execution_package_ready':True,'trajectory_hash':'sha256:approved'}
        with patch('ares_r.canonical_backend.subprocess.Popen') as sender:
            with self.assertRaises(PermissionError): backend.motion_execute({})
            with self.assertRaises(ValueError):
                backend.motion_execute({'authorization':'RIGHT SCENE_AWARE SUPERVISED',
                    'onsite_observer_confirmed':True,'plan_id':'PLAN_A',
                    'trajectory_hash':'sha256:different'})
            sender.assert_not_called()

    def test_saved_profile_does_not_inherit_old_commissioning(self):
        profile = {'arm':'right','purpose':'place','command':'320,2,4,1,1,0',
                   'camera_id':1,'space_id':2,'object_id':4,
                   'output_frame':'right_arm_base_candidate', 'state':'COMMISSIONED'}
        self.write('dryer_config', anchor_profile='corner', detection_profile=profile)
        self.assertEqual(self.registry.read()['dryer']['detection_profile']['state'],'UNCOMMISSIONED')


if __name__ == '__main__': unittest.main()
