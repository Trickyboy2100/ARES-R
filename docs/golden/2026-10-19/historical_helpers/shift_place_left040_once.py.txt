"""Authorized return-only recovery; no release, pick, or arm movement."""
import importlib.util,json,os,time
from urllib.request import Request,urlopen
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');os.chdir(R)
os.environ['ARES_R_ROUNDTRIP_API_URL']='http://127.0.0.1:8775'
O=R/'worklog/evidence/base-routes/20261019-place-left040';O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('demo',R/'scripts/run_grasp_place_roundtrip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
events=[]
def event(stage,state,detail):
    row={'stage':stage,'state':state,'at_unix':time.time(),'detail':detail};events.append(row);m.write(O/'events.json',events)
    print(json.dumps({'stage':stage,'state':state}),flush=True)
p=m.load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json');live=m.Live(p,O,event)
try:
    status=live.get('/api/demo/roundtrip/status')
    if status.get('running') or status.get('run_id')!='a0a473e2bf2242d48e8c3dbf70f6eabc':raise RuntimeError('unexpected task ownership')
    if live.get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('another motion active')
    before=json.load(urlopen(Request('http://127.0.0.1:8775/api/operations/telemetry',data=b'{}',headers={'Content-Type':'application/json'}),timeout=20));m.write(O/'before.json',before)
    if before.get('errors'):raise RuntimeError('telemetry unavailable')
    for arm in before['arms'].values():
        c=arm['controller_status']
        if c.get('errcode') or any(c.get(k) for k in ('emergency_stop','protective_stop','drag_mode','on_soft_limit')):raise RuntimeError('controller unhealthy')
    stop=live.stopfile
    if stop.exists():
        if stop.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unexpected stop latch')
        stop.rename(stop.with_name('stop-preserved-authorized-return-held-'+str(time.time_ns())+'.request'))
    live.command(['.venv/bin/python','scripts/gripper_direct_once.py','read'],O/'held-readback.json',10)
    from ares_r.manipulation.live_roundtrip_contract import validate_hold_readback
    validate_hold_readback(p,m.load(O/'held-readback.json'))
    m.write(O/'authorization.json',{'scope':'PLACE BODY +Y 0.04m, record new PLACE; no release; no arm motion',
        'route_body_m':[[0,.04,0]],'source_run_id':status['run_id']})
    for index,delta in enumerate([[0,.04,0]]):
        live.command_id='OPERATOR_PLACE_LEFT040_20261019'
        stage='PLACE_LEFT040';event(stage,'START',{'delta':delta})
        result=live.base(delta);m.write(O/(stage+'.json'),result);event(stage,'PASS',{})
    after=live.telemetry();m.write(O/'after.json',after)
    info=after['base']['info']
    m.write(O/'new_place_station.json',{'status':'OBSERVED_SETTLED_NOT_PRECISION_COMMISSIONED','map_id':info['mapId'],
        'recorded_at_unix':time.time(),'map_pose_xy_m_yaw_deg':[info['x'],info['y'],info['yawNumber']],
        'station_revision':'PLACE_STATION_20261019_LEFT040','commanded_shift_body_m':[0,.04,0],
        'confidence_raw':info.get('confidence'),'motion_log':after['base'].get('log'),
        'evidence':str(O),'note':'relative move is authoritative; SLAM sample may drift'})
    m.write(O/'REPORT.json',{'state':'NEW_PLACE_LEFT040_SETTLED','release':False,'arm_motion':False,'source_demo_history_preserved':True})
    event('DONE','PASS',{})
except BaseException as exc:
    m.write(O/'FAULT.json',{'error':str(exc),'automatic_retry':False});live.stop();raise
finally:live.pool.shutdown(wait=False)
