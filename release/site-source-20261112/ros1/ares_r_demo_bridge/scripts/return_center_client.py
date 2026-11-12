#!/usr/bin/env python3
import argparse
import uuid
import rospy
import actionlib
from ares_r_demo_bridge.msg import ReturnCenterAction, ReturnCenterGoal

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Confirm onsite preparation and request physical motion')
    parser.add_argument('--request-id', default='ros1-' + uuid.uuid4().hex)
    args = parser.parse_args(rospy.myargv()[1:])
    rospy.init_node('return_center_client', anonymous=True)
    client = actionlib.SimpleActionClient('/ares_r/return_center', ReturnCenterAction)
    if not client.wait_for_server(rospy.Duration(10)):
        raise SystemExit('Action server unavailable')
    goal = ReturnCenterGoal(args.request_id, args.execute, args.execute)
    client.send_goal(goal, feedback_cb=lambda f: print('state=%s stage=%s elapsed=%.1fs run=%s' %
                      (f.state, f.stage, f.elapsed_s, f.run_id), flush=True))
    try:
        client.wait_for_result()
    except KeyboardInterrupt:
        client.cancel_goal()
        print('Cancel requested; verify backend stop result')
        raise SystemExit(130)
    print(client.get_result())
    raise SystemExit(0 if client.get_result().success or
                     (not args.execute and client.get_result().code == 'NOT_CONFIRMED') else 1)
