#!/usr/bin/env python3
import json,threading,time,subprocess,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import rospy,actionlib
from ares_r_center_restore.msg import CenterRestoreAction,CenterRestoreGoal
D={'mode':'ok','state':'IDLE','run_id':'','reads':0,'starts':0,'result':{}}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,x,code=200):self.send_response(code);self.end_headers();self.wfile.write(json.dumps(x).encode())
    def do_POST(self):
        b=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('start'):
            D['starts']+=1
            if D['mode']=='lost':self.send({'error':'simulated lost START acknowledgement'},500);return
            D.update(state='RUNNING',run_id=b['request_id'],reads=0,result={});self.send(D)
        else:D.update(state='STOPPED',result={'terminal_state':'STOPPED'});self.send(D)
    def do_GET(self):
        D['reads']+=1
        if D['reads']>2 and D['mode'] not in ('cancel','busy') and D['state']=='RUNNING':
            ok=D['mode']=='ok';partial=D['mode']=='restore_fail'
            D.update(state='SUCCEEDED' if ok else 'FAULT',result=dict(success=ok,return_to_saved_pose_verified=ok,terminal_state='CENTER_RESTORE_COMPLETED' if ok else 'CENTER_ARRIVED_RESTORE_FAILED' if partial else 'FAULT',error_code='' if ok else 'INJECTED_'+D['mode'],legs={'center_leg':{'arrival':{'passed':ok or partial}},'restore_leg':{'arrival':{'passed':ok}}}))
        self.send(D)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
    node=Path(__file__).resolve().parents[1]/'ros/ares_r_center_restore/scripts/center_restore_node.py'
    p=subprocess.Popen([sys.executable,str(node),'__name:=center_restore_fake_bridge','_base_url:=http://127.0.0.1:'+str(server.server_port)])
    try:
        rospy.init_node('center_restore_fake_transport_test',anonymous=True)
        c=actionlib.SimpleActionClient('/ares_r/center_restore',CenterRestoreAction)
        assert c.wait_for_server(rospy.Duration(10))
        for mode in ['reject','ok','center_fail','restore_fail','cancel','lost']:
            D.update(mode=mode,state='IDLE',starts=0,reads=0,result={})
            g=CenterRestoreGoal(request_id='fake-'+mode,target_mode='CAPTURE_START',empty_hand_confirmed=mode!='reject',onsite_observer_confirmed=True,prepared_environment_confirmed=True)
            c.send_goal(g)
            if mode=='cancel':time.sleep(.4);c.cancel_goal()
            assert c.wait_for_result(rospy.Duration(10)),mode
            z=c.get_result();assert z.success==(mode=='ok'),(mode,z)
            if mode=='reject':assert D['starts']==0
            if mode=='restore_fail':assert z.terminal_state=='CENTER_ARRIVED_RESTORE_FAILED'
            if mode=='lost':assert D['starts']==1 and z.terminal_state=='UNCERTAIN'
            print('PASS_ROS',mode,z.terminal_state,z.error_code,flush=True)
        # Concurrent goal must reject rather than preempt the active motion.
        D.update(mode='busy',state='IDLE',starts=0,reads=0,result={})
        g=CenterRestoreGoal(request_id='first',target_mode='CAPTURE_START',empty_hand_confirmed=True,onsite_observer_confirmed=True,prepared_environment_confirmed=True)
        c.send_goal(g);time.sleep(.4)
        other=actionlib.SimpleActionClient('/ares_r/center_restore',CenterRestoreAction);other.wait_for_server()
        g.request_id='second';other.send_goal(g);assert other.wait_for_result(rospy.Duration(5));assert other.get_result().error_code=='BUSY'
        c.cancel_goal();assert c.wait_for_result(rospy.Duration(5));print('PASS_ROS extra_goal_BUSY_no_preemption')
    finally:p.terminate();p.wait(timeout=10);server.shutdown()
