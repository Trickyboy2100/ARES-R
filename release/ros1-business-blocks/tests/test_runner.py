import sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from blocks.runner import BlockRunner,PayloadSessions,BlockFault
from blocks.contracts import PICK,PLACE
class Adapter:
    mode='OFFLINE'
    def __init__(self,fail=None,stale=None):self.calls=[];self.fail=fail;self.stale=stale;self.stop_calls=0
    def stage(self,stage,**kwargs):
        self.calls.append(stage)
        return dict(verified=stage!=self.fail,observed_monotonic_s=time.monotonic()-(10 if stage==self.stale else 0),
                    object_type='sieve',tool_revision='tool3',geometry_revision='geometry-v1')
    def stop(self):self.stop_calls+=1;return True
class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'payloads.sqlite';self.sessions=PayloadSessions(self.path)
    def tearDown(self):self.sessions.close();self.tmp.cleanup()
    def pick(self,adapter=None):return BlockRunner(adapter or Adapter(),self.sessions).run(dict(stages=list(PICK)))
    def test_pick_no_reset_and_persistent_session(self):
        a=Adapter();r=self.pick(a);self.assertTrue(r['success']);self.assertEqual(a.calls[-1],'VERIFY_AFTER_LIFT')
        self.assertNotIn('RELEASE_CONFIRMED',a.calls)
        self.sessions.close();self.sessions=PayloadSessions(self.path)
        self.assertEqual(self.sessions.get(r['payload_session_id'])['state'],'HELD_CONFIRMED')
    def test_pick_then_place_session(self):
        p=self.pick();a=Adapter();r=BlockRunner(a,self.sessions).run(dict(stages=list(PLACE)+['CENTER']),payload_session_id=p['payload_session_id'])
        self.assertTrue(r['success']);self.assertEqual(r['payload_state'],'RELEASED_CONFIRMED');self.assertEqual(a.calls[-2:],['RETREAT_CLEAR','CENTER'])
    def test_no_release_on_failed_descent(self):
        p=self.pick();a=Adapter(fail='CONTROLLED_DESCEND');r=BlockRunner(a,self.sessions).run(dict(stages=list(PLACE)+['CENTER']),payload_session_id=p['payload_session_id'])
        self.assertFalse(r['success']);self.assertNotIn('RELEASE_CONFIRMED',a.calls);self.assertEqual(r['payload_state'],'UNCERTAIN')
    def test_no_detach_no_center_when_release_unknown(self):
        p=self.pick();a=Adapter(fail='RELEASE_CONFIRMED');r=BlockRunner(a,self.sessions).run(dict(stages=list(PLACE)+['CENTER']),payload_session_id=p['payload_session_id'])
        self.assertNotIn('RETREAT_CLEAR',a.calls);self.assertEqual(r['payload_state'],'UNCERTAIN')
    def test_failed_retreat_keeps_released_session(self):
        p=self.pick();a=Adapter(fail='RETREAT_CLEAR');r=BlockRunner(a,self.sessions).run(dict(stages=list(PLACE)+['CENTER']),payload_session_id=p['payload_session_id'])
        self.assertEqual(r['payload_state'],'RELEASED_CONFIRMED');self.assertNotIn('CENTER',a.calls)
    def test_verification_stale_no_session_created(self):
        a=Adapter(stale='VERIFY_AFTER_LIFT');r=self.pick(a);self.assertFalse(r['success']);self.assertEqual(r['payload_session_id'],'')
    def test_missing_session_rejected(self):
        with self.assertRaisesRegex(BlockFault,'UNKNOWN'):BlockRunner(Adapter(),self.sessions).run(dict(stages=list(PLACE)))
    def test_tool_mismatch_before_scene(self):
        sid=self.sessions.create('sieve','other-tool','geometry-v1',{'old':True});a=Adapter()
        r=BlockRunner(a,self.sessions).run(dict(stages=list(PLACE)),payload_session_id=sid)
        self.assertFalse(r['success']);self.assertEqual(a.calls,['VERIFY_PAYLOAD'])
    def test_cancel_does_not_continue(self):
        a=Adapter();r=BlockRunner(a,self.sessions).run(dict(stages=list(PICK)),cancelled=lambda:len(a.calls)==3)
        self.assertEqual(r['terminal_state'],'STOPPED');self.assertNotIn('CONTACT',a.calls)
    def test_real_adapter_not_released(self):
        a=Adapter();a.mode='PHYSICAL'
        with self.assertRaisesRegex(BlockFault,'NOT_RELEASED'):self.pick(a)
    def test_move_back_added_to_pick_rejected(self):
        with self.assertRaisesRegex(BlockFault,'SEQUENCE'):BlockRunner(Adapter(),self.sessions).run(dict(stages=list(PICK)+['CENTER']))
