"""Narrow-phase diagnostic over actual retained occupied points, no deletion."""
from pathlib import Path
import json,time
import numpy as np
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.manipulation.gripper_component_collision import component_boxes_body
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-current-pick-rehearsal'
r=json.load(open(O/'component_plan/planner_request.json'));body=np.asarray(r['T_body_model']);comp=r['execution_tool_envelope']['component_model'];decomp=json.load(open(O/'epoch2/live_scene/scene/support_decomposition.json'));points=np.load(O/'epoch2/live_scene/scene/clean_residual.npz')['points_body_m']
target=next(x for x in decomp['primitives'] if x['primitive_id']=='support_02_component_00_protruding');c=np.asarray(target['center_m']);h=np.asarray(target['dims_m'])/2
# Same declared manipulation TARGET only, not nearby support or arbitrary radius.
non_target=points[~np.all(np.abs(points-c)<=h,axis=1)];rows=[]
for b in json.load(open(O/'component_plan/contact_lift_precheck.json'))['accepted']:
 for segment in ('contact','lift'):
  minimum=float('inf');limiting=None
  for index,q in enumerate(b['prechecked_paths'][segment]):
   T=body@arm_link_transforms(Path(r['robot_yaml_urdf']),q)['link6']
   for box in component_boxes_body(comp,r['collision_model'],T):
    p=(non_target-np.asarray(box['center_body_m']))@np.asarray(box['rotation_body']);d=np.abs(p)-np.asarray(box['half_extents_m']);outside=np.linalg.norm(np.maximum(d,0),axis=1);inside=np.minimum(np.max(d,axis=1),0);dist=outside+inside;k=np.argmin(dist)
    if dist[k]<minimum:minimum=float(dist[k]);limiting={'component':box['geometry_id'],'sample':index,'point_body_m':non_target[k].tolist()}
  row={'branch':b['grasp_symmetry_id'],'segment':segment,'minimum_point_to_component_m':minimum,'limiting':limiting,'unmodified_non_target_point_count':len(non_target),'diagnostic_only':True};rows.append(row);print(row,flush=True)
  (O/'contact-rawpoint-diagnostic.json').write_text(json.dumps(rows,indent=2))
