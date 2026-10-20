"""One BODY-Z lift path and one native stream; no physical pause at100mm.

The golden100mm contact permission is not extended: the remaining lift uses
full gripper+payload collision checking. Policy phases are validation only.
"""
import copy,hashlib,json,math
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.manipulation.task_tcp_offset import demo_local_rotation
from ares_r.motion.tcp_orientation import validate_level_path

def build_path(package,request,total_m=.230):
    if not math.isclose(total_m,.230):raise ValueError('reviewed continuous lift is230mm')
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    rows=np.asarray(package['trajectories']['lift'],dtype=float).copy()
    grasp=ik.fk(package['trajectories']['contact'][-1]);seed=rows[-1]
    if np.max(np.abs(rows[0]-package['trajectories']['contact'][-1]))>1e-4:
        raise RuntimeError('continuous lift must start at exact grasp endpoint')
    if abs(ik.fk(rows[-1])[2,3]-grasp[2,3]-.100)>.0015:
        raise RuntimeError('source initial lift is not100mm')
    result=list(rows)
    for height in np.linspace(.102,total_m,65):
        solved=ik.solve(grasp[:3,3]+np.array([0,0,height]),grasp[:3,:3],seed)
        seed=np.asarray(solved.joints_rad);result.append(seed)
    return np.asarray(result).tolist()

def _separation(a,b):
    """Positive separating-axis gap; non-positive means box contact/overlap."""
    axes=list(a['rotation_body'].T)+list(b['rotation_body'].T)
    axes += [np.cross(x,y) for x in axes[:3] for y in axes[3:6]]
    gaps=[]
    for axis in axes:
        norm=np.linalg.norm(axis)
        if norm<1e-9:continue
        axis=axis/norm
        gaps.append(abs((b['center_body_m']-a['center_body_m'])@axis)-
          np.abs(a['rotation_body'].T@axis)@a['half_extents_m']-
          np.abs(b['rotation_body'].T@axis)@b['half_extents_m'])
    return float(max(gaps))

