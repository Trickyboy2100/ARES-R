#!/usr/bin/env python3
"""RunBlock ABI endpoint. Physical goals remain explicitly unavailable.

The opt-in offline replay mode performs no socket/SDK/native operations.
"""
import json,os
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
        self.offline=(rospy.get_param('~offline_replay',False) is True and os.environ.get('ARES_R_OFFLINE_REPLAY')=='1')
        self.lock=threading.Lock();self.owner=None;self.cancelled=threading.Event()
        self.server=actionlib.ActionServer('/ares_r/run_block',RunBlockAction,self.goal,self.cancel,auto_start=False)
        if self.offline:
            root=rospy.get_param('~contract_root',str(Path(__file__).resolve().parents[3]))
            sys.path.insert(0,root)
            from blocks.contracts import prepare
            self.prepare=prepare
            from blocks.replay_jobs import ReplayJobs
            self.Jobs=ReplayJobs
            self.state_dir=Path(rospy.get_param('~offline_state_dir',tempfile.mkdtemp(prefix='ares-ros-offline-')))
            self.state_dir.mkdir(parents=True,exist_ok=True)
            store=self.Jobs(self.state_dir/'jobs.sqlite')
            try:store.recover_restart()
            finally:store.close()
        self.server.start()
    def goal(self,h):
        g=h.get_goal()
        if not self.offline:
            h.set_rejected(RunBlockResult(code='CANONICAL_ADAPTER_NOT_RELEASED',terminal_state='REJECTED_NO_DISPATCH'));return
        if not g.request_id or not(g.onsite_observer_confirmed and g.prepared_environment_confirmed):
            h.set_rejected(RunBlockResult(code='INVALID_OR_UNCONFIRMED_GOAL'));return
        if not self.lock.acquire(False):
            h.set_rejected(RunBlockResult(code='BUSY'));return
        try:
            goal={k:getattr(g,k) for k in g.__slots__}
            store=self.Jobs(self.state_dir/'jobs.sqlite')
            try:
                job=store.start(goal)
                saved=store.result(job['run_id'])
            finally:store.close()
            if not job['new_job']:
                if saved:
                    h.set_accepted();result=self.result_message(saved,job['run_id'],g.block_id)
                    if saved['success']:h.set_succeeded(result)
                    elif saved['terminal_state']=='STOPPED':h.set_canceled(result)
                    else:h.set_aborted(result)
                else:h.set_rejected(RunBlockResult(code='DUPLICATE_UNCERTAIN_NO_REDISPATCH',run_id=job['run_id'],terminal_state=job['state']))
                self.lock.release();return
        except Exception as e:
            self.lock.release();h.set_rejected(RunBlockResult(code=str(e)));return
        self.owner=h;self.cancelled.clear();h.set_accepted()
        threading.Thread(target=self.run,args=(h,g,job['run_id']),daemon=True).start()
    def cancel(self,h):
        if self.owner and self.owner.get_goal_id().id==h.get_goal_id().id:self.cancelled.set()
    def result_message(self,r,run_id,block_id):
        return RunBlockResult(success=r['success'],code='OFFLINE_REPLAY_ONLY',terminal_state=r['terminal_state'],
               run_id=run_id,block_id=block_id,payload_session_id=r.get('payload_session_id',''),
               payload_state=r.get('payload_state','UNKNOWN'),transport_handoff_ready=False,details_json=json.dumps(r))
    def persist_result(self,run_id,r):
        store=self.Jobs(self.state_dir/'jobs.sqlite')
        try:store.finish(run_id,'SUCCEEDED' if r['success'] else r['terminal_state'] if r['terminal_state'] in ('FAULT','STOPPED') else 'UNCERTAIN',r)
        finally:store.close()
    def run(self,h,g,run_id):
        # Persistent offline request ledger; physical dispatch remains unavailable.
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
                    h.publish_feedback(RunBlockFeedback(run_id=run_id,stage=stage,state='OFFLINE_REPLAY',elapsed_s=time.monotonic()-started))
                    return dict(verified=stage!=fail,observed_monotonic_s=time.monotonic(),
                                object_type='synthetic-sieve',tool_revision='synthetic-tool',geometry_revision='synthetic-geometry')
                def stop(self):return True
            sessions=PayloadSessions(self.state_dir/'payloads.sqlite')
            try:r=BlockRunner(Adapter(),sessions).run(plan,payload_session_id=g.payload_session_id,cancelled=cancel.is_set)
            finally:sessions.close()
            self.persist_result(run_id,r)
            result=self.result_message(r,run_id,g.block_id)
            if r['success']:h.set_succeeded(result)
            elif r['terminal_state']=='STOPPED':h.set_canceled(result)
            else:h.set_aborted(result)
        except Exception as e:
            r=dict(success=False,terminal_state='UNCERTAIN',error=str(e))
            self.persist_result(run_id,r)
            h.set_aborted(RunBlockResult(code=str(e),terminal_state='UNCERTAIN',run_id=run_id))
        finally:self.owner=None;self.lock.release()

if __name__=='__main__':
    rospy.init_node('ares_r_run_block_offline_contract');Node();rospy.spin()
