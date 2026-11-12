import unittest,tempfile,json,threading
from pathlib import Path
from center_restore.console import CenterRestoreConsole,ALIAS


class Backend:
    def __init__(self,r):
        self.root=r;self._physical_guard=threading.RLock();self._base_running=False;self._physical_process=None
        self.roundtrip=type('R',(),{'check_physical_access':lambda s,b:None})()
    def physical_status(self):return {'state':'IDLE'}


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)
        (self.r/'demos').mkdir();(self.r/'demos/catalog_aliases.json').write_text('{"demos":[]}')
        self.c=CenterRestoreConsole(Backend(self.r));self.c._run=lambda definition:None
        self.b=dict(alias=ALIAS,authorization='RUN '+ALIAS,request_id='unique',target_mode='CAPTURE_START',empty_hand_confirmed=True,onsite_observer_confirmed=True,prepared_environment_confirmed=True)
    def tearDown(self):self.tmp.cleanup()
    def test_duplicate_active(self):
        a=self.c.start(self.b);b=self.c.start(self.b);self.assertEqual(a['run_id'],b['run_id']);self.assertTrue(b['duplicate_suppressed'])
    def test_duplicate_terminal(self):
        a=self.c.start(self.b);self.c.update(state='SUCCEEDED')
        self.assertEqual(a['run_id'],self.c.start(self.b)['run_id'])
    def test_extra_goal_busy(self):
        self.c.start(self.b)
        with self.assertRaisesRegex(RuntimeError,'占用'):self.c.start(dict(self.b,request_id='other'))
    def test_restarted_no_replay(self):
        a=self.c.start(self.b);c=CenterRestoreConsole(Backend(self.r));c._run=lambda d:(_ for _ in ()).throw(Exception('must not run'))
        self.assertEqual(c.job['state'],'RECOVERY_REQUIRED');self.assertTrue(c.start(self.b)['duplicate_suppressed'])
    def test_changed_request_id_payload(self):
        self.c.start(self.b)
        with self.assertRaisesRegex(ValueError,'PAYLOAD_CHANGED'):self.c.start(dict(self.b,target_mode='SAVED_POSE_REF'))
    def test_empty_unknown(self):
        with self.assertRaisesRegex(ValueError,'EMPTY_HAND'):self.c.start(dict(self.b,empty_hand_confirmed=False))
