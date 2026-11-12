"""Find a diagnostic planning target without modifying the 55mm task or scene."""
import copy,json,time,hashlib
from pathlib import Path
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.independent_path_validation import validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
r=json.loads((O/'frozen-pregrasp-only-request.json').read_text());p=json.loads((O/'frozen-pregrasp-only/preparation.json').read_text())
ik=RuntimeGoalIK(r['robot_yaml_urdf'],r['T_body_model'],r['T_link6_tcp']);rows=[];selected=None
for distance in (.075,.100,.125,.150):
 for index,meta in enumerate(r['goal_candidate_metadata']):
  at=time.monotonic();xyz=np.array(p['target_body_m'])-distance*np.array(p['approach_direction_body'])
  result=ik.solve_diagnostic(xyz,np.array(meta['target_rotation_body']),np.array(r['goal_candidates_rad'][index]))
  q=list(result.joints_rad);validation=validate_dense_world([q,q],r,subdivisions=2)
  valid=result.position_error_m<=.003 and np.degrees(result.orientation_error_rad)<=3 and validation['collision_free']
  row=dict(distance_m=distance,symmetry=meta['grasp_symmetry_id'],xyz_body_m=xyz.tolist(),joints_rad=q,position_error_m=result.position_error_m,orientation_error_deg=float(np.degrees(result.orientation_error_rad)),validation=validation,valid=bool(valid),wall_s=time.monotonic()-at)
  rows.append(row);print(json.dumps({k:row[k] for k in ('distance_m','symmetry','valid','position_error_m','orientation_error_deg')}|dict(gap=validation['min_clearance_m'])),flush=True)
  if valid and selected is None:
   selected=(row,meta)
 if selected:break
(O/'diagnostic-preapproach-search.json').write_text(json.dumps(rows,indent=2)+'\n')
if selected is None:raise RuntimeError('no collision-free diagnostic preapproach target; no obstacle changes')
row,meta=selected;request=copy.deepcopy(r)
request.update(goal_rad=row['joints_rad'],goal_candidates_rad=[row['joints_rad']],goal_candidate_metadata=[meta],benchmark_scope='DIAGNOSTIC_PREAPPROACH_NOT_GOLDEN_55MM_GRASP',benchmark_target_offset_m=row['distance_m'])
path=O/'diagnostic-preapproach-request.json';path.write_text(json.dumps(request,indent=2)+'\n')
summary=dict(scope=request['benchmark_scope'],task_modified=False,scene_modified=False,selected=row,request=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical_motion=False)
(O/'diagnostic-preapproach-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
