"""Frozen-data narrow-phase diagnosis only; never changes the planning world."""
import json
from pathlib import Path
import numpy as np
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.manipulation.gripper_component_collision import component_boxes_body
from ares_r.manipulation.observed_contact_geometry import point_box_distance
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study';r=json.loads((O/'frozen-pregrasp-only-request.json').read_text())
scene=O/'pick-epoch/live_scene/scene';report=json.loads((scene/'scene_report.json').read_text());manifest=json.loads(Path(report['fresh_manifest']).read_text());raw=np.load(manifest['artifact_npz'])['points_body_m']
decomp=json.loads((scene/'support_decomposition.json').read_text());name='observed_support_00_component_01_protruding';primitive=next(x for x in decomp['primitives'] if 'observed_'+x['primitive_id']==name)
low,high=np.array(primitive['observed_bounds_m']);cloud=raw[np.all((raw>=low-1e-6)&(raw<=high+1e-6),axis=1)]
obj=next(x for x in report['objects'] if x['id']==name);padding=float(obj['inflation_m']);rows=[]
for i,q in enumerate(r['goal_candidates_rad']):
 t=np.array(r['T_body_model'])@arm_link_transforms(Path(r['robot_yaml_urdf']),q)['link6']
 boxes=component_boxes_body(r['execution_tool_envelope']['component_model'],r['collision_model'],t)
 gaps=[]
 for b in boxes:
  values=point_box_distance(cloud,b);k=int(np.argmin(values));gaps.append(dict(component=b['geometry_id'],raw_point_gap_m=float(values[k]),same_sensor_padding_gap_m=float(values[k]-padding),nearest_point_body_m=cloud[k].tolist()))
 row=dict(symmetry=r['goal_candidate_metadata'][i]['grasp_symmetry_id'],limiting=min(gaps,key=lambda x:x['same_sensor_padding_gap_m']),all_components=gaps);rows.append(row);print(json.dumps(row),flush=True)
summary=dict(object_id=name,semantic=primitive['semantic'],source_cluster=primitive.get('source_cluster'),observed_bounds_body_m=primitive['observed_bounds_m'],source_raw_points=len(cloud),sensor_padding_m=padding,diagnostic_only=True,world_modified=False,rows=rows)
(O/'pregrasp-raw-geometry-diagnosis.json').write_text(json.dumps(summary,indent=2)+'\n')
