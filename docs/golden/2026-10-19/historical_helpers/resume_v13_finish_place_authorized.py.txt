"""Resume this exact stopped Demo after explicit operator authorization."""
import json,time,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
R=Path('/home/yikun/ARES-R-RC1-20261019');U='http://127.0.0.1:8775'
def get(p):return json.load(urlopen(U+p,timeout=20))
def post(p,v):return json.load(urlopen(Request(U+p,data=json.dumps(v).encode(),headers={'Content-Type':'application/json'}),timeout=30))
s=get('/api/demo/roundtrip/status')
if s.get('run_id')!='a0a473e2bf2242d48e8c3dbf70f6eabc' or s.get('running') or s.get('stage')!='MOVE_PRELAND':
    raise RuntimeError('unexpected job; no resume')
t=post('/api/operations/telemetry',{})
if t.get('errors'):raise RuntimeError('telemetry unavailable')
for arm in t['arms'].values():
    c=arm['controller_status']
    if c.get('errcode') or any(c.get(k) for k in ('emergency_stop','protective_stop','drag_mode','on_soft_limit')):
        raise RuntimeError('controller not healthy; do not reset protection')
out=Path(s['run_dir'])/('authorized-resume-'+str(time.time_ns()))
out.mkdir()
(out/'authorization.json').write_text(json.dumps({'at_unix':time.time(),'source':'operator:恢复运动，回到GRASP位并且将右臂返回center位',
    'scope':'finish pending place/release/return; center after completion','no_pick_restart':True,'telemetry':t},indent=2))
job=json.loads((Path(s['run_dir'])/'job.json').read_text())
expected=job['completed'][-1]['snapshot']['telemetry']
auth={'operator_confirmed_no_physical_base_motion':True,'source':'operator:底盘没动过',
      'run_id':s['run_id'],'base_pose_revision':get('/api/scene/status')['base_pose_revision'],
      'expected_telemetry_sha256':hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
      'expires_at_unix':time.time()+900,'requires_fresh_ID3_and_scene':True}
with (Path(s['run_dir'])/'stationary-base-reconciliation-authorization.json').open('x') as f:json.dump(auth,f,indent=2)
stop=R/'worklog/runtime/right_arm_grasp_place_roundtrip_v1/stop.request'
if stop.exists():
    if stop.read_text().strip()!='CANONICAL_OPERATOR_STOP':raise RuntimeError('unexpected stop latch')
    stop.rename(stop.with_name('stop-preserved-authorized-place-resume-'+str(time.time_ns())+'.request'))
result=post('/api/demo/roundtrip/resume',{'run_id':s['run_id'],'authorization':'RIGHT GRASP PLACE ROUNDTRIP','onsite_observer_confirmed':True})
(out/'dispatch.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
