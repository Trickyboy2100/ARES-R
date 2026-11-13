#!/usr/bin/env python3
"""ROS-to-HTTP execution bridge test with a loopback-only synthetic server."""
import json
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import rospy
import actionlib
from ares_r_manipulation_blocks.msg import RunBlockAction, RunBlockGoal

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from blocks.contracts import resolve
profile=resolve('pick.scale.sieve.v1')
requests={}
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        method,args=data['method'],data['args']
        if method=='demo_console_catalog':
            result=dict(demos=[dict(alias='ros-run-P01',physical_start_enabled=True,
                                    profile_revision=profile['profile_revision'])])
        elif method=='demo_console_start':
            goal=args[0]
            if goal['request_id'] not in requests:
                requests[goal['request_id']]=dict(run_id='a'*32,state='SUCCEEDED',
                    result=dict(success=True,terminal_state='HELD_CONFIRMED',payload_session_id='synthetic-session',
                                payload_state='HELD_CONFIRMED'))
            result=requests[goal['request_id']]
        else:result={'error':'unexpected method'}
        body=json.dumps(result).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
node=subprocess.Popen([sys.executable,str(root/'ros/ares_r_manipulation_blocks/scripts/run_block_node.py'),
    '_contract_root:='+str(root),'_canonical_base_url:=http://127.0.0.1:'+str(server.server_port)])
try:
    rospy.init_node('business_canonical_transport',anonymous=True)
    client=actionlib.SimpleActionClient('/ares_r/run_block',RunBlockAction)
    assert client.wait_for_server(rospy.Duration(20))
    goal=RunBlockGoal(request_id='canonical-test',block_id=profile['block_id'],
        expected_profile_revision=profile['profile_revision'],onsite_observer_confirmed=True,
        prepared_environment_confirmed=True)
    for _ in range(2):
        client.send_goal(goal)
        assert client.wait_for_result(rospy.Duration(10))
        result=client.get_result()
        assert result.success and result.terminal_state=='HELD_CONFIRMED'
        assert result.payload_session_id=='synthetic-session'
    assert len(requests)==1
    print('ROS_CANONICAL_SYNTHETIC_HTTP_PASS 2/2; no hardware backend used')
finally:
    node.terminate();node.wait(timeout=10)
    server.shutdown();server.server_close();thread.join(timeout=5)
