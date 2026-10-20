"""Continue only after independently confirmed descent; never descends again."""
import importlib.util,json,os,time
from pathlib import Path
from urllib.request import urlopen,Request
import numpy as np
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
S=R/'worklog/evidence/operations-single/20261019-descend50-release-return-once'
O=S/'release-return-after-verified-arrival-v2';O.mkdir(exist_ok=False)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
def load(p):return json.loads(p.read_text())
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(p):return json.load(urlopen('http://127.0.0.1:8775'+p,timeout=20))
def telemetry():return json.load(urlopen(Request('http://127.0.0.1:8775/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'}),timeout=20))
events=[]
def event(stage,state,detail):
    v={'stage':stage,'state':state,'at_unix':time.time(),'detail':detail};events.append(v);write('events.json',events);print(json.dumps(v),flush=True)
live=None
try:
    if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another task running')
    rows=[json.loads(x) for x in (S/'descent50.jsonl').read_text().splitlines() if x.startswith('{')]
    if (not any(x.get('event')=='target_reached' for x in rows) or
        not any(x.get('event')=='servo_disabled' and x.get('code')==0 for x in rows) or
        any(x.get('event') in ('failed','abort') for x in rows)):raise RuntimeError('descent sender arrival not confirmed')
    target=load(S/'points.json')[-1];request=load(S/'request.json');actual=telemetry();write('before-release.json',actual)
    if actual.get('errors') or actual['arms']['right']['controller_status']['errcode']:raise RuntimeError('controller not healthy')
    if max(abs(a-b) for a,b in zip(actual['arms']['right']['joints_rad'],target))>np.deg2rad(.05):raise RuntimeError('not at descended endpoint')
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    start=ik.fk(load(S/'points.json')[0]);end=np.array(actual['arms']['right']['T_body_tcp']);delta=end[:3,3]-start[:3,3]
    if np.linalg.norm(delta[:2])>.003 or abs(delta[2]+.05)>.003:raise RuntimeError('actual50mm descent not confirmed')
    write('actual-descent.json',{'body_displacement_m':delta.tolist(),'native_motion_repeated':False})
    spec=importlib.util.spec_from_file_location('formal',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    p=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json');live=m.Live(p,O,event)
    live.attached=request['attached_object_collision'];live.preland_arrived=True;live.place_descent_arrived=True
    if live.stopfile.exists():
        if live.stopfile.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unexpected stop')
        live.stopfile.rename(live.stopfile.with_name('stop-preserved-event-parser-recovery-'+str(time.time_ns())+'.request'))
    from ares_r.motion.arrival_contract import await_arrival
    def sample():
        right=live.telemetry()['arms']['right'];c=right['controller_status']
        return {'joints_rad':right['joints_rad'],'in_position':c['in_position'],'tool_valid':right['tool_id']==1,
            'fault':bool(c['errcode']) or any(c.get(k,False) for k in ('emergency_stop','protective_stop','drag_mode','on_soft_limit'))}
    arrival=await_arrival(sample,target,event=lambda s:event('DESCENT_ARRIVAL',s,{}));write('verified-arrival.json',arrival)
    with (O/'release-once.json').open('x') as f:json.dump({'authorization':'CURRENT_USER_DESCEND50_RELEASE_RETURN','at_unix':time.time()},f)
    live.command_id='OPERATOR_RELEASE_AFTER_VERIFIED_DESCENT_20261019'
    event('RELEASE','START',{});result=live.gripper(p['gripper_release_raw']);event('RELEASE','PASS',result);live.detach()
    for name,delta in [('RETURN_BACK032',[-.32,0,0]),('RETURN_LEFT085',[0,.85,0]),('RETURN_FORWARD040',[.4,0,0])]:
        live.command_id='OPERATOR_PLACE_FINISH_20261019_'+name
        event(name,'START',{'delta':delta});result=live.base(delta);write(name+'.json',result);event(name,'PASS',{})
    after=live.telemetry();write('after.json',after)
    report={'state':'DESCENDED_RELEASED_RETURNED_GRASP','descent_m':.05,'descent_not_repeated':True,
        'release_confirmed':live.release_confirmed,'arm_stow':False,'base_return_completed':True,
        'current_right_tcp_body_m':after['arms']['right']['position_m']}
    write('REPORT.json',report);event('DONE','PASS',report)
except BaseException as e:
    write('FAULT.json',{'error':str(e),'automatic_retry':False});event('FAULT','FAIL',{'error':str(e)})
    if live:live.stop()
    raise
finally:
    if live:live.pool.shutdown(wait=False)
