"""One fresh stationary PLACE scan/plan after 409; never dispatches motion."""
import importlib.util,json,os,time
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
O=R/('worklog/evidence/20261019-v17-place409-fresh-recheck-'+str(time.time_ns()));O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Preview(m.Live):
    def check_cancelled(self):
        # Read/scan/plan only. Preserve the stop latch; no execution endpoint exists here.
        return
    def post(self,path,body,timeout=150):
        if path not in ('/api/operations/telemetry','/api/operations/update','/api/motion/plan'):
            raise RuntimeError('no-motion recheck forbidden endpoint '+path)
        return super().post(path,body,timeout)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
live=Preview(p,O,lambda *args:None)
try:
    status=live.get('/api/demo/roundtrip/status')
    if status.get('run_id')!='af491998a03e4ecaaa524a3504583889' or status.get('running') or status.get('stage')!='MOVE_PRELAND':raise RuntimeError('unexpected run')
    m.write(O/'fault-status.json',status);m.write(O/'before.json',live.telemetry())
    old=m.load(R/'worklog/evidence/scene-aware-motion/PLAN_8a7bc97bb3f1421289fbab04dc927dff/planner_request.json')
    live.attached=old['attached_object_collision']
    target=live.place_target(p['slot_id'],p['preland_height_m']);m.write(O/'fresh-ID3-target.json',target)
    request={'arm':'right','position_m':live.preland.tolist(),'orientation':'EXPLICIT',
      'explicit_rotation':old['goal_candidate_metadata'][0]['rotation'],'environment_avoidance':'ON',
      'scene_policy':'FORCE_RESCAN','speed_profile':p['motion_speed_profile'],'planning_mode':'FAST',
      'attached_object_geometry':live.attached,'attached_object_revision':live.attached['revision'],
      'source':'V17_PLACE409_NO_MOTION_RECHECK','request_label':'V17_FRESH_PRELAND40'}
    m.write(O/'request.json',request)
    handle=live.post('/api/motion/plan',request,timeout=360);m.write(O/'handle.json',handle)
    m.write(O/'REPORT.json',{'ready':bool(handle.get('execution_package_ready')),'physical_motion':False,'handle':handle})
    print(json.dumps({'ready':handle.get('execution_package_ready'),'plan_id':handle.get('plan_id')}),flush=True)
except BaseException as exc:
    m.write(O/'FAULT.json',{'error':str(exc),'physical_motion':False});print(str(exc)[:1400],flush=True);raise
finally:live.pool.shutdown(wait=False)
