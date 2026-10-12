import json
import tempfile
import unittest
from pathlib import Path

from research.skill_handoff_smoke.audit_plans import audit_tree
from research.skill_handoff_smoke.headroom import evaluate_headroom


class SkillHandoffResearchSmokeTest(unittest.TestCase):
    def test_planner_success_does_not_imply_downstream_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'run'
            folder.mkdir()
            (folder / 'planner_request.json').write_text(json.dumps({
                'scene_snapshot_id': 'SCENE_A', 'start_rad': [0]*6,
                'runtime_motion_goal': {'position_m': [.6, -.2, 1.2]}}))
            (folder / 'planning.json').write_text(json.dumps({
                'scene_snapshot_id': 'SCENE_A', 'observed_result': 'SUCCESS',
                'trajectory_points_rad': [[0]*6, [.1]*6],
                'independent_dense_validation': {'collision_free': True},
                'orientation_validation': {'passed': True}}))
            rows, report = audit_tree(Path(tmp))
            self.assertEqual(report['verified_planning_success_count'], 1)
            self.assertEqual(report['known_downstream_transition_labels'], 0)
            self.assertIsNone(rows[0]['downstream_skill_success'])
            self.assertFalse(rows[0]['execution_eligible'])

    def test_mismatched_scene_is_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'planner_request.json').write_text('{"scene_snapshot_id":"SCENE_A"}')
            (root/'planning.json').write_text(json.dumps({
                'scene_snapshot_id': 'SCENE_B', 'observed_result': 'SUCCESS',
                'trajectory_points_rad': [[0], [1]],
                'independent_dense_validation': {'collision_free': True}}))
            _, report = audit_tree(root)
            self.assertEqual(report['verified_planning_success_count'], 0)

    def test_empty_labels_cannot_pass_scientific_gate(self):
        result = evaluate_headroom([{'context_id':'A','candidate_id':'X',
            'heuristic_rank':0,'downstream_skill_success':None}])
        self.assertEqual(result['eligible_contexts'], 0)
        self.assertFalse(result['ready_for_rl_comparison'])

    def test_oracle_gap_identifies_wrong_greedy_terminal(self):
        data = [
            {'context_id':'A','candidate_id':'short','heuristic_rank':0,
             'downstream_skill_success':False},
            {'context_id':'A','candidate_id':'long','heuristic_rank':1,
             'downstream_skill_success':True},
        ]
        result = evaluate_headroom(data)
        self.assertEqual(result['oracle_advantage_mean'], 1)
        self.assertEqual(result['any_candidate_choice_matters'], 1)
        self.assertFalse(result['ready_for_rl_comparison'])

    def test_no_oracle_gap_if_heuristic_optimal(self):
        data = [
            {'context_id':'A','candidate_id':'a','heuristic_rank':0,
             'downstream_skill_success':True},
            {'context_id':'A','candidate_id':'b','heuristic_rank':1,
             'downstream_skill_success':False},
        ]
        self.assertEqual(evaluate_headroom(data)['oracle_advantage_mean'], 0)


if __name__ == '__main__':
    unittest.main()
