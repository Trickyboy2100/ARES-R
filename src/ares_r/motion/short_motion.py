"""Shared dense checks for contact/lift geometry changed by native retiming."""
import numpy as np
from ares_r.manipulation.contact_bypass import ContactBypassPolicy,validate_bypass_segment
from ares_r.perception.robot_collision import arm_link_transforms
from .runtime_goal_ik import RuntimeGoalIK
from .tcp_orientation import validate_level_path
from .independent_path_validation import _quaternion_rotation


def validate_short_motion(points,request,*,segment,observation_id,direction,central_exclusion=False,check_cancelled=lambda:None,contact_target_ids=None):
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
    non_target_validation=validate_dense_world(points,non_target,subdivisions=4)
    if not non_target_validation['collision_free']:raise RuntimeError('CONTACT_TOOL_NON_TARGET_WORLD_COLLISION')
    level=validate_level_path(ik.fk,q,subdivisions=4,tolerance_deg=3.)
    if not level['passed']:raise ValueError('RETIMED_HORIZONTAL_CONTRACT_FAILED')
    return {'passed':True,'bypass':bypass,'orientation':level,'dense_samples':len(dense),
            'geometry_policy':'REVALIDATED_CONTACT_SCOPE_ONLY','self_collision_checked':True,'allowed_contact_object_ids':target_ids,
            'non_target_tool_world_validation':non_target_validation}