def fixture_escape(points,request,attached,grasp_z,policy):
    """Demo-only departure from a visually confirmed lower grasp fixture.

    No world object is deleted. Only tool/payload pairs with an observed box
    wholly inside the registered lower fixture region may depart contact.
    Arm/world pairs are independently hard-checked by validate_path below.
    """
    if not policy or not policy.get('enabled'):return [],None
    if policy.get('scope')!='RIGHT_ROUNDTRIP_LIFT230_ONLY' or policy.get('operator_confirmed') is not True:
        raise RuntimeError('invalid demo lift contact escape scope')
    from ares_r.motion.independent_path_validation import _quaternion_rotation
    from ares_r.perception.robot_collision import arm_link_transforms
    lower,upper=np.asarray(policy['fixture_bounds_body_m'],dtype=float)
    anchor_proof=None
    if policy.get('reference_grasp_body_m') is not None:
        reference=np.asarray(policy['reference_grasp_body_m'],dtype=float)
        target=np.asarray(request.get('task_target_pose_body_m_rad',[])[:3],dtype=float)
        if (reference.shape!=(3,) or target.shape!=(3,) or not np.isfinite([reference,target]).all()):
            raise RuntimeError('demo fixture target anchor unavailable')
        shift=target-reference
        if np.linalg.norm(shift)>.060:raise RuntimeError('demo fixture anchor moved beyond60mm; registration required')
        lower=lower+shift;upper=upper+shift
        anchor_proof={'reference_grasp_body_m':reference.tolist(),'current_grasp_body_m':target.tolist(),
            'translation_m':shift.tolist(),'source_scene_snapshot_id':policy.get('source_scene_snapshot_id'),
            'same_dimensions':True,'registration_role':'bounded source-fixture association only, not camera calibration'}
    association=float(policy.get('association_tolerance_m',0.))
    if not math.isfinite(association) or not 0<=association<=.015:
        raise RuntimeError('demo fixture association tolerance outside0..15mm')
    if (lower.shape!=(3,) or upper.shape!=(3,) or not np.isfinite([lower,upper]).all() or
        np.any(upper<=lower) or np.any(upper-lower>np.array([.10,.22,.10])+1e-9) or upper[2]>grasp_z+.01):
        raise RuntimeError('demo fixture region must be small and below grasp')
    body=np.asarray(request['T_body_model']);sign=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])
    fixtures={}
    for name,box in request['compiled_scene']['cuboids'].items():
        if not name.startswith('observed_') or name in request['manipulation_contact_scope']['target_object_ids']:continue
        center=body[:3,:3]@np.asarray(box['pose'][:3])+body[:3,3]
        rotation=body[:3,:3]@_quaternion_rotation(box['pose'][3:]);half=np.asarray(box['dims'])/2
        corners=(sign*half)@rotation.T+center
        if (np.all(corners>=lower-association) and np.all(corners<=upper+association)
            and np.max(corners[:,2])<=grasp_z+.01):
            fixtures[name]={'center_body_m':center,'rotation_body':rotation,'half_extents_m':half}
    if not fixtures:raise RuntimeError('confirmed lower grasp fixture not found in fresh scene')
    local_boxes=[attached['link6_aabb'],request['collision_model']['gripper_max_envelope_link6']]
    proofs=[]
    for name,fixture in fixtures.items():
        for component,local in zip(('payload','gripper_envelope'),local_boxes):
            gaps=[]
            for q in points:
                t=body@arm_link_transforms(request['robot_yaml_urdf'],q)['link6']
                box={'center_body_m':t[:3,:3]@np.asarray(local['center_m'])+t[:3,3],
                     'rotation_body':t[:3,:3],'half_extents_m':np.asarray(local['half_extents_m'])}
                gaps.append(_separation(box,fixture))
            if min(np.diff(gaps))<-.0005 or gaps[-1]<=.002:
                raise RuntimeError('demo lift must separate from fixture without deeper/new contact')
            if gaps[0]>0 and min(gaps)<0:raise RuntimeError('new fixture contact during lift')
            proofs.append({'object_id':name,'component':component,'start_axis_gap_m':gaps[0],
                           'end_axis_gap_m':gaps[-1],'minimum_axis_gap_m':min(gaps)})
    return list(fixtures),{'revision':policy['revision'],'scope':policy['scope'],
        'fixture_bounds_body_m':[lower.tolist(),upper.tolist()],'association_tolerance_m':association,'pairs':proofs,
        'target_anchor':anchor_proof,
        'arm_world_still_hard':True,'other_world_still_hard':True,'expires_after_lift':True}

