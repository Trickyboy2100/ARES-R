"""Frozen candidate comparison. No robot/network interfaces or execution."""
import copy,hashlib,json,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ares_r.manipulation.collision_refinement import payload_spheres_link6,observed_obb
from ares_r.manipulation.continuous_demo_lift import _separation
from ares_r.motion.independent_path_validation import validate_dense_world,_quaternion_rotation
from ares_r.perception.robot_owned_filter import grid_spheres_local
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.world.scene_compiler import _quaternion_wxyz
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-v17-oriented-geometry-audit-v2';O.mkdir(exist_ok=False)
S=R/'worklog/evidence/scene-aware-motion/scene_20261019T105247Z_e546b192/scene'
r=json.loads((R/'worklog/evidence/scene-aware-motion/PLAN_57999a4d9b084d62b76e1f9899459619/planner_request.json').read_text())
points=np.load(S/'clean_residual.npz')['points_body_m'];decomp=json.loads((S/'support_decomposition.json').read_text())
B=np.asarray(r['T_body_model']);a=r['attached_object_collision'];T=B@arm_link_transforms(r['robot_yaml_urdf'],r['start_rad'])['link6']@np.asarray(a['T_link6_object'])
payload={'center_body_m':T[:3,3],'rotation_body':T[:3,:3],'half_extents_m':np.asarray(a['object_dimensions_m'])/2+a['inflation_m']}
candidate=copy.deepcopy(r);records=[]
for primitive in decomp['primitives']:
    if primitive['semantic']!='UNKNOWN_OCCUPIED':continue
    name='observed_'+primitive['primitive_id']
    if name not in candidate['compiled_scene']['cuboids']:continue
    low,high=np.asarray(primitive['observed_bounds_m']);member=points[np.all((points>=low-1e-9)&(points<=high+1e-9),axis=1)]
    if len(member)<3:continue
    box=observed_obb(member,float(primitive['inflation_m']))
    center=B[:3,:3].T@(np.asarray(box['center_body_m'])-B[:3,3]);rotation=B[:3,:3].T@np.asarray(box['rotation_body'])
    candidate['compiled_scene']['cuboids'][name]={'pose':center.tolist()+_quaternion_wxyz(rotation),'dims':(2*np.asarray(box['half_extents_m'])).tolist()}
    records.append(dict(box,id=name,source_bounds=primitive['observed_bounds_m']))
world=candidate['compiled_scene'];world.pop('digest',None);world['digest']=hashlib.sha256(json.dumps(world,sort_keys=True,separators=(',',':')).encode()).hexdigest();candidate['scene_digest']=world['digest']
rows=[]
for label,req,cell in [('LEGACY',r,None),('ORIENTED_PAYLOAD_15MM',r,.015),('ORIENTED_PAYLOAD_AND_OBSERVED_OBB_15MM',candidate,.015),('ORIENTED_PAYLOAD_AND_OBSERVED_OBB_5MM',candidate,.005)]:
    started=time.monotonic()
    def builder(box,original_cell=.035):
        if cell is not None and box==a['link6_aabb']:return payload_spheres_link6(a,cell)
        return grid_spheres_local(box,original_cell)
    with patch('ares_r.motion.independent_path_validation.grid_spheres_local',builder):
        proof=validate_dense_world([req['start_rad']]*2,req,subdivisions=2)
    exact=[]
    for name,b in req['compiled_scene']['cuboids'].items():
        w={'center_body_m':B[:3,:3]@b['pose'][:3]+B[:3,3],'rotation_body':B[:3,:3]@_quaternion_rotation(b['pose'][3:]),'half_extents_m':np.asarray(b['dims'])/2}
        exact.append((_separation(payload,w),name))
    rows.append({'variant':label,'dense_start':proof,'exact_payload_obb_limiting':sorted(exact)[:3],'wall_s':time.monotonic()-started})
report={'physical_motion':False,'runtime_activated':False,'points_deleted':0,'payload_padding_m':a['inflation_m'],'source_scene':r['scene_snapshot_id'],'variants':rows,'fitted_obstacle_count':len(records),'coverage':records}
(O/'REPORT.json').write_text(json.dumps(report,indent=2));(O/'candidate_request_NOT_EXECUTION_READY.json').write_text(json.dumps(candidate,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='coverage'}),flush=True)
