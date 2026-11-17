import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from ares_r.demos.console import DemoConsole
class RecoveryTests(unittest.TestCase):
 def make(self,root,state='RECOVERY_REQUIRED'):
  c=DemoConsole.__new__(DemoConsole);c.root=Path(root);c.path=c.root/'job.json';c.lock=threading.RLock();c.thread=None;c.child=None;c.cancel=threading.Event();c.token='old';c.job={'state':state,'run_id':'old'};return c
 def test_health_failure_retains_fault(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.make(d)
   with patch('ares_r.motion.mirror_native.snapshot',side_effect=RuntimeError('CONTROLLER_FAULT')):
    with self.assertRaisesRegex(RuntimeError,'CONTROLLER_FAULT'):c.recover({'confirmation':'RESET_FAILED_DEMO'})
   self.assertEqual(c.job['state'],'RECOVERY_REQUIRED')
 def test_health_success_releases_task_without_motion(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.make(d)
   with patch('ares_r.motion.mirror_native.snapshot',return_value={'controller_health_passed':True}) as snap:
    r=c.recover({'confirmation':'RESET_FAILED_DEMO'})
   self.assertTrue(r['ok']);self.assertFalse(r['auto_resume']);self.assertEqual(c.job['state'],'STOPPED');self.assertEqual(snap.call_count,2)
 def test_running_task_cannot_reset(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.make(d,'RUNNING')
   with self.assertRaisesRegex(RuntimeError,'NO_FAILED'):c.recover({'confirmation':'RESET_FAILED_DEMO'})
