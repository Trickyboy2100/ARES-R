"""Read frozen fresh-scan artifacts; no hardware imports or control calls."""
import copy,hashlib,itertools,json,sys
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.independent_path_validation import _quaternion_rotation,validate_dense_world
from ares_r.manipulation.observed_contact_geometry import point_box_distance
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261019-lift230-fresh-rescan-audit-no-motion'
OUTPUT=O/'rotation-corrected' if '--correct-rotation' in sys.argv else O
OUTPUT.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text())
f=next(O.glob('pick_*'));request=load(f/'pregrasp_plan/planner_request.json')
scene=f/'epoch/live_scene/scene';report=load(scene/'scene_report.json');manifest=load(Path(report['fresh_manifest']))
cloud=np.load(manifest['artifact_npz'])['points_body_m'];decomp=load(scene/'support_decomposition.json')
if '--correct-rotation' in sys.argv:
    from ares_r.world import SceneObject,SceneObjectRole,PoseSE3,compile_snapshot
    saved=load(scene/'snapshot.json');obstacles=[]
    for obj in saved['environment']['observation']['obstacles']:
        pose=obj['pose'];obstacles.append(SceneObject(obj['object_id'],SceneObjectRole(obj['role']),obj['geometry_type'],
          PoseSE3(pose['frame_id'],tuple(pose['xyz_m']),tuple(pose['quaternion_wxyz'])),tuple(obj['dimensions_m']),
          obj['inflation_m'],obj['source_observation_id'],obj['confidence']))
    if saved['left_attached_object'] or saved['right_attached_object']:raise RuntimeError('diagnostic expects pre-grasp snapshot')
    snapshot=SimpleNamespace(snapshot_id=saved['snapshot_id'],planning_context_digest=saved['planning_context_digest'],
       calibration_revision=saved['environment']['observation']['calibration']['revisions'],left_attached_object=None,
       right_attached_object=None,environment=SimpleNamespace(observation=SimpleNamespace(obstacles=obstacles)))
    request['compiled_scene']=compile_snapshot(snapshot,'right',request['T_body_model'],'P3_PRODUCTION_PLANNING_ONLY')
    from ares_r.manipulation.observed_contact_geometry import build_observed_contact_geometry
    request['contact_observed_geometry']=build_observed_contact_geometry(f/'epoch',request)
    (OUTPUT/'corrected_planner_request_DIAGNOSTIC_ONLY.json').write_text(json.dumps(request,indent=2)+'\n')
ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
branch=next(x for x in request['goal_candidate_metadata'] if x['grasp_symmetry_id']=='NORMAL')
from ares_r.world import SceneObject,SceneObjectRole,PoseSE3
from ares_r.manipulation.attached_collision import attach_scene_object,build_attached_collision
from ares_r.manipulation.continuous_demo_lift import build_path
target=next(x for x in decomp['primitives'] if x['primitive_id']==report['target_binding']['primitive_id'])
shape=SceneObject('observed_'+target['primitive_id'],SceneObjectRole.TARGET,'cuboid',
    PoseSE3('body',tuple(target['center_m']),(1.,0.,0.,0.)),tuple(target['dims_m']),0.,report['observation_id'])
attached=build_attached_collision(attach_scene_object(shape,ik.fk(branch['prechecked_paths']['contact'][-1]).tolist(),
    side='right',source_revision='FRESH_LIFT_DIAGNOSTIC_NOT_EXECUTABLE'),request['T_link6_tcp'],inflation_m=.004)
