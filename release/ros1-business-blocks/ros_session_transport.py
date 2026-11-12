#!/usr/bin/env python3
"""Cross-Goal/session/restart ROS tests using the explicit synthetic adapter."""
import os,json,subprocess,sys,tempfile,time
from pathlib import Path
import rospy,actionlib
from ares_r_manipulation_blocks.msg import RunBlockAction,RunBlockGoal
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
rows=json.loads((ROOT/'block_registry.json').read_text())['blocks']
def goal(short,request,session=''):
    row=next(r for r in rows if r['id']==short)
    return RunBlockGoal(request_id=request,block_id=row['block_id'],expected_profile_revision=row['profile_revision'],payload_session_id=session,onsite_observer_confirmed=True,prepared_environment_confirmed=True)
def call(c,g):
    c.send_goal(g);assert c.wait_for_result(rospy.Duration(10));time.sleep(.1);return c.get_result()
def start(state):
    p=subprocess.Popen([sys.executable,str(ROOT/'ros/ares_r_manipulation_blocks/scripts/run_block_node.py'),'_offline_replay:=true','_fault_stage:=NONE','_offline_state_dir:='+str(state),'_repository:='+str(REPO)],env=dict(os.environ,ARES_R_OFFLINE_REPLAY='1'))
    c=actionlib.SimpleActionClient('/ares_r/run_block',RunBlockAction);assert c.wait_for_server(rospy.Duration(10));return p,c
if __name__=='__main__':
    rospy.init_node('runblock_session_test',anonymous=True)
    with tempfile.TemporaryDirectory(prefix='ares-session-') as state:
        p,c=start(state)
        try:
            a=call(c,goal('P01','pick-one'));assert a.success and a.payload_session_id
            again=call(c,goal('P01','pick-one'));assert again.run_id==a.run_id and again.payload_session_id==a.payload_session_id
            print('PASS terminal_request_dedupe',flush=True)
        finally:p.terminate();p.wait();time.sleep(.5)
        p,c=start(state)
        try:
            again=call(c,goal('P01','pick-one'));assert again.run_id==a.run_id
            print('PASS restart_terminal_no_redispatch',flush=True)
            b=call(c,goal('L01','place-one',a.payload_session_id));assert b.success and b.payload_state=='RELEASED_CONFIRMED'
            print('PASS pick_place_cross_goal_persistent_session',flush=True)
            again=call(c,goal('L01','place-one',a.payload_session_id));assert again.run_id==b.run_id
            print('PASS release_not_repeated',flush=True)
        finally:p.terminate();p.wait()
    print('ROS_SESSION_CASES_PASS 4')
