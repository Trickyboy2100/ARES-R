"""One authorized BODY+X60mm move, no arm/gripper commands or station edits."""
import json,time
from pathlib import Path
from urllib.request import urlopen,Request
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-timing/forward60';O.mkdir(exist_ok=False)
URL='http://127.0.0.1:8775'
def get(path):return json.load(urlopen(URL+path,timeout=15))
def post(path,data,timeout=150):return json.load(urlopen(Request(URL+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=timeout))
def save(name,value):(O/name).write_text(json.dumps(value,indent=2)+'\n')
run=get('/api/operations/run-status');demo=get('/api/demo/roundtrip/status')
if run.get('state')=='RUNNING' or demo.get('running'):raise RuntimeError('another physical operation active')
before=post('/api/operations/telemetry',{});save('before.json',before)
if before.get('errors'):raise RuntimeError('live telemetry unavailable')
body=dict(x_m=.060,y_m=0.,yaw_deg=0.,linear_mps=.05,authorization='MOVE BASE',command_id='PICK_RESET_20261022_FORWARD60_ONCE')
save('dispatch-once.json',dict(body=body,operator_authorized=True,onsite_monitor_confirmed=True,at_unix=time.time(),station_registry_modified=False,route_modified=False))
at=time.monotonic()
try:
 result=post('/api/operations/base-move',body);save('result.json',dict(result=result,wall_s=time.monotonic()-at))
 if result.get('state')!='SUCCEEDED' or result.get('result',{}).get('result')!='SETTLED':raise RuntimeError('base completion not confirmed')
 after=post('/api/operations/telemetry',{});save('after.json',after)
 save('scene-status.json',get('/api/scene/status'))
 print(json.dumps(dict(state=result['state'],observer=result['result']['result'],wall_s=time.monotonic()-at,base_before=before.get('base'),base_after=after.get('base'))),flush=True)
except BaseException:
 try:save('stop.json',post('/api/operations/stop',{},15))
 except Exception:pass
 raise
