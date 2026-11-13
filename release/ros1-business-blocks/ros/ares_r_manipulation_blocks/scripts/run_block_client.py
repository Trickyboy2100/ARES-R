#!/usr/bin/env python3
"""Explicit ROS Action client; queries are available through the catalog services."""
import argparse
import json
import actionlib
import rospy
from ares_r_manipulation_blocks.msg import RunBlockAction, RunBlockGoal


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--block',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--request-id',required=True)
    parser.add_argument('--payload-session',default='')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--onsite-observer-confirmed',action='store_true')
    parser.add_argument('--prepared-environment-confirmed',action='store_true')
    args=parser.parse_args()
    if not (args.execute and args.onsite_observer_confirmed and args.prepared_environment_confirmed):
        parser.error('execute and both confirmation flags are required')
    rospy.init_node('ares_run_block_client',anonymous=True,disable_signals=True)
    client=actionlib.SimpleActionClient('/ares_r/run_block',RunBlockAction)
    if not client.wait_for_server(rospy.Duration(10)):
        raise SystemExit('RUNBLOCK_SERVER_UNAVAILABLE')
    goal=RunBlockGoal(request_id=args.request_id,block_id=args.block,
        expected_profile_revision=args.revision,payload_session_id=args.payload_session,
        onsite_observer_confirmed=True,prepared_environment_confirmed=True)
    def show(message):
        print(json.dumps({k:getattr(message,k) for k in message.__slots__},ensure_ascii=False),flush=True)
    client.send_goal(goal,feedback_cb=show)
    try:
        while not client.wait_for_result(rospy.Duration(1)):
            pass
    except KeyboardInterrupt:
        client.cancel_goal()
        if not client.wait_for_result(rospy.Duration(30)):
            raise SystemExit('STOP_UNCONFIRMED_CHECK_CANONICAL_JOB')
    result=client.get_result()
    show(result)
    return 0 if result.success else 1

if __name__=='__main__':
    raise SystemExit(main())
