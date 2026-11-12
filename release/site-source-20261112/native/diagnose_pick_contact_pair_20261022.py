"""Exact first contact pair attribution, no motion or geometry changes."""
import json
from pathlib import Path
import numpy as np
from ares_r.manipulation.gripper_component_collision import build_gripper_component_model,component_boxes_body
from ares_r.manipulation.observed_contact_geometry import point_box_distance
from ares_r.manipulation.contact_motion import _geometry_overlap
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.independent_path_validation import _quaternion_rotation
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-overlap-r2';E=R/'worklog/evidence/20261022-pick-reset-overlap-r1/epoch'
r=json.loads((O/'pregrasp/planner_request.json').read_text());p=json.loads((O/'package/first_pick_execution_package.json').read_text());report=json.loads((E/'live_scene/scene/scene_report.json').read_text());decomp=json.loads((E/'live_scene/scene/support_decomposition.json').read_text());manifest=json.loads(Path(report['fresh_manifest']).read_text());raw=np.load(manifest['artifact_npz'])['points_body_m'];body=np.array(r['T_body_model']);name='observed_support_00_component_01_protruding';w=r['compiled_scene']['cuboids'][name];ob=dict(center_body_m=(body[:3,:3]@w['pose'][:3]+body[:3,3]).tolist(),rotation_body=body[:3,:3]@_quaternion_rotation(w['pose'][3:]),half_extents_m=np.array(w['dims'])/2);prim=next(x for x in decomp['primitives'] if 'observed_'+x['primitive_id']==name);lo,hi=np.array(prim['observed_bounds_m']);cloud=raw[np.all((raw>=lo-1e-6)&(raw<=hi+1e-6),axis=1)];out=[]
for stage,openings in [('contact',[40]),('lift',list(range(0,41,5)))]:
 found=False
 for i,q in enumerate(p['trajectories'][stage]):
  t=body@arm_link_transforms(r['robot_yaml_urdf'],q)['link6']
  for opening in openings:
   model=build_gripper_component_model(r['collision_model'],opening)
   for box in component_boxes_body(model,r['collision_model'],t):
    if _geometry_overlap(box,ob):
     d=point_box_distance(cloud,box);j=int(d.argmin());out.append(dict(stage=stage,knot=i,opening=opening,component=box['geometry_id'],component_body=box,obstacle_center=ob['center_body_m'],raw_min_gap_m=float(d[j]),raw_min_gap_with_sensor_padding_m=float(d[j])-.007,nearest_point=cloud[j].tolist(),target_ids=r['manipulation_contact_scope']['target_object_ids'],primitive=prim));found=True;break
   if found:break
  if found:break
(O/'contact-pair-attribution.json').write_text(json.dumps(dict(physical_motion=False,rows=out),indent=2)+'\n')
for row in out:print(json.dumps({k:v for k,v in row.items() if k not in ('primitive','component_body')}),flush=True)
