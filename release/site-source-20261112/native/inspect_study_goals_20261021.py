import json,time
from pathlib import Path
from ares_r.motion.independent_path_validation import validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
r=json.loads((O/'frozen-pregrasp-only-request.json').read_text());rows=[]
for i,q in enumerate(r['goal_candidates_rad']):
 t=time.monotonic();v=validate_dense_world([q,q],r,subdivisions=2)
 row=dict(candidate=i,symmetry=r['goal_candidate_metadata'][i]['grasp_symmetry_id'],elapsed_s=time.monotonic()-t,validation=v,limiting_box=r['compiled_scene']['cuboids'][v['limiting_object_id']]);rows.append(row)
 print(json.dumps({k:row[k] for k in ('candidate','symmetry','elapsed_s','limiting_box')}|dict(gap=v['min_clearance_m'],component=v['limiting_robot_component_id'],object=v['limiting_object_id'])),flush=True)
(O/'goal-diagnostics.json').write_text(json.dumps(rows,indent=2)+'\n')
