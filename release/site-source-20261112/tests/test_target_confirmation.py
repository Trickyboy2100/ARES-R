import importlib.util,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('task_runner',ROOT/'scripts/run_task_pick_reset_timing.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

#: 2026-11-06 probe: the 5700 pick detector latches one of two discrete solutions.
BRANCH_A=[0.4802,-0.5092,-0.1688,1.5791,3.0927,0.8286]
BRANCH_B=[0.4831,-0.5061,-0.1686,1.5809,3.0940,0.8004]


class _Pose:
    def __init__(self,values):self._values=list(values)
    def values(self):return list(self._values)


class _Detection:
    def __init__(self,values=None,raw='raw'):
        self.success=values is not None
        self.pose=None if values is None else _Pose(values)
        self.raw_response=raw


def _sequence(items):
    calls={'n':0}
    def detect(index):
        calls['n']+=1
        value=items[min(index,len(items)-1)]
        return _Detection(value,raw='sample-%d'%index)
    detect.calls=calls
    return detect


class TargetConfirmationTests(unittest.TestCase):
    """The gate asks whether the camera still reproduces the planned pose."""
    def test_accepts_when_a_later_attempt_reproduces_the_planned_pose(self):
        proof=runner.confirm_target(_sequence([BRANCH_B,BRANCH_B,BRANCH_A]),BRANCH_A)
        self.assertTrue(proof['accepted'])
        self.assertEqual(len(proof['attempts']),3)
        self.assertLessEqual(proof['position_gap_m'],0.003)
        self.assertEqual([a['ok'] for a in proof['attempts']],[True,True,True])

    def test_rejects_when_no_attempt_reproduces_the_planned_pose(self):
        moved=[0.4902,-0.5092,-0.1688,1.5791,3.0927,0.8286]
        proof=runner.confirm_target(_sequence([moved]),BRANCH_A,max_attempts=4)
        self.assertFalse(proof['accepted'])
        self.assertEqual(len(proof['attempts']),4)
        self.assertAlmostEqual(proof['position_gap_m'],0.010,places=3)

    def test_failed_detections_are_recorded_not_fatal(self):
        def detect(index):
            return _Detection(None if index<2 else BRANCH_A)
        proof=runner.confirm_target(detect,BRANCH_A)
        self.assertTrue(proof['accepted'])
        self.assertEqual([a['ok'] for a in proof['attempts']],[False,False,True])

    def test_every_attempt_is_auditable(self):
        proof=runner.confirm_target(_sequence([BRANCH_B,BRANCH_A]),BRANCH_A)
        for row in proof['attempts']:
            self.assertIn('position_gap_m',row)
            self.assertIn('pose',row)
            self.assertIn('raw_response',row)

    def test_first_attempt_short_circuits_a_matching_detection(self):
        detect=_sequence([BRANCH_A])
        proof=runner.confirm_target(detect,BRANCH_A)
        self.assertTrue(proof['accepted'])
        self.assertEqual(detect.calls['n'],1)


if __name__=='__main__':unittest.main()
