import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ares_r.canonical_backend import CanonicalBackend

class SiftHoldDispatchTests(unittest.TestCase):
    def backend(self,root):
        b=CanonicalBackend.__new__(CanonicalBackend);b.root=root;b.roundtrip=Mock()
        b._physical_guard=threading.Lock();b._physical_process=None;b._base_running=False
        b.physical_status=Mock(return_value={'state':'IDLE'});return b
    def test_hold_requires_specific_auth_not_reset_auth(self):
        b=self.backend('.')
        with self.assertRaises(PermissionError):
            b.start_pick_reset_timing(dict(task_demo_id='right_arm_shaiwang_pick_reset_v1',hold_after_lift=True,
                authorization='RIGHT SHAIWANG STAGE1 PICK RESET',onsite_observer_confirmed=True))
    def test_hold_rejects_unrelated_demo(self):
        with self.assertRaises(ValueError):self.backend('.').start_pick_reset_timing(dict(hold_after_lift=True))
    def test_hold_launch_uses_distinct_runner_output_and_stop_latch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();p=root/'worklog/evidence/candidate';p.mkdir(parents=True);(p/'native-manifest.json').write_text('{}')
            b=self.backend(root)
            with patch('ares_r.manipulation.task_contract.verify_task'),patch('ares_r.manipulation.task_contract.task_sender'),patch('ares_r.canonical_backend.subprocess.Popen') as launch:
                launch.return_value.pid=123
                result=b.start_pick_reset_timing(dict(prepared=str(p),task_demo_id='right_arm_shaiwang_pick_reset_v1',hold_after_lift=True,
                    authorization='RIGHT SIFT PICK LIFT230 HOLD',onsite_observer_confirmed=True))
            try:
                argv=launch.call_args.args[0]
                self.assertIn(str(root/'scripts/run_sift_lift_hold.py'),argv)
                self.assertIn(str(p/'hold-execution'),argv)
                self.assertEqual(b._physical_abort_path,p/'timing-hold-stop.request')
                self.assertTrue(result['hold_after_lift'])
            finally:b._physical_stream.close()

if __name__=='__main__':unittest.main()
