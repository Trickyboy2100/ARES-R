"""Read-only exact OBB diagnostic, keeps original scene inflation."""
from pathlib import Path
import json,time
import numpy as np
from ares_r.perception.robot_collision import CollisionBox,obb_overlap,arm_link_transforms
from ares_r.manipulation.gripper_component_collision import component_boxes_body
from ares_r.motion.independent_path_validation import _quaternion_rotation
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-current-pick-rehearsal'
r=json.load(open(O/'component_plan/planner_request.json'));body=np.asarray(r['T_body_model']);comp=r['execution_tool_envelope']['component_model'];ignored=set(r['motion_constraints']['ignore_cuboid_ids']);world=[]
for k,v in r['compiled_scene']['cuboids'].items():
 if k in ignored:continue
 c=body[:3,:3]@v['pose'][:3]+body[:3,3];rot=body[:3,:3]@_quaternion_rotation(v['pose'][3:]);h=np.asarray(v['dims'])/2
 world.append((k,CollisionBox(k,'world','obstacle',tuple(c),tuple(map(tuple,rot)),tuple(h),False,'FROZEN_SCENE'),c,np.abs(rot)@h))
records=[]
for b in json.load(open(O/'component_plan/contact_lift_precheck.json'))['accepted']:
 for segment in ('contact','lift'):
  t=time.monotonic();hits=[];pairs=0
  for index,q in enumerate(b['prechecked_paths'][segment]):
   T=body@arm_link_transforms(Path(r['robot_yaml_urdf']),q)['link6']
   for box in component_boxes_body(comp,r['collision_model'],T):
    c=np.asarray(box['center_body_m']);rot=np.asarray(box['rotation_body']);h=np.asarray(box['half_extents_m']);aabb=np.abs(rot)@h
    x=CollisionBox(box['geometry_id'],'right','gripper',tuple(c),tuple(map(tuple,rot)),tuple(h),False,comp['revision'])
    for k,ob,c2,h2 in world:
     if np.any(np.abs(c-c2)>aabb+h2):continue
     pairs+=1
     if obb_overlap(x,ob):hits.append({'index':index,'component':box['geometry_id'],'obstacle':k})
  row={'branch':b['grasp_symmetry_id'],'segment':segment,'samples':len(b['prechecked_paths'][segment]),'hits':hits,'pairs':pairs,'wall_s':time.monotonic()-t};records.append(row);print(row['branch'],segment,'EXACT_OBB_HITS',len(hits),hits[:3],flush=True)
  (O/'exact-component-diagnostic.json').write_text(json.dumps(records,indent=2))
