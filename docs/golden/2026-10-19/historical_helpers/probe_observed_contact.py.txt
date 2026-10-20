"""Frozen-scene diagnostic: source raw occupancy, unchanged sensor inflation."""
import json,time
from pathlib import Path
import numpy as np
from ares_r.manipulation.gripper_component_collision import build_gripper_component_model,component_boxes_body
from ares_r.perception.robot_collision import arm_link_transforms
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-pick-retest-1113'
def load(p):return json.loads(p.read_text())
r=load(O/'pregrasp_plan/planner_request.json');scene=O/'epoch2/live_scene/scene';report=load(scene/'scene_report.json');manifest=load(Path(report['fresh_manifest']));raw=np.load(manifest['artifact_npz'])['points_body_m'];decomp=load(scene/'support_decomposition.json');objects={x['id']:x for x in report['objects']};comp=build_gripper_component_model(r['collision_model'],40);body=np.asarray(r['T_body_model']);voxels=[];source=[]
for p in decomp['primitives']:
 name='observed_'+p['primitive_id']
 if name in r['motion_constraints']['ignore_cuboid_ids'] or p['semantic'] not in ('SUPPORT_SURFACE','STRUCTURE'):continue
 if name not in r['compiled_scene']['cuboids']:continue
 lo,hi=np.asarray(p['observed_bounds_m']);cloud=raw[np.all((raw>=lo-.000001)&(raw<=hi+.000001),axis=1)]
 if len(cloud)<10:continue
 keys=np.unique(np.floor(cloud/.002).astype(np.int64),axis=0);centers=(keys+.5)*.002;inflation=objects[name]['inflation_m'];radius=np.sqrt(3)*.001+inflation
 source.append({'id':name,'raw_points':len(cloud),'voxels':len(keys),'inflation_m':inflation});voxels.append((name,centers,radius))
print('raw',len(raw),'refined',len(source),'voxels',sum(x['voxels'] for x in source),flush=True)
records=[]
for b in load(O/'pregrasp_plan/contact_lift_precheck.json')['accepted']:
 for segment in ('contact','lift'):
  minimum=float('inf');limiting=None
  for index,q in enumerate(b['prechecked_paths'][segment]):
   T=body@arm_link_transforms(Path(r['robot_yaml_urdf']),q)['link6']
   for box in component_boxes_body(comp,r['collision_model'],T):
    for name,centers,radius in voxels:
     local=(centers-box['center_body_m'])@np.asarray(box['rotation_body']);d=np.abs(local)-box['half_extents_m'];dist=np.linalg.norm(np.maximum(d,0),axis=1)+np.minimum(np.max(d,axis=1),0)-radius
     value=float(dist.min())
     if value<minimum:minimum=value;limiting={'component':box['geometry_id'],'obstacle':name,'sample':index}
  v={'branch':b['grasp_symmetry_id'],'stage':segment,'min_clearance_m':minimum,'limiting':limiting};records.append(v);print(v,flush=True)
g=load(O/'epoch2/live_scene/whole_robot_geometry.json');near=[]
for p in decomp['primitives']:
 if p['primitive_id'] not in ('remaining_structure_structure_001','remaining_structure_structure_002','support_02_support_surface_001','support_02_support_surface_002'):continue
 point=np.asarray(p['center_m']);dist=[]
 for box in g['boxes']:
  if box['owner'] not in ('right_arm','right_gripper','left_arm','left_gripper'):continue
  local=(point-box['center_body_m'])@np.asarray(box['rotation_body']);d=np.abs(local)-box['half_extents_m'];value=np.linalg.norm(np.maximum(d,0))+min(max(d),0);dist.append((float(value),box['geometry_id']))
 near.append({'id':p['primitive_id'],'nearest_current_robot':min(dist)})
print('self_filter_attribution',near,flush=True)
(O/'raw_occupancy_probe.json').write_text(json.dumps({'source':source,'stages':records,'self_filter_attribution':near},indent=2))
