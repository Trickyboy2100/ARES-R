"""Shared dense checks for contact/lift geometry changed by native retiming."""
import numpy as np
from ares_r.manipulation.contact_bypass import ContactBypassPolicy,validate_bypass_segment
from ares_r.perception.robot_collision import arm_link_transforms
from .runtime_goal_ik import RuntimeGoalIK
from .tcp_orientation import validate_level_path
from .independent_path_validation import _quaternion_rotation


def validate_short_motion(points,request,*,segment,observation_id,direction,central_exclusion=False,check_cancelled=lambda:None,contact_target_ids=None):
    # Additive: legacy frozen/golden requests retain their existing contract.
    # New first-pick requests bind a target-only, one-validation permission.
    if 'manipulation_contact_scope' not in request:
        if request.get('contact_observed_geometry'):
            raise RuntimeError('CONTACT_SCOPE_BINDING_REQUIRED')
        return _validate_short_motion(points,request,segment=segment,observation_id=observation_id,
            direction=direction,central_exclusion=central_exclusion,check_cancelled=check_cancelled,
            contact_target_ids=contact_target_ids)
    from ares_r.manipulation.stage_contact_permission import StageContactPermission
    ids=list(contact_target_ids if contact_target_ids is not None else
        request['manipulation_contact_scope']['target_object_ids'])
    permission=StageContactPermission.issue(request,points,segment=segment,
        observation_id=observation_id,target_ids=ids)
    def checked():
        check_cancelled()
        permission.check(request,segment=segment,observation_id=observation_id)
    try:
        permission.check(request,points,segment=segment,observation_id=observation_id)
        result=_validate_short_motion(points,request,segment=segment,observation_id=observation_id,
            direction=direction,central_exclusion=central_exclusion,check_cancelled=checked,
            contact_target_ids=ids)
        checked();permission.consume()
        result['stage_contact_permission']=permission.proof()
        result['bypass']['ignored_collision_pair']='ACTIVE_RIGHT_GRIPPER_VS_BOUND_TARGET_ONLY'
        return result
    except BaseException:
        permission.revoke()
        raise


def _validate_short_motion(points,request,*,segment,observation_id,direction,central_exclusion=False,check_cancelled=lambda:None,contact_target_ids=None):
    if segment not in ('contact','lift'):raise ValueError('short motion stage required')
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    body=np.asarray(request['T_body_model']);world={}
    for name,box in request['compiled_scene']['cuboids'].items():
        pose=body@np.block([[_quaternion_rotation(box['pose'][3:]),np.asarray(box['pose'][:3])[:,None]],
                           [np.zeros((1,3)),np.ones((1,1))]])
        world[name]={'center_body_m':pose[:3,3].tolist(),'rotation_body':pose[:3,:3].tolist(),
                     'half_extents_m':(np.asarray(box['dims'])/2).tolist()}
    q=np.asarray(points);dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(q,q[1:])]+[q[-1:]])
    samples=[]
    for row in dense:
        check_cancelled()
        frames=arm_link_transforms(request['robot_yaml_urdf'],row);links=[]
        for name in ('link1','link2','link3','link4','link5','link6'):
            box=request['collision_model']['arm_link_boxes'][name];T=body@frames[name]
            links.append({'geometry_id':name,'center_body_m':(T[:3,:3]@np.asarray(box['center_m'])+T[:3,3]).tolist(),
                'rotation_body':T[:3,:3].tolist(),'half_extents_m':box['half_extents_m']})
        samples.append({'joints_rad':row.tolist(),'tcp_position_body_m':ik.fk(row)[:3,3].tolist(),'arm_links':links})
    bypass=validate_bypass_segment(samples,world,ContactBypassPolicy.for_manipulation_skill(
        'PICK_CONTACT_ESCAPE',observation_id,central_exclusion=central_exclusion),
        expected_direction_body=direction,joint_lower=ik.lower,joint_upper=ik.upper,expire_at_end=segment=='lift',check_cancelled=check_cancelled)
    # CONTACT_BYPASS does not inspect the active tool. Independently keep its
    # collision geometry hard against every NON-target world object.
    target_ids=list(contact_target_ids if contact_target_ids is not None else
        (request.get('motion_constraints') or {}).get('ignore_cuboid_ids',[]))
    if not target_ids or any(name not in request['compiled_scene']['cuboids'] for name in target_ids):
        raise RuntimeError('CONTACT_TARGET_IDENTITY_REQUIRED')
    import copy
    non_target=copy.deepcopy(request)
    non_target['motion_constraints']=dict(non_target.get('motion_constraints') or {},ignore_cuboid_ids=target_ids)
    from .independent_path_validation import validate_dense_world
    if request.get('contact_observed_geometry'):
        from ares_r.manipulation.observed_contact_geometry import validate_observed_contact
        non_target_validation=validate_observed_contact(points,request,world,segment=segment,
            check_cancelled=check_cancelled)
    else:
        non_target_validation=validate_dense_world(points,non_target,subdivisions=4)
    if not non_target_validation['collision_free']:raise RuntimeError('CONTACT_TOOL_NON_TARGET_WORLD_COLLISION')
    from ares_r.manipulation.task_tcp_offset import demo_local_rotation
    compensation={'demo_tcp_orientation_compensation':request.get('demo_tcp_orientation_compensation',{})}
    def physical_reference_fk(row):
        pose=ik.fk(row).copy();pose[:3,:3]=demo_local_rotation(pose[:3,:3],compensation,inverse=True);return pose
    level=validate_level_path(physical_reference_fk,q,subdivisions=4,tolerance_deg=3.)
    if not level['passed']:raise ValueError('RETIMED_HORIZONTAL_CONTRACT_FAILED')
    return {'passed':True,'bypass':bypass,'orientation':level,'dense_samples':len(dense),
            'geometry_policy':'REVALIDATED_CONTACT_SCOPE_ONLY','self_collision_checked':True,'allowed_contact_object_ids':target_ids,
            'non_target_tool_world_validation':non_target_validation}
