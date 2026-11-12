import json,math,time
from pathlib import Path
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019');out=R/'worklog/evidence/operations-single/20261019-center-after-release-compensated'
requests=sorted((R/'worklog/evidence/scene-aware-motion').glob('PLAN_*/planner_request.json'),key=lambda p:p.stat().st_mtime,reverse=True)
p=next(json.loads(p.read_text()) for p in requests if 'CENTER_DEMO_MINUS10' in p.read_text()) if False else json.loads(requests[0].read_text())
goal=json.loads((out/'request.json').read_text());ik=RuntimeGoalIK(p['robot_yaml_urdf'],p['T_body_model'],p['T_link6_tcp'])
named=json.loads((R/'config/named_poses.json').read_text())['poses']['center']['arms']['right']['ik_joint_rad']
start=np.array(p['start_rad']);old=np.array(named);wrapped=old+2*np.pi*np.round((start-old)/(2*np.pi))
seeds=[start,np.clip(wrapped,ik.lower+.001,ik.upper-.001),np.clip(old,ik.lower+.001,ik.upper-.001),np.zeros(6)]
rows=[]
for seed in seeds:
    at=time.monotonic();v=ik.solve_diagnostic(goal['position_m'],goal['explicit_rotation'],seed)
    rows.append({'seed':seed.tolist(),'joints_rad':v.joints_rad,'position_error_m':v.position_error_m,'orientation_error_deg':math.degrees(v.orientation_error_rad),'s':time.monotonic()-at})
(out/'bounded-ik-diagnostic.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
