"""Bounded target-pocket contact, not a general collision-disable mode."""
import copy,hashlib,json
import numpy as np
from ares_r.motion.independent_path_validation import _quaternion_rotation,validate_dense_world
from ares_r.manipulation.task_tcp_offset import validate_body_descent,demo_local_rotation
from ares_r.manipulation.contact_bypass import ContactBypassPolicy,validate_bypass_segment
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.tcp_orientation import validate_level_path

def build_descent_points(ik,start_joints,distance_m=.05):
    if abs(distance_m-.05)>1e-9:raise ValueError('commissioned descent is 50mm')
    q=np.asarray(start_joints);start=ik.fk(q);points=[q.tolist()]
    for d in np.linspace(.002,.05,25):
        q=np.asarray(ik.solve(start[:3,3]+[0,0,-d],start[:3,:3],q).joints_rad)
        points.append(q.tolist())
    return points

def outside_parts(lo,hi,lower,upper):
    lo=np.array(lo,dtype=float);hi=np.array(hi,dtype=float)
    a=np.maximum(lo,lower);b=np.minimum(hi,upper)
    if np.any(b<=a):return [(lo,hi)]
    parts=[]
    for axis in range(3):
        if lo[axis]<a[axis]:
            end=hi.copy();end[axis]=a[axis];parts.append((lo.copy(),end));lo[axis]=a[axis]
        if hi[axis]>b[axis]:
            start=lo.copy();start[axis]=b[axis];parts.append((start,hi.copy()));hi[axis]=b[axis]
    return parts

def validate(points,request,ik,slot_body,p,check_cancelled=lambda:None):
    axis=validate_body_descent(points,ik.fk,.05,tolerance_m=.003)
    rows=np.asarray(points);dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(rows,rows[1:])]+[rows[-1:]])
    actual=ik.fk(rows[0]);slot=np.asarray(slot_body)
    if np.linalg.norm(actual[:2,3]-slot[:2])>.005 or abs(actual[2,3]-slot[2]-.04)>.005:
        raise RuntimeError('PLACE_CONTACT_REQUIRES_CURRENT_ID3_PRELAND')
    def physical(q):
        t=ik.fk(q);t[:3,:3]=demo_local_rotation(t[:3,:3],p,inverse=True);return t
    level=validate_level_path(physical,rows,tolerance_deg=3.,subdivisions=4)
    if not level['passed']:raise RuntimeError('PLACE_CONTACT_LEVEL_INVALID')
    # A registered empty 300x300mm lower-middle placement contact corridor.
    # Only measured lower dock geometry INSIDE this region permits tool/payload
    # contact. All geometry outside it, unknowns and all arm links stay hard.
    lower=slot+[-.15,-.15,-.22];upper=slot+[.15,.15,.01]
    body=np.asarray(request['T_body_model']);world={};clipped=copy.deepcopy(request);allowed=[]
    signs=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])
    for name,b in request['compiled_scene']['cuboids'].items():
        center=body[:3,:3]@np.array(b['pose'][:3])+body[:3,3];rotation=body[:3,:3]@_quaternion_rotation(b['pose'][3:]);half=np.array(b['dims'])/2
        world[name]={'center_body_m':center.tolist(),'rotation_body':rotation.tolist(),'half_extents_m':half.tolist()}
        corners=(signs*half)@rotation.T+center;lo=corners.min(0);hi=corners.max(0)
        measured=name.startswith(('observed_support_','observed_remaining_structure_'))
        if not measured or hi[2]>upper[2] or np.any(hi<=lower) or np.any(lo>=upper):continue
        parts=outside_parts(lo,hi,lower,upper);allowed.append(name)
        clipped['compiled_scene']['cuboids'].pop(name)
        for i,(a,z) in enumerate(parts):
            center_model=np.linalg.inv(body)@np.r_[(a+z)/2,1]
            from ares_r.world.scene_compiler import _quaternion_wxyz
            clipped['compiled_scene']['cuboids'][name+'_outside_contact_'+str(i)]={
                'dims':(z-a).tolist(),'pose':center_model[:3].tolist()+_quaternion_wxyz(body[:3,:3].T)}
    if not allowed:raise RuntimeError('PLACE_TARGET_DOCK_GEOMETRY_NOT_FOUND')
    samples=[]
    for q in dense:
        check_cancelled();frames=arm_link_transforms(request['robot_yaml_urdf'],q);links=[]
        for name in ('link1','link2','link3','link4','link5','link6'):
            b=request['collision_model']['arm_link_boxes'][name];t=body@frames[name]
            links.append({'geometry_id':name,'center_body_m':(t[:3,:3]@np.array(b['center_m'])+t[:3,3]).tolist(),
                'rotation_body':t[:3,:3].tolist(),'half_extents_m':b['half_extents_m']})
        samples.append({'joints_rad':q.tolist(),'tcp_position_body_m':ik.fk(q)[:3,3].tolist(),'arm_links':links})
    hard=validate_bypass_segment(samples,world,ContactBypassPolicy.for_manipulation_skill('PLACE_DESCENT',
        request['scene_snapshot_id'],central_exclusion=request['motion_constraints'].get('central_exclusion',False)),
        expected_direction_body=[0,0,-1],joint_lower=ik.lower,joint_upper=ik.upper,check_cancelled=check_cancelled)
    clipped['motion_constraints']['ignore_cuboid_ids']=[]
    clipped['compiled_scene'].pop('digest',None)
    clipped['compiled_scene']['digest']=hashlib.sha256(json.dumps(clipped['compiled_scene'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result=validate_dense_world(dense,clipped,subdivisions=2)
    if not result['collision_free']:raise RuntimeError('PLACE_CONTACT_NON_TARGET_COLLISION:'+str(result))
    return {'passed':True,'axis':axis,'level':level,'arm_world_and_self':hard,'non_target_world':result,
        'contact_target_ids':allowed,'contact_region_body_m':[lower.tolist(),upper.tolist()],
        'policy':'DEMO_PLACE_DESCENT50_EMPTY_LOWER_MIDDLE_ONLY','expires_after_descent':True,
        'scene_snapshot_id':request['scene_snapshot_id'],'original_world_unchanged':True}
