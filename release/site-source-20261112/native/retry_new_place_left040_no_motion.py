"""Fresh ID3 + new-station scene + preland planning. No arm/gripper/base execution."""
import importlib.util,json,os,time
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
O=R/'worklog/evidence/20261019-new-place-left040-preland';O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
class Preview(m.Live):
    def post(self,path,body,timeout=150):
        if path not in ('/api/operations/telemetry','/api/operations/update','/api/motion/plan'):
            raise RuntimeError('preview cannot actuate '+path)
        return super().post(path,body,timeout)
events=[]
def event(stage,state,detail):
    events.append({'stage':stage,'state':state,'detail':detail,'at_unix':time.time()});m.write(O/'events.json',events)
    print(json.dumps({'stage':stage,'state':state,'detail':detail}),flush=True)
live=Preview(p,O,event);started=time.monotonic()
try:
    station=m.load(R/'worklog/evidence/base-routes/20261019-place-left040/REPORT.json')
    if station['state']!='NEW_PLACE_LEFT040_SETTLED':raise RuntimeError('new station not settled')
    if live.get('/api/demo/roundtrip/status').get('running') or live.get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another job active')
    old=m.load(R/'worklog/evidence/scene-aware-motion/PLAN_6a461e93d9544b8e8ed80cd4c686d0f5/planner_request.json')
    attached=old['attached_object_collision'];live.attached=attached
    m.write(O/'before.json',live.telemetry())
    target=live.place_target(p['slot_id'],p['preland_height_m']);m.write(O/'fresh-ID3-target.json',target)
    request={'arm':'right','position_m':live.preland.tolist(),'orientation':'EXPLICIT',
        'explicit_rotation':old['goal_candidate_metadata'][0]['rotation'],'environment_avoidance':'ON',
        'scene_policy':'FORCE_RESCAN','speed_profile':p['motion_speed_profile'],
        'attached_object_geometry':attached,'attached_object_revision':attached['revision'],
        'source':'NEW_PLACE_LEFT040_FRESH_ID3_PREVIEW','request_label':'NEW_PLACE_LEFT040_PRELAND40'}
    def attempt(mode,index):
        trial=dict(request,planning_mode=mode);m.write(O/('request-'+mode+str(index)+'.json'),trial)
        try:return live.post('/api/motion/plan',trial,timeout=360)
        except Exception as exc:raise m.PlanningAttemptFailure(str(exc)) from exc
    h=m.plan_with_retries(p,attempt,event,live.check_cancelled)
    m.write(O/'handle.json',h);m.write(O/'REPORT.json',{'ready':True,'physical_arm_motion':False,
        'new_place_target':target,'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash'],
        'execution_package_ready':h.get('execution_package_ready'),'wall_s':time.monotonic()-started,
        'hard_validity':h.get('hard_validity')})
    print(json.dumps(m.load(O/'REPORT.json')),flush=True)
except BaseException as exc:
    m.write(O/'FAULT.json',{'error':str(exc),'physical_arm_motion':False,'wall_s':time.monotonic()-started});raise
finally:live.pool.shutdown(wait=False)
