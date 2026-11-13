import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / 'site-source-20261112/src')]
from blocks.contracts import registry
from blocks.dryer_slots import bind_target, read_target, assert_binding_current, save_binding


class DryerSlotsTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'profiles/templates/ros_dryer_tasks.json').read_text())
        slots = {slot: dict(offset_m_rad=[.1, .2, .3, 0, 0, 0],
                            offset_frame='DETECTION', occupancy='EMPTY', reservation=None)
                 for slot in self.config['slots']}
        self.state = dict(revision=21, dryer=dict(slots=slots, anchor_revision='a', anchor=dict(
            T_body_corner=[[0,-1,0,1],[1,0,0,2],[0,0,1,3],[0,0,0,1]],
            captured_at_unix=100, observation_epoch='epoch', base_pose_revision='base')))
        self.block = 'place.dryer.tray.lower_middle.v1'

    def bind(self, block=None):
        return bind_target(block or self.block, self.state, self.config,
                           observation_epoch='epoch', base_pose_revision='base', now=101)

    def test_twelve_unique_entries(self):
        rows = [r for r in registry() if r.get('family') == 'dryer_six_slots']
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r['block_id'] for r in rows}), 12)
        for row in rows:
            result = self.bind(row['block_id'])
            self.assertEqual(result['slot_id'], row['slot_id'])
            self.assertFalse(row['physical_start_enabled'])

    def test_actual_rotation_applied(self):
        result = self.bind()
        self.assertEqual([r[3] for r in result['T_body_slot'][:3]], [.8, 2.1, 3.3])

    def test_pick_and_place_share_slot_but_have_distinct_tcp(self):
        actions = self.config['slots']['lower_middle']
        actions['pick']['tcp_offset_m_rad'] = [0,0,.02,0,0,0]
        actions['place']['tcp_offset_m_rad'] = [0,0,-.01,0,0,0]
        pick = self.bind('pick.dryer.tray.lower_middle.v1')
        place = self.bind()
        self.assertAlmostEqual(pick['T_body_tcp'][2][3]-place['T_body_tcp'][2][3], .03)
        self.assertFalse(pick['occupancy_matches'])
        self.assertTrue(place['occupancy_matches'])

    def test_ui_edit_changes_binding(self):
        before = self.bind()
        self.state['dryer']['slots']['lower_middle']['offset_m_rad'][0] += .01
        after = self.bind()
        self.assertNotEqual(before['binding_sha256'], after['binding_sha256'])
        self.assertNotEqual(before['T_body_slot'], after['T_body_slot'])

    def test_unset_tcp_remains_explicit(self):
        result = self.bind()
        self.assertIsNone(result['T_body_tcp'])
        self.assertFalse(result['geometry_configured'])
        self.assertFalse(result['execution_package_ready'])

    def test_stale_epoch_base_and_time_rejected(self):
        for field, value in [('observation_epoch','old'),('base_pose_revision','moved'),
                             ('captured_at_unix',-500),('captured_at_unix',200)]:
            state = copy.deepcopy(self.state)
            self.state['dryer']['anchor'][field] = value
            with self.assertRaisesRegex(ValueError,'STALE'):
                self.bind()
            self.state = state

    def test_invalid_matrix_and_nonfinite_offsets_rejected(self):
        self.state['dryer']['anchor']['T_body_corner'][0][0] = 4
        with self.assertRaises(ValueError): self.bind()
        self.setUp()
        self.state['dryer']['slots']['lower_middle']['offset_m_rad'][0] = float('nan')
        with self.assertRaises(ValueError): self.bind()

    def test_body_display_values_cannot_be_double_rotated(self):
        self.state['dryer']['slots']['lower_middle']['offset_frame'] = 'BODY'
        with self.assertRaisesRegex(ValueError, 'FRAME'): self.bind()

    def test_missing_slot_offset(self):
        self.state['dryer']['slots']['lower_middle']['offset_m_rad'] = None
        with self.assertRaisesRegex(ValueError, 'NOT_CONFIGURED'): self.bind()

    def test_atomic_input_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            state_path = site / 'worklog/runtime/operations/state.json'
            config_path = site / 'config/ros_dryer_tasks.json'
            state_path.parent.mkdir(parents=True)
            config_path.parent.mkdir()
            state_path.write_text(json.dumps(self.state))
            config_path.write_text(json.dumps(self.config))
            with patch('blocks.dryer_slots.time.time', return_value=101):
                binding = read_target(site,self.block,'epoch','base')
                assert_binding_current(binding,site,'epoch','base')
                self.state['revision'] += 1
                state_path.write_text(json.dumps(self.state))
                with self.assertRaisesRegex(ValueError,'CHANGED'):
                    assert_binding_current(binding,site,'epoch','base')
            save_binding(binding,site/'binding.json')
            with self.assertRaises(FileExistsError): save_binding(binding,site/'binding.json')

    def test_target_query_does_not_mutate_registry(self):
        before = copy.deepcopy(self.state)
        self.bind()
        self.assertEqual(before,self.state)
