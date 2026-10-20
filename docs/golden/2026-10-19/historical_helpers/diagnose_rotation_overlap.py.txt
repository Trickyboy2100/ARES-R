import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.spatial import cKDTree
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.perception.robot_owned_filter import grid_spheres_local
R=Path('/home/yikun/ARES-R-RC1-20261019')
p=json.loads((R/'worklog/evidence/scene-aware-motion/PLAN_86864ba63d3442068f6ad375b87b9b44/planner_request.json').read_text())
s=R/'worklog/evidence/scene-aware-motion/scene_20261019T060021Z_2ae46da1/scene'
points=np.load(s/'clean_residual.npz')['points_body_m'];T=np.array(p['T_body_model']);fk=arm_link_transforms(Path(p['robot_yaml_urdf']),p['start_rad'])
box=p['compiled_scene']['cuboids']['observed_support_01_component_00_protruding'];rot=Rotation.from_quat(np.array(box['pose'][3:])[[1,2,3,0]]).as_matrix()
model=p['collision_model'];geometries=[(k,v) for k,v in model['arm_link_boxes'].items()]
env=p['execution_tool_envelope'];geometries += [('gripper',env['box']),('payload',p['attached_object_collision']['link6_aabb'])]
rows=[]
for name,g in geometries:
    link=name if name in fk else 'link6';tf=T@fk[link]
    sphere=grid_spheres_local(g,float(p['planning_parameters'].get('active_sphere_cell_m',.035)))
    c=np.array([x['center'] for x in sphere])@tf[:3,:3].T+tf[:3,3];r=np.array([x['radius'] for x in sphere]);local=(c-T[:3,3])@T[:3,:3];a=(local-np.array(box['pose'][:3]))@rot
    delta=np.abs(a)-np.array(box['dims'])/2;gap=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(axis=1),0)-r
    distances,idx=cKDTree(points).query(c);rawgap=distances-r
    rows.append({'geometry':name,'aabb_gap_mm':float(gap.min()*1000),'observed_point_gap_mm':float(rawgap.min()*1000),'nearest_point':points[idx[rawgap.argmin()]].tolist()})
out=R/'worklog/evidence/operations-single/20261019-tcp-local-z-minus10/overlap-attribution.json';out.write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
