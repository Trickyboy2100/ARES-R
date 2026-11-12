"""Exercise the real descent stage with an execution-intercepting HTTP allowlist."""
import importlib.util,json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/('worklog/evidence/2026-10-19-descend50-planning-only-'+str(time.time_ns()));O.mkdir(parents=True)
spec=importlib.util.spec_from_file_location('descent_live_preview',R/'scripts/run_grasp_place_roundtrip.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PreviewComplete(Exception):pass
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=10))
def post(path,body,timeout=150):
    if path=='/api/operations/execute':
        (O/'approved-preview-not-executed.json').write_text(json.dumps(body,indent=2));raise PreviewComplete()
    if path not in ('/api/motion/plan','/api/operations/telemetry'):raise RuntimeError('forbidden physical/mutation endpoint '+path)
    req=Request('http://127.0.0.1:8775'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:return json.load(urlopen(req,timeout=timeout))
    except HTTPError as e:raise RuntimeError('HTTP '+str(e.code)+': '+e.read().decode(errors='replace')) from e
if get('/api/demo/roundtrip/status').get('running') or get('/api/operations/run-status').get('state')=='RUNNING':raise RuntimeError('physical job active')
live=object.__new__(module.Live);live.p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
live.config=json.loads((R/'config/system.json').read_text());live.out=O;live.preland_arrived=True;live.place_descent_arrived=False
pkg=next((R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792382763337808664').glob('pick_attempt_2_QUALITY_*/package/first_pick_execution_package.json'))
live.attached=json.loads(pkg.read_text())['coarse_attached_object_collision']
live.post=post;live.get=get;live.check_cancelled=lambda:None
events=[]
def event(*args):
    events.append(args);(O/'events.json').write_text(json.dumps(events,indent=2))
live.event=event
start=time.monotonic()
try:
    live.place_descend(.05)
    raise RuntimeError('preview must never complete physical arrival')
except PreviewComplete:
    result={'result':'PLANNING_AND_BODY_Z_GATE_PASS','physical_execution':False,'release_sent':False,'wall_s':time.monotonic()-start}
except Exception as e:
    result={'result':'PLANNING_REJECTED','error':str(e),'physical_execution':False,'release_sent':False,'wall_s':time.monotonic()-start}
(O/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(result,report=str(O/'REPORT.json'))))
