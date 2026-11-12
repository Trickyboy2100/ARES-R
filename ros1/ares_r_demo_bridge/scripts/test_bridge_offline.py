#!/usr/bin/env python3
"""Actual ROS action transport against a fake HTTP server; never accesses hardware."""
import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import rospy
import actionlib
from ares_r_demo_bridge.msg import ReturnCenterAction, ReturnCenterGoal

data = dict(mode='success', state='IDLE', running=False, run_id='', starts=0, stops=0)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, value, code=200):
        payload = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.reply(data)
        if data['running'] and data['mode'] in ('success', 'fault'):
            data.update(state='SUCCEEDED' if data['mode'] == 'success' else 'FAULT', running=False)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('/start'):
            data['starts'] += 1
            data.update(run_id=body['request_id'], state='RUNNING', running=True)
            self.reply(data)
        elif self.path.endswith('/stop'):
            data['stops'] += 1
            data.update(state='STOPPED', running=False)
            self.reply(data)


if __name__ == '__main__':
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    node = subprocess.Popen(['rosrun', 'ares_r_demo_bridge', 'return_center_node.py',
                            '_base_url:=http://127.0.0.1:%s' % http.server_port,
                            '_poll_interval_s:=0.2'])
    try:
        rospy.init_node('bridge_offline_test', anonymous=True)
        client = actionlib.SimpleActionClient('/ares_r/return_center', ReturnCenterAction)
        assert client.wait_for_server(rospy.Duration(10))
        for mode, confirmed, expected in [('reject', False, 'NOT_CONFIRMED'),
                                          ('busy', True, 'DEMO_BUSY'),
                                          ('success', True, 'SUCCEEDED'),
                                          ('fault', True, 'FAULT'),
                                          ('cancel', True, 'STOPPED')]:
            data.update(mode=mode, state='RUNNING' if mode == 'busy' else 'IDLE',
                        running=mode == 'busy', run_id='', starts=0, stops=0)
            client.send_goal(ReturnCenterGoal('offline-' + mode, confirmed, confirmed))
            if mode == 'cancel':
                end = time.monotonic() + 5
                while not data['starts'] and time.monotonic() < end:
                    time.sleep(.05)
                client.cancel_goal()
            assert client.wait_for_result(rospy.Duration(10)), mode
            result = client.get_result()
            assert result.code == expected, (mode, result)
            if mode in ('reject', 'busy'):
                assert data['starts'] == 0
            if mode == 'cancel':
                assert data['stops'] == 1
            print('PASS', mode, result.code, flush=True)
        print('5/5 OFFLINE ROS INTEGRATION PASS; fake backend only', flush=True)
    finally:
        node.terminate()
        node.wait(timeout=10)
        http.shutdown()
