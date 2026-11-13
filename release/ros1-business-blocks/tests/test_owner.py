import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent/'ros1-blocks-center-restore'),
                str(ROOT.parent/'site-source-20261112/src')]
from blocks.console import BusinessConsole
from blocks.contracts import registry

class Backend:
    def __init__(self, root):
        self.root = root
        self._physical_guard = threading.RLock()
        self._base_running = False
        self._physical_process = None
        self.roundtrip = type('Roundtrip', (), {'check_physical_access': lambda s,b: None})()
    def physical_status(self):
        return {'state': 'IDLE'}

class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        profile = next(p for p in registry() if p['id']=='P01')
        relative = profile['profile_source'].split('release/site-source-20261112/',1)[1]
        target = self.root/relative
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT.parent/'site-source-20261112'/relative).read_bytes())
        self.console = BusinessConsole(Backend(self.root))
        self.console._run = lambda definition: None
        self.body = dict(alias='ros-prepare-P01', authorization='RUN ros-prepare-P01',
                         expected_profile_revision=profile['profile_revision'], request_id='prepare-1',
                         onsite_observer_confirmed=True, prepared_environment_confirmed=True)
    def tearDown(self):
        self.tmp.cleanup()
    def test_shared_owner_blocks_other_request(self):
        self.console.start(self.body)
        with self.assertRaisesRegex(RuntimeError,'占用'):
            self.console.start(dict(self.body,request_id='other'))
    def test_same_request_terminal_dedup(self):
        first=self.console.start(self.body)
        self.console.update(state='SUCCEEDED')
        duplicate=self.console.start(self.body)
        self.assertEqual(first['run_id'],duplicate['run_id'])
        self.assertTrue(duplicate['duplicate_suppressed'])
    def test_restart_does_not_resume(self):
        first=self.console.start(self.body)
        restarted=BusinessConsole(Backend(self.root))
        self.assertEqual(restarted.job['state'],'RECOVERY_REQUIRED')
        self.assertEqual(restarted.start(self.body)['run_id'],first['run_id'])
    def test_profile_change_rejected(self):
        with self.assertRaisesRegex(ValueError,'REVISION'):
            self.console.start(dict(self.body,expected_profile_revision='wrong'))
    def test_original_utility_remains_in_catalog(self):
        self.assertIn('block-01-center-restore-right',[d['alias'] for d in self.console.catalog()['demos']])
    def test_base_active_rejects_prepare(self):
        self.console.backend._base_running=True
        with self.assertRaisesRegex(RuntimeError,'任务运行'):
            self.console.start(self.body)
