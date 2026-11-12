#!/usr/bin/env python3
import json,time,threading
from urllib.request import Request,urlopen
import rospy,actionlib
from ares_r_center_restore.msg import CenterRestoreAction,CenterRestoreFeedback,CenterRestoreResult


class Node:
    def __init__(self):
        self.lock=threading.Lock();self.owner=None
        self.base=rospy.get_param('~base_url','http://127.0.0.1:8775')
        rospy.loginfo('CenterRestore canonical HTTP backend: %s',self.base)
        self.server=actionlib.ActionServer('/ares_r/center_restore',CenterRestoreAction,self.goal,self.cancel,auto_start=False)
        self.server.start()
    def api(self,path,body=None):
        with urlopen(Request(self.base+'/api/demo-console/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=130) as s:return json.load(s)
    def goal(self,h):
        g=h.get_goal()
        if not (g.onsite_observer_confirmed and g.prepared_environment_confirmed and g.empty_hand_confirmed):
            h.set_rejected(CenterRestoreResult(error_code='NOT_CONFIRMED'));return
        if not g.request_id or g.target_mode not in ('CAPTURE_START','SAVED_POSE_REF'):
            h.set_rejected(CenterRestoreResult(error_code='BAD_GOAL'));return
        if not self.lock.acquire(False):h.set_rejected(CenterRestoreResult(error_code='BUSY'));return
        self.cancelled=False;self.owner=(h,None);h.set_accepted();threading.Thread(target=self.run,args=(h,g),daemon=True).start()
    def cancel(self,h):
        # Goal handle cancellation is polled by its worker; another goal never preempts it.
        if self.owner and self.owner[0].get_goal_id().id==h.get_goal_id().id:
            self.cancelled=True
    def run(self,h,g):
        rid=None
        try:
            body={k:getattr(g,k) for k in ('request_id','target_mode','saved_pose_id','expected_saved_pose_sha','onsite_observer_confirmed','prepared_environment_confirmed','empty_hand_confirmed')}
            body.update(alias='block-01-center-restore-right',authorization='RUN block-01-center-restore-right')
            status=self.api('start',body);rid=status.get('run_id')
            if not rid:raise RuntimeError('START_UNCERTAIN_DO_NOT_RETRY')
            while not rospy.is_shutdown():
                s=self.api('status')
                if s.get('run_id')!=rid:raise RuntimeError('RUN_BINDING_CHANGED')
                h.publish_feedback(CenterRestoreFeedback(s.get('stage',''),s.get('phase',''),rid,s.get('elapsed_s',0)))
                if s.get('state') in ('SUCCEEDED','FAULT','STOPPED','RECOVERY_REQUIRED'):
                    b=s.get('result') or {};legs=b.get('legs',{})
                    result=CenterRestoreResult(success=s['state']=='SUCCEEDED' and b.get('return_to_saved_pose_verified') is True,terminal_state=b.get('terminal_state',s['state']),return_to_saved_pose_verified=b.get('return_to_saved_pose_verified',False),run_id=rid,center_arrival_json=json.dumps(legs.get('center_leg',{}).get('arrival')),saved_arrival_json=json.dumps(legs.get('restore_leg',{}).get('arrival')),evidence_uri=b.get('evidence_uri',''),error_code=b.get('error_code',s.get('error','') or ''))
                    if result.success:h.set_succeeded(result)
                    elif s['state']=='STOPPED':h.set_canceled(result)
                    else:h.set_aborted(result)
                    return
                if self.cancelled:
                    self.api('stop',{});self.cancelled=False
                time.sleep(.5)
            raise RuntimeError('ROS_SHUTDOWN_TASK_MAY_REMAIN_ACTIVE')
        except Exception as e:h.set_aborted(CenterRestoreResult(terminal_state='UNCERTAIN' if rid is None else 'FAULT',run_id=rid or '',error_code=str(e)))
        finally:self.owner=None;self.lock.release()


if __name__=='__main__':
    rospy.init_node('ares_r_center_restore');Node();rospy.spin()