package={'trajectories':branch['prechecked_paths'],'coarse_attached_object_collision':attached,'observation_id':report['observation_id']}
points=np.array(build_path(package,request,.23))
tcp=np.array([ik.fk(q)[:3,3] for q in points]);height=tcp[:,2]-tcp[0,2];suffix=np.flatnonzero(height>=.1-1e-5)
full=copy.deepcopy(request);full['attached_object_collision']=attached;full['motion_constraints']['attached_object_revision']=attached['revision']
full['motion_constraints']['ignore_cuboid_ids']=[];full['compiled_scene']['attached_object_revision']=attached['revision']
for name in request['manipulation_contact_scope']['target_object_ids']:full['compiled_scene']['cuboids'].pop(name)
full['compiled_scene'].pop('digest',None)
full['compiled_scene']['digest']=hashlib.sha256(json.dumps(full['compiled_scene'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
full['scene_digest']=full['compiled_scene']['digest']
coarse_result=validate_dense_world(points[suffix],full,subdivisions=2);name=coarse_result['limiting_object_id']
(OUTPUT/'fresh_lift_coarse_validation.json').write_text(json.dumps(coarse_result,indent=2)+'\n')
(OUTPUT/'fresh_lift_diagnostic_inputs.json').write_text(json.dumps({'kind':'DIAGNOSTIC_ONLY_NOT_EXECUTION_PACKAGE',
    'physical_motion':False,'execution_allowed':False,'source_observation_id':report['observation_id'],
    'package_subset':package,'points_rad':points.tolist()},indent=2)+'\n')
primitive=next(x for x in decomp['primitives'] if 'observed_'+x['primitive_id']==name)
lo,hi=np.array(primitive['observed_bounds_m']);observed=cloud[np.all((cloud>=lo-1e-6)&(cloud<=hi+1e-6),axis=1)]
body=np.array(request['T_body_model'])
b=request['compiled_scene']['cuboids'][name];W=np.eye(4);W[:3,:3]=_quaternion_rotation(b['pose'][3:]);W[:3,3]=b['pose'][:3];W=body@W
obstacle={'center_body_m':W[:3,3],'rotation_body':W[:3,:3],'half_extents_m':np.array(b['dims'])/2}
sign=np.array(list(itertools.product((-1,1),repeat=3)))
def corners(box):return sign*np.array(box['half_extents_m'])@np.array(box['rotation_body']).T+box['center_body_m']
def sep(a,b):
    axes=list(np.array(a['rotation_body']).T)+list(np.array(b['rotation_body']).T)
    axes += [np.cross(x,y) for x in axes[:3] for y in axes[3:6]]
    values=[]
    for axis in axes:
        n=np.linalg.norm(axis)
        if n<1e-9:continue
        axis=axis/n
        values.append(abs(np.dot(b['center_body_m']-a['center_body_m'],axis))-
          np.dot(a['half_extents_m'],np.abs(np.array(a['rotation_body']).T@axis))-
          np.dot(b['half_extents_m'],np.abs(np.array(b['rotation_body']).T@axis)))
    return float(max(values)) # positive = separating axis, NOT Euclidean clearance
def payload(q,coarse):
    t=body@arm_link_transforms(Path(request['robot_yaml_urdf']),q)['link6']
    if coarse:
        box=attached['link6_aabb'];center=t[:3,:3]@box['center_m']+t[:3,3];rot=t[:3,:3];half=np.array(box['half_extents_m'])
    else:
        t=t@np.array(attached['T_link6_object']);center=t[:3,3];rot=t[:3,:3]
        half=np.array(attached['object_dimensions_m'])/2+attached['inflation_m']
    return {'center_body_m':center,'rotation_body':rot,'half_extents_m':half}
tcp=np.array([ik.fk(q)[:3,3] for q in points]);height=tcp[:,2]-tcp[0,2];suffix=np.flatnonzero(height>=.1-1e-5)
coarse=[payload(q,True) for q in points];oriented=[payload(q,False) for q in points]
coarse_gap=np.array([sep(x,obstacle) for x in coarse]);oriented_gap=np.array([sep(x,obstacle) for x in oriented])
raw_gap=np.array([float(np.min(point_box_distance(observed,x)))-primitive['inflation_m'] for x in oriented])
worst=int(suffix[np.argmin(coarse_gap[suffix])]);clear_above=cloud[(np.linalg.norm(cloud[:,:2]-tcp[0,:2],axis=1)<.025)&(cloud[:,2]>tcp[0,2]+.01)&(cloud[:,2]<tcp[0,2]+.23)]
result={'physical_motion':False,'scene_snapshot_id':request['scene_snapshot_id'],'pointcloud_sha256':load(f/'epoch/manipulation_observation.json')['pointcloud_sha256'],
 'limiting_object_id':name,'limiting_observed_bounds_body_m':primitive['observed_bounds_m'],'observed_points_in_bounds':len(observed),
 'grasp_tcp_body_m':tcp[0].tolist(),'lift_end_body_m':tcp[-1].tolist(),'limiting_obstacle_is_above_grasp_tcp':bool(lo[2]>tcp[0,2]),
 'min_coarse_AABB_SAT_axis_gap_suffix_m':float(coarse_gap[suffix].min()),
 'min_oriented_payload_SAT_axis_gap_suffix_m':float(oriented_gap[suffix].min()),
 'min_oriented_payload_to_observed_points_suffix_m':float(raw_gap[suffix].min()),
 'worst_coarse_height_m':float(height[worst]),'raw_points_in_25mm_tcp_vertical_column':len(clear_above),
 'unknown_or_occluded_space_not_certified_free':True,'production_geometry_changed':False,'error_not_cleared':True,
 'full_coarse_validation':coarse_result,'scope':'FRESH_TARGET_LIFT_ONLY_NOT_CACHED_PREGRASP_APPROVAL',
 'payload_dimensions_m':attached['object_dimensions_m'],'coarse_link6_dims_m':attached['link6_aabb']['dims_m'],
 'rotation_correction_applied':'--correct-rotation' in sys.argv}
(OUTPUT/'GEOMETRY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
fig,axs=plt.subplots(2,2,figsize=(15,10));near=cloud[np.all((cloud>tcp[0]-[.25,.3,.22])&(cloud<tcp[0]+[.3,.3,.4]),axis=1)][::3]
edges=[(i,j) for i in range(8) for j in range(i+1,8) if np.sum(sign[i]!=sign[j])==1]
for ax,(i,j,title) in zip(axs.flat,[(0,2,'SIDE X/Z'),(1,2,'REAR Y/Z'),(0,1,'TOP X/Y')]):
    ax.scatter(near[:,i],near[:,j],s=1,c='silver',label='fresh raw BODY cloud')
    ax.scatter(observed[:,i],observed[:,j],s=5,c='red',label='limiting measured points')
    ax.plot(tcp[:,i],tcp[:,j],'b-',lw=2,label='TCP +230mm')
    for box,color,label in [(obstacle,'red','reported obstacle AABB'),(coarse[worst],'orange','coarse link6 payload AABB'),(oriented[worst],'green','same payload oriented box')]:
        c=corners(box)
        for e,(a,b) in enumerate(edges):ax.plot(c[[a,b],i],c[[a,b],j],color=color,lw=1,label=label if e==0 else None)
    ax.set_title(title);ax.set_xlabel('BODY '+'XYZ'[i]+' / m');ax.set_ylabel('BODY '+'XYZ'[j]+' / m');ax.axis('equal');ax.grid(alpha=.2)
axs[0,0].legend(fontsize=7)
ax=axs[1,1];ax.plot(height*1000,coarse_gap*1000,label='coarse payload AABB SAT axis gap')
ax.plot(height*1000,oriented_gap*1000,label='oriented payload SAT axis gap');ax.plot(height*1000,raw_gap*1000,label='oriented payload vs measured points')
ax.axhline(0,color='red',ls='--');ax.axvline(100,color='gray',ls=':');ax.set_xlabel('BODY lift / mm');ax.set_ylabel('gap metric / mm (not interchangeable)');ax.legend(fontsize=7);ax.grid(alpha=.2)
fig.suptitle('Fresh 230mm lift audit - planning only, NO MOTION\n'+request['scene_snapshot_id']);fig.tight_layout();fig.savefig(OUTPUT/'lift230_fresh_geometry_audit.png',dpi=170);plt.close(fig)
print(json.dumps(result),flush=True)
