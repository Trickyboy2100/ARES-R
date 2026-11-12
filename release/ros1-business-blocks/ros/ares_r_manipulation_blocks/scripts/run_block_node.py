#!/usr/bin/env python3
"""No-motion ABI endpoint. All execution goals explicitly rejected.

This node is intentionally not a second hardware dispatcher. The accepted U01
Action remains separate. Canonical RunBlock adapter commissioning is pending.
"""
import actionlib
import rospy
from ares_r_manipulation_blocks.msg import RunBlockAction, RunBlockResult

def reject(handle):
    goal = handle.get_goal()
    handle.set_rejected(RunBlockResult(success=False, code='CANONICAL_ADAPTER_NOT_RELEASED',
                       terminal_state='REJECTED_NO_DISPATCH', block_id=goal.block_id,
                       transport_handoff_ready=False,
                       details_json='{"physical_dispatch":false}'))

if __name__ == '__main__':
    rospy.init_node('ares_r_run_block_offline_contract')
    server = actionlib.ActionServer('/ares_r/run_block', RunBlockAction, reject,
                                  lambda h: None, auto_start=False)
    server.start()
    rospy.logwarn('RunBlock ABI preview only: physical dispatch unavailable')
    rospy.spin()
