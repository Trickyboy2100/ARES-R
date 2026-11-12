#!/usr/bin/env python3
"""RunBlock ABI endpoint. Physical goals remain explicitly unavailable.

The opt-in offline replay mode performs no socket/SDK/native operations.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import actionlib
import rospy
from ares_r_manipulation_blocks.msg import RunBlockAction,RunBlockResult,RunBlockFeedback

class Node:
    def __init__(self):
        self.offline=rospy.get_param('~offline_replay',False)
        self.lock=threading.Lock();self.owner=None;self.cancelled=threading.Event()
        self.server=actionlib.ActionServer('/ares_r/run_block',RunBlockAction,self.goal,self.cancel,auto_start=False)
        if self.offline:
            root=rospy.get_param('~contract_root',str(Path(__file__).resolve().parents[3]))
            sys.path.insert(0,root)
            from blocks.contracts import prepare
            self.prepare=prepare
        self.server.start()
    def goal(self,h):
        g=h.get_goal()
        if not self.offline:
            h.set_rejected(RunBlockResult(code='CANONICAL_ADAPTER_NOT_RELEASED',terminal_state='REJECTED_NO_DISPATCH'));return
        if not g.request_id or not(g.onsite_observer_confirmed and g.prepared_environment_confirmed):
            h.set_rejected(RunBlockResult(code='INVALID_OR_UNCONFIRMED_GOAL'));return
        if not self.lock.acquire(False):
            h.set_rejected(RunBlockResult(code='BUSY'));return
        self.owner=h;self.cancelled.clear();h.set_accepted()
        threading.Thread(target=self.run,args=(h,g),daemon=True).start()
    def cancel(self,h):
        if self.owner and self.owner.get_goal_id().id==h.get_goal_id().id:self.cancelled.set()
    def run(self,h,g):
        # Persistent dedupe is deliberately tested separately; this preview node
        # must not be used as a physical dispatcher.
        try:
            from blocks.runner import BlockRunner,PayloadSessions
            repo=Path(rospy.get_param('~repository'))
            plan=self.prepare(g.block_id,g.expected_profile_revision,repo)
            fail=rospy.get_param('~fault_stage','');delay=float(rospy.get_param('~stage_delay_s',.02))
            cancel=self.cancelled;started=time.monotonic()
            class Adapter:
                mode='OFFLINE'
                def stage(self,stage,**kwargs):
                    cancel.wait(delay)
                    h.publish_feedback(RunBlockFeedback(run_id=g.request_id,stage=stage,state='OFFLINE_REPLAY',elapsed_s=time.monotonic()-started))
                    return dict(verified=stage!=fail,observed_monotonic_s=time.monotonic(),
                                object_type='synthetic-sieve',tool_revision='synthetic-tool',geometry_revision='synthetic-geometry')
                def stop(self):return True
            with tempfile.TemporaryDirectory(prefix='ares-offline-ros-') as tmp:
                sessions=PayloadSessions(Path(tmp)/'payloads.sqlite')
                try:r=BlockRunner(Adapter(),sessions).run(plan,payload_session_id=g.payload_session_id,cancelled=cancel.is_set)
                finally:sessions.close()
            result=RunBlockResult(success=r['success'],code='OFFLINE_REPLAY_ONLY',terminal_state=r['terminal_state'],
                       run_id=g.request_id,block_id=g.block_id,payload_session_id=r.get('payload_session_id',''),
                       payload_state=r.get('payload_state','UNKNOWN'),transport_handoff_ready=False,details_json=json.dumps(r))
            if r['success']:h.set_succeeded(result)
            elif r['terminal_state']=='STOPPED':h.set_canceled(result)
            else:h.set_aborted(result)
        except Exception as e:h.set_aborted(RunBlockResult(code=str(e),terminal_state='OFFLINE_ERROR'))
        finally:self.owner=None;self.lock.release()

if __name__=='__main__':
    rospy.init_node('ares_r_run_block_offline_contract');Node();rospy.spin()