def validate_path(points,request,package,*,check_cancelled=lambda:None,contact_escape=None):
    from ares_r.motion.short_motion import validate_short_motion
    from ares_r.motion.independent_path_validation import validate_dense_world,_quaternion_rotation
    from ares_r.perception.robot_collision import arm_link_transforms
    from ares_r.manipulation.contact_bypass import HardWorldBroadPhase
    from ares_r.manipulation.contact_motion import _geometry_overlap
    from ares_r.manipulation.attached_collision import verify_attached_collision
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    rows=np.asarray(points,dtype=float)
    if rows.ndim!=2 or rows.shape[1]!=6 or len(rows)<3 or not np.isfinite(rows).all():raise ValueError('finite continuous lift path required')
    grasp=ik.fk(package['trajectories']['contact'][-1]);dense=np.concatenate([
        a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(rows,rows[1:])]+[rows[-1:]])
    positions=np.array([ik.fk(q)[:3,3] for q in dense]);delta=positions-grasp[:3,3]
    if (np.linalg.norm(delta[0])>.003 or np.linalg.norm(delta[:,:2],axis=1).max()>.002 or
        abs(delta[-1,2]-.230)>.003 or delta[:,2].min()<-.002 or
        delta[:,2].max()>.233 or np.diff(delta[:,2]).min()<-.001):
        raise RuntimeError('continuous lift must be one monotonic BODY+Z230mm path')
    compensation={'demo_tcp_orientation_compensation':request.get('demo_tcp_orientation_compensation',{})}
    def physical_fk(q):
        t=ik.fk(q);t[:3,:3]=demo_local_rotation(t[:3,:3],compensation,inverse=True);return t
    level=validate_level_path(physical_fk,rows,subdivisions=4,tolerance_deg=3.)
    if not level['passed']:raise RuntimeError('continuous230 physical level invalid')
    boundary=int(np.flatnonzero(delta[:,2]>=.100-1e-5)[0])
    target_ids=request['manipulation_contact_scope']['target_object_ids']
    prefix=validate_short_motion(dense[:boundary+1],request,segment='lift',
        observation_id=package['observation_id'],direction=[0,0,1],
        central_exclusion=request['motion_constraints'].get('central_exclusion',False),
        contact_target_ids=target_ids,check_cancelled=check_cancelled)
    full=copy.deepcopy(request);attached=package['coarse_attached_object_collision']
    verify_attached_collision(attached)
    if attached['object_id'] not in target_ids or attached['source_observation_id']!=package['observation_id']:
        raise RuntimeError('continuous lift payload/observation identity mismatch')
    full['attached_object_collision']=attached
    full['motion_constraints']['attached_object_revision']=attached['revision']
    escaped,escape_proof=fixture_escape(dense[boundary:],request,attached,grasp[2,3],contact_escape)
    full['motion_constraints']['ignore_cuboid_ids']=escaped
    world=full['compiled_scene'];world['attached_object_revision']=attached['revision']
    removed=[]
    for name in target_ids:
        if world['cuboids'].pop(name,None) is None:raise RuntimeError('bound payload missing from source world')
        removed.append(name)
    world['attached_observation_deduplication']={'object_ids':removed,'attachment_revision':attached['revision']}
    world.pop('digest',None)
    world['digest']=hashlib.sha256(json.dumps(world,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    full['scene_digest']=world['digest']
    suffix=validate_dense_world(dense[boundary:],full,subdivisions=2)
    if not suffix['collision_free']:raise RuntimeError('continuous230 full loaded-world collision: '+str(suffix))
    # Independent full-path link/world and non-adjacent link/link SAT checks.
    body=np.asarray(request['T_body_model']);hard_world={}
    for name,box in request['compiled_scene']['cuboids'].items():
        pose=body@np.block([[_quaternion_rotation(box['pose'][3:]),np.array(box['pose'][:3])[:,None]],
                           [np.zeros((1,3)),np.ones((1,1))]])
        hard_world[name]={'center_body_m':pose[:3,3].tolist(),'rotation_body':pose[:3,:3].tolist(),
                          'half_extents_m':(np.asarray(box['dims'])/2).tolist()}
    broad=HardWorldBroadPhase(hard_world)
    for q in dense:
        check_cancelled()
        if np.any(q<ik.lower) or np.any(q>ik.upper):raise RuntimeError('continuous230 joint limit')
        frames=arm_link_transforms(request['robot_yaml_urdf'],q);links=[]
        for name in ('link1','link2','link3','link4','link5','link6'):
            box=request['collision_model']['arm_link_boxes'][name];t=body@frames[name]
            link={'geometry_id':name,'center_body_m':(t[:3,:3]@np.array(box['center_m'])+t[:3,3]).tolist(),
                  'rotation_body':t[:3,:3].tolist(),'half_extents_m':box['half_extents_m']}
            if any(_geometry_overlap(link,obstacle) for _,obstacle in broad.candidates(link)):
                raise RuntimeError('continuous230 link/world collision')
            links.append(link)
        if any(_geometry_overlap(a,b) for i,a in enumerate(links) for b in links[i+2:]):
            raise RuntimeError('continuous230 non-adjacent self collision')
    return {'passed':True,'single_native_stream':True,'distance_m':float(delta[-1,2]),
        'physical_level':level,'initial_contact100_validation':prefix,'remaining_loaded_world_validation':suffix,
        'contact_permission_extended':False,'self_collision_checked':True,
        'demo_lower_fixture_contact_escape':escape_proof,
        'payload_world_duplicate_ids':removed,'dense_samples':len(dense)}
