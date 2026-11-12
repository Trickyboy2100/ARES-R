import json
from pathlib import Path
import unittest
from ares_r.manipulation.grasp_verification import verify_grasp_phase
ROOT=Path(__file__).resolve().parents[1]
class GraspPhaseTests(unittest.TestCase):
    def setUp(self):
        self.params=json.loads((ROOT/'config/tray_to_groove_v2.json').read_text())
        self.delta={'before_voxels':100,'after_voxels':98,'removed_voxels':67,'removed_fraction':.6667,'added_fraction':.5204,'revision':'delta'}
        self.reads=[{'position_raw':37,'captured_at_unix':t} for t in [100.25,100.75,101.5]]
    def test_pre_lift_changed_scene_is_candidate_not_failure_or_confirmed(self):
        result=verify_grasp_phase(self.delta,self.reads,self.params,phase='HOLD_CANDIDATE',now=102)
        self.assertEqual(result['state'],'HOLD_CANDIDATE')
    def test_only_arrived_lift_plus_evidence_confirms(self):
        result=verify_grasp_phase(self.delta,self.reads,self.params,phase='POST_LIFT',initial_lift_arrived=True,lift_displacement_m=.1,now=102)
        self.assertEqual(result['state'],'VERIFICATION_AMBIGUOUS')
        self.delta['added_fraction']=.1
        result=verify_grasp_phase(self.delta,self.reads,self.params,phase='POST_LIFT',initial_lift_arrived=True,lift_displacement_m=.1,now=102)
        self.assertEqual(result['state'],'GRASP_CONFIRMED')
    def test_duplicate_or_missing_timestamps_fail(self):
        for row in self.reads:row['captured_at_unix']=101
        self.assertEqual(verify_grasp_phase(self.delta,self.reads,self.params,phase='HOLD_CANDIDATE',now=102)['result'],'FAIL')
    def test_continuous230_requires_actual230_not_legacy100(self):
        self.delta['added_fraction']=.1
        for measured,expected in ((.230,'GRASP_CONFIRMED'),(.100,'VERIFICATION_AMBIGUOUS')):
            result=verify_grasp_phase(self.delta,self.reads,self.params,phase='POST_LIFT',initial_lift_arrived=True,
                lift_displacement_m=measured,expected_lift_m=.230,now=102)
            self.assertEqual(result['state'],expected)
