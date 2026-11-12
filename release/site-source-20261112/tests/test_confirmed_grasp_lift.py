import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from resume_confirmed_grasp_lift import validate_checkpoint, lift_only


class ConfirmedLiftTests(unittest.TestCase):
    def checkpoint(self):
        return [dict(stage=s, state='PASS') for s in
                ('MOVE_PREGRASP', 'GRIPPER40', 'CONTACT_APPROACH', 'CLOSE')] + [
                    dict(stage='VERIFY_GRASP', state='FAULT')]

    def test_expected_checkpoint(self):
        validate_checkpoint(self.checkpoint())

    def test_no_duplicate_lift(self):
        e = self.checkpoint()
        e.insert(0, dict(stage='LIFT_INITIAL100', state='START'))
        with self.assertRaises(ValueError):
            validate_checkpoint(e)

    def test_missing_close(self):
        with self.assertRaises(ValueError):
            validate_checkpoint([e for e in self.checkpoint() if e['stage'] != 'CLOSE'])

    def test_lift_only_never_base_or_gripper(self):
        calls = []
        class Fake:
            def check_cancelled(self): pass
            def pick_segment(self, segment): calls.append(('segment', segment)); return {}
            def attach(self): calls.append(('attach',)); return {}
            def lift_remaining(self, distance): calls.append(('lift', distance)); return {}
        result = lift_only(Fake(), lambda *a: None)
        self.assertEqual(calls, [('segment', 'lift'), ('attach',), ('lift', .13)])
        self.assertEqual(result['result'], 'HOLD230')
