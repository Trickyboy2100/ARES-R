"""Bounded frozen-request CPU IK diagnostic, no network/SDK/planner execution."""
import json,time,math
from pathlib import Path
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792382763337808664/observer'
out=[]
for name in ('PLAN_edf4064e4277409ea56dbb940e98db68','PLAN_8ff85a1188aa4216aed2239b5368ddd2','PLAN_b7e86c32ab4a43d286623f8cfd7d4476'):
    req=json.loads((R/'worklog/evidence/scene-aware-motion'/name/'planner_request.json').read_text())
    solver=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp'])
    rows=[]
    for i,meta in enumerate(req.get('goal_candidate_metadata') or []):
        at=time.monotonic();q=solver.solve_diagnostic(req['runtime_motion_goal']['position_m'],meta['rotation'],req['start_rad'])
        rows.append({'index':i,'metadata':meta,'position_error_mm':q.position_error_m*1000,
          'orientation_error_deg':math.degrees(q.orientation_error_rad),'wall_s':time.monotonic()-at,
          'passes_unchanged_ik_contract':q.position_error_m<=.0015 and q.orientation_error_rad<=math.radians(.6),
          'closest_candidate_joints_rad':list(q.joints_rad),
          'joint_margin_rad':float(np.min(np.minimum(np.asarray(q.joints_rad)-solver.lower,solver.upper-np.asarray(q.joints_rad))))})
    out.append({'plan':name,'target':req['runtime_motion_goal'],'orientation_lock':req.get('orientation_lock'),
      'attempted_seeds_per_orientation':1,'start_rad':req['start_rad'],'candidates':rows,
      'physical_execution':False,'curobo_called':False})
(O/'409-frozen-ik-diagnostic.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
