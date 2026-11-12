"""New operator approval: prepared PLACE recovery only, exact once per stage."""
import importlib.util,json,os,time,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
P=R/'worklog/evidence/20261019-v17-payload160x100-place-preparation-v2'
O=R/'worklog/evidence/operations-single/20261019-v17-approved-place160-return';O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
events=[]
def event(stage,state,detail):
    events.append(dict(stage=stage,state=state,detail=detail,at_unix=time.time()));m.write(O/'events.json',events)
    print(json.dumps({'stage':stage,'state':state,'detail':str(detail)[:1200]}),flush=True)
def check_stop():
    if (O/'stop.request').exists():raise RuntimeError('OPERATOR_RECOVERY_STOP_REQUESTED')
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
job=SimpleNamespace(value={'stage':'PREFLIGHT'},check_stop=check_stop)
live=m.Live(p,O,event,job=job)
def stage(name,fn):
    job.value['stage']=name;live.command_id='V17_APPROVED_PLACE160_'+name
    receipt=live._record_path(live.command_id)
    if receipt.exists():raise RuntimeError('stage already dispatched: '+name)
    event(name,'START',{});started=time.monotonic();result=fn()
    m.write(O/(name+'.json'),result);event(name,'PASS',{'wall_s':time.monotonic()-started});return result
try:
    status=live.get('/api/demo/roundtrip/status')
    if status.get('run_id')!='af491998a03e4ecaaa524a3504583889' or status.get('running') or status.get('stage')!='MOVE_PRELAND':raise RuntimeError('unexpected original job')
    if live.get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another motion active')
    prepared=m.load(P/'prepared-placement-manifest.json');core=dict(prepared);sha=core.pop('manifest_sha256')
    if hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=sha:raise RuntimeError('prepared manifest changed')
    for name,want in prepared['files_sha256'].items():
        if hashlib.sha256((R/name).read_bytes()).hexdigest()!=want:raise RuntimeError('prepared artifact changed: '+name)
    # Telemetry is read before retiring ONLY the recognized old software stop.
    from urllib.request import Request,urlopen
    actual=json.load(urlopen(Request('http://127.0.0.1:8775/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'}),timeout=20))
    from ares_r.manipulation.live_roundtrip_contract import validate_place_dispatch_state,validate_hold_readback
    from ares_r.motion.arrival_contract import check_start
    from ares_r.motion.live_state import base_stationarity
    validate_place_dispatch_state(actual,m.load(P/'before.json'))
    check_start(actual['arms']['right']['joints_rad'],prepared['actual_start_joints_rad'])
    if live.get('/api/scene/status')['base_pose_revision']!=prepared['base_pose_revision']:raise RuntimeError('base revision changed since preview')
    if not base_stationarity(live.config)['stationary']:raise RuntimeError('base not stationary')
    m.write(O/'authorization.json',{'source':'operator:确认，开始','scope':'approved 160x100 payload PLACE descent/release/return only',
        'at_unix':time.time(),'source_run_id':status['run_id'],'source_manifest_sha256':sha,'no_pick_restart':True,
        'refresh_expired_candidate_with_same_goal_and_model':True,'controller_protections_unchanged':True,'initial_telemetry':actual})
    if live.stopfile.exists():
        if live.stopfile.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unrecognized software stop; not cleared')
        live.stopfile.rename(live.stopfile.with_name('stop-preserved-v17-approved-place160-'+str(time.time_ns())+'.request'))
    live.attached=m.load(P/'attachment.json');live.grasp_state='GRASP_CONFIRMED'
    live.command(['.venv/bin/python','scripts/gripper_direct_once.py','read'],O/'hold-readback.json',10)
    validate_hold_readback(p,m.load(O/'hold-readback.json'))
    original_report=m.load(P/'REPORT.json');h=m.load(P/'handle.json')
    new_target=live.place_target(p['slot_id'],p['preland_height_m']);m.write(O/'fresh-ID3-target.json',new_target)
    if np.linalg.norm(np.asarray(new_target['preland_body_m'])-original_report['target']['preland_body_m'])>.003:
        raise RuntimeError('approved placement target changed by more than3mm')
    live.preland=np.asarray(new_target['preland_body_m'])
    # Fresh scene, fresh plan/candidate. No expiry extension or old lease reuse.
    request=dict(m.load(P/'request-1.json'),position_m=live.preland.tolist(),scene_policy='FORCE_RESCAN',
       source='V17_AUTHORIZED_PLACE_RECOVERY_REFRESH',request_label='APPROVED_PLACE160_REFRESH')
    def attempt(mode,index):
        try:return live.post('/api/motion/plan',dict(request,planning_mode=mode),timeout=360)
        except Exception as exc:raise m.PlanningAttemptFailure(str(exc)) from exc
    h=stage('REFRESH_PLAN',lambda:m.plan_with_retries(p,attempt,event,live.check_cancelled))
    if not h.get('execution_package_ready'):raise RuntimeError('fresh native package unavailable')
    req=m.load(R/h['plan_artifact']/'planner_request.json');plan=m.load(R/h['plan_artifact']/'planning.json')
    m.write(O/'level-proof.json',live._level(plan['trajectory_points_rad'],req))
    # Predict the actual contact stage before moving the arm into preland.
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    from ares_r.manipulation.demo_place_contact import build_descent_points,validate
    ik=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp'])
    down=build_descent_points(ik,plan['trajectory_points_rad'][-1],.05)
    m.write(O/'pre_dispatch_descent_proof.json',validate(down,req,ik,new_target['slot_body_m'],p))
    m.write(O/'PRELAND40.plan_handle.json',h);m.write(O/'parameters.json',p)
    def move():
        live.post('/api/operations/execute',{'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash'],
          'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True})
        until=time.monotonic()+300
        while time.monotonic()<until:
            live.check_cancelled();value=live.get('/api/operations/run-status');m.write(O/'preland-execution-status.json',value)
            if value.get('state')!='RUNNING':
                if value.get('state')!='SUCCEEDED' or not value.get('execution_result',{}).get('target_reached'):raise RuntimeError('preland motion did not confirm arrival: '+str(value))
                arrival=live._settle(plan['trajectory_points_rad'][-1]);live.preland_arrived=True
                return {'execution':value,'arrival':arrival}
            time.sleep(.3)
        raise RuntimeError('preland motion deadline')
    stage('MOVE_PRELAND',move)
    stage('PLACE_DESCENT50',lambda:live.place_descend(.05))
    stage('RELEASE',lambda:live.gripper(p['gripper_release_raw']))
    stage('DETACH',live.detach)
    route=m.load(R/p['base_route'])
    for name,delta in [('RETURN_BACK032',[-.32,0,0]),('RETURN_LEFT081',[0,.81,0]),('RETURN_FORWARD040',[.4,0,0])]:
        stage(name,lambda delta=delta:live.base(delta))
    m.write(O/'after.json',live.telemetry())
    m.write(O/'REPORT.json',{'state':'PLACED_RELEASED_RETURNED_GRASP','source_run_id':status['run_id'],
      'release_confirmed':live.release_confirmed,'descent_arrived':live.place_descent_arrived,'arm_stow':False,
      'route_revision':route['revision'],'source_fault_history_preserved':True,
      'recovery_not_uninterrupted_full_cycle':True,'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash']})
    event('DONE','PASS',m.load(O/'REPORT.json'))
except BaseException as exc:
    m.write(O/'FAULT.json',{'stage':job.value['stage'],'error':str(exc),'automatic_retry':False})
    event('FAULT','FAIL',{'error':str(exc)});live.stop();raise
finally:live.pool.shutdown(wait=False)
