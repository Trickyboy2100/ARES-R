#!/usr/bin/env python3
"""Real ROS transport + synthetic stage adapter; no device network imports."""
import json,os,subprocess,sys,time
from pathlib import Path
import actionlib,rospy
from ares_r_manipulation_blocks.msg import RunBlockAction,RunBlockGoal
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
node=ROOT/'ros/ares_r_manipulation_blocks/scripts/run_block_node.py'
rows=json.loads((ROOT/'block_registry.json').read_text())['blocks']
row=next(r for r in rows if r['id']=='P01')
def goal(req='test',revision=None):
    return RunBlockGoal(request_id=req,block_id=row['block_id'],expected_profile_revision=revision or row['profile_revision'],onsite_observer_confirmed=True,prepared_environment_confirmed=True)
def launch(*args):return subprocess.Popen([sys.executable,str(node),'_repository:='+str(REPO),*args],env=dict(os.environ,ARES_R_OFFLINE_REPLAY='1'))
def client():
    c=actionlib.SimpleActionClient('/ares_r/run_block',RunBlockAction)
    assert c.wait_for_server(rospy.Duration(10));return c
if __name__=='__main__':
    rospy.init_node('runblock_transport_test',anonymous=True)
    count=0
    for args,case in [([], 'physical_rejected'),(['_offline_replay:=true'],'success'),(['_offline_replay:=true','_fault_stage:=VERIFY_AFTER_LIFT'],'failed_verify'),(['_offline_replay:=true','_stage_delay_s:=0.2'],'cancel_busy')]:
        p=launch(*args)
        try:
            c=client();feedback=[];c.send_goal(goal(case),feedback_cb=lambda f:feedback.append(f))
            if case=='cancel_busy':
                time.sleep(.15);other=client();other.send_goal(goal('second'));assert other.wait_for_result(rospy.Duration(5));assert other.get_result().code=='BUSY'
                count+=1;print('PASS busy_no_preemption',flush=True);c.cancel_goal()
            assert c.wait_for_result(rospy.Duration(15));r=c.get_result()
            if case=='physical_rejected':assert not r.success and r.code=='CANONICAL_ADAPTER_NOT_RELEASED'
            elif case=='success':assert r.success and r.terminal_state=='HELD_CONFIRMED' and feedback and not r.transport_handoff_ready
            elif case=='failed_verify':assert not r.success and r.terminal_state=='FAULT'
            else:assert not r.success and r.terminal_state=='STOPPED'
            count+=1;print('PASS',case,r.terminal_state,flush=True)
        finally:p.terminate();p.wait(timeout=10);time.sleep(.4)
    print('ROS_TRANSPORT_CASES_PASS',count)
