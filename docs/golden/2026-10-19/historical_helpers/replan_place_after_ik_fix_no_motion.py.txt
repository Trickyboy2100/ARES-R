"""Fresh current->same preland planning only. No execution/stop/base/gripper calls."""
import json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-place-ik3mm3deg-fresh-preflight'
O.mkdir(exist_ok=False)
def save(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def get(path):return json.load(urlopen('http://127.0.0.1:8775'+path,timeout=20))
old=json.loads((R/'worklog/evidence/scene-aware-motion/PLAN_540ca50a1888479880d64af51a3df378/planner_request.json').read_text())
if get('/api/demo/roundtrip/status').get('running'):raise RuntimeError('demo still running')
goal=old['runtime_motion_goal'];attached=old['attached_object_collision']
body={'arm':'right','position_m':goal['position_m'],'orientation':'EXPLICIT',
      'explicit_rotation':old['goal_candidate_metadata'][0]['rotation'],
      'environment_avoidance':'ON','scene_policy':'FORCE_RESCAN',
      'attached_object_geometry':attached,'attached_object_revision':attached['revision'],
      'speed_profile':'right_scene_aware_0_20','source':'IK_TOLERANCE_FIX_PLANNING_ONLY',
      'request_label':'SAME_PRELAND_AFTER_IK3MM3DEG'}
errors=[];started=time.monotonic()
for mode in ('FAST','QUALITY'):
    trial=dict(body,planning_mode=mode);save(mode+'-request.json',trial)
    try:
        req=Request('http://127.0.0.1:8775/api/motion/plan',data=json.dumps(trial).encode(),headers={'Content-Type':'application/json'})
        result=json.load(urlopen(req,timeout=360));save(mode+'-handle.json',result)
        save('REPORT.json',{'ready':True,'physical_motion':False,'handle':result,'prior_errors':errors,'wall_s':time.monotonic()-started})
        print(json.dumps({'ready':True,'mode':mode,'plan_id':result['plan_id'],'hash':result['trajectory_hash'],
              'hard_validity':result.get('hard_validity'),'wall_s':time.monotonic()-started}),flush=True)
        break
    except HTTPError as exc:
        row={'mode':mode,'code':exc.code,'body':exc.read().decode()};errors.append(row);save('errors.json',errors);print(json.dumps(row),flush=True)
else:
    save('REPORT.json',{'ready':False,'physical_motion':False,'errors':errors,'wall_s':time.monotonic()-started})
    raise RuntimeError('preland replan failed; no motion issued')
