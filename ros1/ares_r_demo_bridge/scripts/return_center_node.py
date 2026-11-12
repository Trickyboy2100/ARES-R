#!/usr/bin/env python3
"""One ROS Action, one canonical backend job; no SDK, motion or retries at startup."""
import json
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import rospy
import actionlib
from ares_r_demo_bridge.msg import ReturnCenterAction, ReturnCenterFeedback, ReturnCenterResult


class Bridge:
    def __init__(self):
        self.base = rospy.get_param('~base_url', 'http://127.0.0.1:8775').rstrip('/')
        self.poll = max(0.2, float(rospy.get_param('~poll_interval_s', 1.0)))
        self.deadline = float(rospy.get_param('~job_timeout_s', 900.0))
        self.server = actionlib.SimpleActionServer('/ares_r/return_center', ReturnCenterAction,
                                                  execute_cb=self.execute, auto_start=False)
        self.server.start()
        rospy.loginfo('ReturnCenter Action ready; backend=%s; startup sends no motion', self.base)

    def api(self, path, body=None, timeout=10):
        req = Request(self.base + '/api/demo-console/' + path,
                      data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError('HTTP_%s: %s' % (exc.code, exc.read().decode(errors='replace')[-1200:]))

    def finish(self, code, message, run_id='', success=False, canceled=False):
        result = ReturnCenterResult(success, code, message, run_id)
        if success:
            self.server.set_succeeded(result)
        elif canceled:
            self.server.set_preempted(result)
        else:
            self.server.set_aborted(result)

    def execute(self, goal):
        run_id = ''
        started = time.monotonic()
        cancel_sent = False
        try:
            if not goal.onsite_observer_confirmed or not goal.prepared_environment_confirmed:
                self.finish('NOT_CONFIRMED', 'Both现场 confirmation fields must be true; no start sent')
                return
            status = self.api('status')
            if status.get('running'):
                self.finish('DEMO_BUSY', 'Canonical backend already owns a running task')
                return
            if self.server.is_preempt_requested():
                self.finish('CANCELED_BEFORE_START', 'No start sent', canceled=True)
                return
            # Never retry START after a timeout: the backend may already have accepted it.
            job = self.api('start', dict(alias='demo-0-return-center',
                           authorization='RUN demo-0-return-center',
                           onsite_observer_confirmed=True, prepared_environment_confirmed=True,
                           request_id=goal.request_id or 'ros1-' + uuid.uuid4().hex), timeout=120)
            run_id = job.get('run_id', '')
            if not run_id:
                raise RuntimeError('START returned no run_id; inspect backend before retrying')
            while not rospy.is_shutdown():
                status = self.api('status')
                if status.get('run_id') != run_id:
                    self.finish('RUN_BINDING_CHANGED', 'Backend current job changed; no foreign task stopped', run_id)
                    return
                elapsed = time.monotonic() - started
                state = status.get('state', 'UNKNOWN')
                self.server.publish_feedback(ReturnCenterFeedback(state, status.get('stage', ''), run_id, elapsed))
                if state in ('SUCCEEDED', 'FAULT', 'STOPPED', 'RECOVERY_REQUIRED'):
                    self.finish(state, str(status.get('error') or state), run_id,
                                success=state == 'SUCCEEDED', canceled=cancel_sent and state == 'STOPPED')
                    return
                if self.server.is_preempt_requested() or elapsed > self.deadline:
                    if not cancel_sent:
                        # Stop is backend-global: check ownership immediately before forwarding.
                        latest = self.api('status')
                        if latest.get('run_id') != run_id:
                            raise RuntimeError('Stop ownership changed; inspect backend')
                        self.api('stop', {}, timeout=60)
                        cancel_sent = True
                        cancel_at = time.monotonic()
                    elif time.monotonic() - cancel_at > 30:
                        raise RuntimeError('STOP_UNCONFIRMED; inspect canonical backend and physical robot')
                time.sleep(self.poll)
            raise RuntimeError('ROS shutdown; backend task may remain active; check console')
        except Exception as exc:
            self.finish('BRIDGE_ERROR', str(exc) + '; no automatic restart/retry', run_id)


if __name__ == '__main__':
    rospy.init_node('ares_r_return_center')
    Bridge()
    rospy.spin()
