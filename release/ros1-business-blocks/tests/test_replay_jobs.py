from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from blocks.replay_jobs import ReplayJobs

class Jobs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'replay.sqlite';self.jobs=ReplayJobs(self.path)
    def tearDown(self):self.jobs.close();self.tmp.cleanup()
    def test_dropped_ack_duplicate_and_restart(self):
        g=dict(request_id='one',block_id='pick.scale.sieve.v1')
        a=self.jobs.start(g);self.assertFalse(self.jobs.start(g)['new_job'])
        self.jobs.close();self.jobs=ReplayJobs(self.path)
        self.assertEqual(a['run_id'],self.jobs.start(g)['run_id'])
    def test_busy_never_preempts(self):
        self.jobs.start(dict(request_id='a'))
        with self.assertRaisesRegex(ValueError,'BUSY'):self.jobs.start(dict(request_id='b'))
    def test_terminal_request_never_runs_again(self):
        g=dict(request_id='a');r=self.jobs.start(g);self.jobs.finish(r['run_id'],'SUCCEEDED')
        self.assertEqual(self.jobs.start(g)['state'],'SUCCEEDED')
        self.assertFalse(self.jobs.start(g)['new_job'])
    def test_conflicting_reuse(self):
        self.jobs.start(dict(request_id='a',block_id='x'))
        with self.assertRaisesRegex(ValueError,'CONFLICT'):self.jobs.start(dict(request_id='a',block_id='y'))
    def test_cancel_requires_stop_confirmation(self):
        r=self.jobs.start(dict(request_id='a'))
        self.assertEqual(self.jobs.cancel(r['run_id']),'STOPPING')
        with self.assertRaisesRegex(ValueError,'BUSY'):self.jobs.start(dict(request_id='b'))
        self.assertEqual(self.jobs.cancel(r['run_id'],stop_confirmed=True),'STOPPED')
    def test_unknown_dispatch_keeps_owner(self):
        r=self.jobs.start(dict(request_id='a'));self.jobs.finish(r['run_id'],'UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'RECOVERY'):self.jobs.start(dict(request_id='b'))
