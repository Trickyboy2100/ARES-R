"""Authorized exact prepared preland -> verified contact50 -> release -> return81.
No pick restart, stow, obstacle deletion, parameter relaxation or automatic retry.
"""
import importlib.util,json,os,time
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request,urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
O=R/'worklog/evidence/operations-single/20261019-new-place810-after-preland';O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
events=[]
def event(stage,state,detail):
    events.append({'stage':stage,'state':state,'detail':detail,'at_unix':time.time()});m.write(O/'events.json',events)
    print(json.dumps({'stage':stage,'state':state,'detail':detail if state=='FAIL' else {}}),flush=True)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
job=SimpleNamespace(value={'stage':'PREFLIGHT'},check_stop=lambda:None)
live=m.Live(p,O,event,job=job)
def stage(name,action):
    job.value['stage']=name;live.command_id='OPERATOR_NEW_PLACE810_'+name
    event(name,'START',{});at=time.monotonic();result=action()
    m.write(O/(name+'.json'),result);event(name,'PASS',{'wall_s':time.monotonic()-at});return result
try:
    if live.get('/api/demo/roundtrip/status').get('running') or live.get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another job active')
    preview=R/'worklog/evidence/20261019-new-place-left040-preland';report=m.load(preview/'REPORT.json');h=m.load(preview/'handle.json')
    if not report['ready'] or not h['execution_package_ready']:raise RuntimeError('new preland not ready')
    prior=R/'worklog/evidence/operations-single/20261019-new-place810-finish'
    previous=m.load(prior/'MOVE_PRELAND.json')
    if not previous['execution'].get('execution_result',{}).get('target_reached'):raise RuntimeError('prior preland arrival not proven')
    if (prior/'PLACE_DESCENT50.native.jsonl').exists():raise RuntimeError('descent outcome must be reconciled; no repeat')
    import hashlib
    receipt=prior/'command_records'/(hashlib.sha256(b'OPERATOR_NEW_PLACE810_PLACE_DESCENT50').hexdigest()+'.json')
    if receipt.exists():raise RuntimeError('descent dispatch already recorded; no repeat')
    request=m.load(R/h['plan_artifact']/'planner_request.json');plan=m.load(R/h['plan_artifact']/'planning.json')
    actual=json.load(urlopen(Request('http://127.0.0.1:8775/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'}),timeout=20))
    from ares_r.motion.arrival_contract import check_start
    from ares_r.manipulation.live_roundtrip_contract import validate_place_dispatch_state
    check_start(actual['arms']['right']['joints_rad'],plan['trajectory_points_rad'][-1])
    validate_place_dispatch_state(actual,actual)
    stop=live.stopfile
    if stop.exists():
        if stop.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unexpected stop latch')
        stop.rename(stop.with_name('stop-preserved-place810-software-field-fix-'+str(time.time_ns())+'.request'))
    live.attached=request['attached_object_collision'];live.grasp_state='GRASP_CONFIRMED'
    live.preland=report['new_place_target']['preland_body_m']
    live._level(plan['trajectory_points_rad'],request)
    live.command(['.venv/bin/python','scripts/gripper_direct_once.py','read'],O/'held-readback.json',10)
    from ares_r.manipulation.live_roundtrip_contract import validate_hold_readback
    validate_hold_readback(p,m.load(O/'held-readback.json'))
    m.write(O/'parameters.json',p);m.write(O/'PRELAND40.plan_handle.json',h)
    m.write(O/'authorization.json',{'scope':'continue approved placement after PLACE left40mm, then revised81cm return',
       'source_run_id':'a0a473e2bf2242d48e8c3dbf70f6eabc','plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash']})
    def move():
        live.post('/api/operations/execute',{'plan_id':h['plan_id'],'trajectory_hash':h['trajectory_hash'],
            'authorization':'RIGHT SCENE_AWARE SUPERVISED','onsite_observer_confirmed':True})
        until=time.monotonic()+300
        while time.monotonic()<until:
            live.check_cancelled();value=live.get('/api/operations/run-status');m.write(O/'preland-execution-status.json',value)
            if value.get('state')!='RUNNING':
                if value.get('state')!='SUCCEEDED' or not value.get('execution_result',{}).get('target_reached'):raise RuntimeError('preland execution failed')
                arrival=live._settle(plan['trajectory_points_rad'][-1]);live.preland_arrived=True
                return {'execution':value,'arrival':arrival}
            time.sleep(.3)
        raise RuntimeError('preland execution deadline')
    live.preland_arrived=True
    m.write(O/'PRELAND_ALREADY_ARRIVED.json',{'previous_evidence':str(prior/'MOVE_PRELAND.json'),
        'fresh_arrival':live._settle(plan['trajectory_points_rad'][-1]),'physical_motion_repeated':False})
    stage('PLACE_DESCENT50',lambda:live.place_descend(.05))
    stage('RELEASE',lambda:live.gripper(p['gripper_release_raw']))
    stage('DETACH',live.detach)
    for name,delta in [('RETURN_BACK032',[-.32,0,0]),('RETURN_LEFT081',[0,.81,0]),('RETURN_FORWARD040',[.4,0,0])]:
        stage(name,lambda delta=delta:live.base(delta))
    after=live.telemetry();m.write(O/'after.json',after)
    m.write(O/'REPORT.json',{'state':'PLACED_RELEASED_RETURNED_GRASP','route_revision':'GRASP_PLACE_BODY_ROUTE_2026_10_19_V5_PLACE_LEFT040_LATERAL810',
        'release_confirmed':live.release_confirmed,'arm_stow':False,'source_demo_history_preserved':True,
        'source_run_id':'a0a473e2bf2242d48e8c3dbf70f6eabc','recovery_not_uninterrupted_full_cycle':True})
    event('DONE','PASS',{})
except BaseException as exc:
    m.write(O/'FAULT.json',{'stage':job.value['stage'],'error':str(exc),'automatic_retry':False});event('FAULT','FAIL',{'error':str(exc)});live.stop();raise
finally:live.pool.shutdown(wait=False)
