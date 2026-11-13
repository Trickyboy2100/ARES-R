#!/usr/bin/env python3
"""Independent ROS task; uses unchanged canonical HTTP motion APIs."""
import os,json,time,threading,uuid,subprocess,signal
from pathlib import Path
from urllib.request import Request,urlopen
import rospy,actionlib
from ares_r_center_restore.msg import CenterRestoreAction,CenterRestoreFeedback,CenterRestoreResult
ROOT=Path('/home/yikun/ARES-R-RC1-20261019')
HERE=Path(__file__).resolve().parent

def api(path,body=None):
    req=Request('http://127.0.0.1:8775'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urlopen(req,timeout=30))

class Node:
    def __init__(self):
        self.lock=threading.Lock();self.owner=None;self.cancelled=False
        self.server=actionlib.ActionServer('/ares_r/center_restore_turbo',CenterRestoreAction,self.goal,self.cancel,auto_start=False)
        self.server.start()
    def goal(self,h):
        g=h.get_goal()
        if not all((g.onsite_observer_confirmed,g.prepared_environment_confirmed,g.empty_hand_confirmed)):
            h.set_rejected(CenterRestoreResult(error_code='NOT_CONFIRMED'));return
        if not self.lock.acquire(False):h.set_rejected(CenterRestoreResult(error_code='BUSY'));return
        self.owner=h;self.cancelled=False;h.set_accepted()
        threading.Thread(target=self.run,args=(h,g),daemon=True).start()
    def cancel(self,h):
        if self.owner and self.owner.get_goal_id().id==h.get_goal_id().id:self.cancelled=True
    def run(self,h,g):
        child=None;rid=uuid.uuid4().hex;out=ROOT/'worklog/evidence/demo01-turbo-physical'/rid
        start=time.monotonic();stop_sent=False
        try:
            status=api('/api/demo-console/status')
            if status.get('running') or status.get('state')=='RECOVERY_REQUIRED':raise RuntimeError('CANONICAL_TASK_BUSY_OR_RECOVERY_REQUIRED')
            if api('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('PHYSICAL_TASK_BUSY')
            out.mkdir(parents=True)
            goal={k:getattr(g,k) for k in ('request_id','target_mode','saved_pose_id','expected_saved_pose_sha','onsite_observer_confirmed','prepared_environment_confirmed','empty_hand_confirmed')}
            (out/'goal.json').write_text(json.dumps(goal,indent=2))
            env=dict(os.environ,ARES_R_SITE_ROOT=str(ROOT),ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',PYTHONPATH=str(ROOT/'src'))
            with (out/'run.log').open('w') as log:
                child=subprocess.Popen([str(ROOT/'.venv/bin/python'),str(HERE/'run_turbo.py'),'--goal',str(out/'goal.json'),'--output',str(out/'block'),'--execute'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                while child.poll() is None:
                    events=out/'block/events.jsonl';rows=events.read_text().splitlines() if events.exists() else []
                    row=json.loads(rows[-1]) if rows else {}
                    h.publish_feedback(CenterRestoreFeedback(row.get('stage','PREFLIGHT'),row.get('phase',''),rid,time.monotonic()-start))
                    if self.cancelled or rospy.is_shutdown():
                        if not stop_sent:
                            api('/api/operations/stop',{});os.killpg(child.pid,signal.SIGTERM);stop_sent=True
                    time.sleep(.25)
            f=out/'block/result.json';value=json.loads(f.read_text()) if f.exists() else {}
            legs=value.get('legs',{})
            ok=child.returncode==0 and value.get('success') is True and value.get('return_to_saved_pose_verified') is True
            result=CenterRestoreResult(success=ok,terminal_state=value.get('terminal_state','FAULT'),return_to_saved_pose_verified=ok,run_id=rid,center_arrival_json=json.dumps(legs.get('center_leg',{}).get('arrival')),saved_arrival_json=json.dumps(legs.get('restore_leg',{}).get('arrival')),evidence_uri=str(out),error_code=value.get('error_code','' if ok else 'TURBO_TASK_FAILED'))
            (out/'ros-result.json').write_text(json.dumps(dict(success=ok,terminal_state=result.terminal_state,run_id=rid,total_s=time.monotonic()-start,error=result.error_code),indent=2))
            if ok:h.set_succeeded(result)
            elif stop_sent:h.set_canceled(result)
            else:h.set_aborted(result)
        except BaseException as e:
            if child is not None and child.poll() is None:
                try:api('/api/operations/stop',{})
                finally:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=15)
            h.set_aborted(CenterRestoreResult(terminal_state='FAULT',run_id=rid,error_code=str(e),evidence_uri=str(out)))
        finally:self.owner=None;self.lock.release()

if __name__=='__main__':
    rospy.init_node('ares_r_center_restore_turbo');Node();rospy.spin()
