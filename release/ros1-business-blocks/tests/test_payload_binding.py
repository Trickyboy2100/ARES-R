from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent/'site-source-20261112/src')]
from blocks.payload_binding import validate_payload_session

class PayloadBindingTests(unittest.TestCase):
    def setUp(self):
        delta=dict(before_voxels=100,after_voxels=80,removed_voxels=30,
                   removed_fraction=.3,added_fraction=.1,revision='source-cloud')
        self.session=dict(state='HELD_CONFIRMED',object_type='sieve',tool_revision='tool3',
                          geometry_revision='g1',evidence=dict(verification={'result':'PASS','readbacks':[{'position_raw':100},{'position_raw':101}]},local_scene_delta=delta))
        self.args=dict(object_type='sieve',tool_revision='tool3',geometry_revision='g1',now=100,
                       readbacks=[dict(captured_at_unix=99,position_raw=100),dict(captured_at_unix=100,position_raw=101)],
                       parameters=dict(gripper={'raw_closed':0},grasp_verification=dict(
                           maximum_readback_spread_raw=20,minimum_hold_above_closed_raw=20,
                           minimum_removed_voxels=10,minimum_removed_fraction=.1,maximum_unexpected_added_fraction=.5)))
    def test_current_hold_reuses_verifier(self):
        self.assertTrue(validate_payload_session(self.session,**self.args)['validated'])
    def test_stale_feedback(self):
        self.args['readbacks'][0]['captured_at_unix']=90
        with self.assertRaisesRegex(ValueError,'WINDOW'):validate_payload_session(self.session,**self.args)
    def test_tool_changed(self):
        with self.assertRaisesRegex(ValueError,'tool_revision'):
            validate_payload_session(self.session,**dict(self.args,tool_revision='new'))
    def test_empty_closed_gripper(self):
        for row in self.args['readbacks']:row['position_raw']=0
        with self.assertRaisesRegex(ValueError,'HELD'):validate_payload_session(self.session,**self.args)
    def test_grasp_original_unconfirmed(self):
        self.session['evidence']['verification']['result']='FAIL'
        with self.assertRaisesRegex(ValueError,'ORIGINAL'):validate_payload_session(self.session,**self.args)

    def test_open_gripper_cannot_reuse_held_session(self):
        for row in self.args['readbacks']:row['position_raw']=400
        with self.assertRaisesRegex(ValueError,'POSITION_CHANGED'):
            validate_payload_session(self.session,**self.args)
