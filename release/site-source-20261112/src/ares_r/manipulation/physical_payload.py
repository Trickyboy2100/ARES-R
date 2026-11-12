"""Measured task payloads, independent of a possibly merged perception cluster.

No inference of dimensions or grasp anchoring from the observed cluster is
allowed here. This module builds geometry only and cannot execute a motion.
"""
import hashlib,json
import numpy as np
from .attached_collision import build_attached_collision
from .attached_world import seal,bind_owned_points,inside_boxes
from ares_r.world import AttachedObject,PoseSE3,SceneObject,SceneObjectRole
from ares_r.world.scene_compiler import _quaternion_wxyz

DEMO_PAYLOAD_POLICY = "DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2"


def prepare_task_payload(legacy, policy=None, **context):
    """Opt-in formal package hook. Legacy/golden defaults remain byte-equivalent."""
    if policy is None:
        return legacy
    if policy != DEMO_PAYLOAD_POLICY:
        raise ValueError("unknown task payload policy")
    return demo_exposed_payload_override(legacy, **context)


def _rigid(value,name):
    try:t=np.asarray(value,dtype=float)
    except (TypeError,ValueError) as exc:raise ValueError(name+' required') from exc
    if (t.shape!=(4,4) or not np.isfinite(t).all() or not np.allclose(t[3],[0,0,0,1],atol=1e-8)
            or not np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-6)
            or not np.isclose(np.linalg.det(t[:3,:3]),1.,atol=1e-6)):
        raise ValueError(name+' requires a measured rigid transform')
    return t


def validate_profile(profile):
    if profile.get('schema_version')!=1 or profile.get('geometry_source')!='OPERATOR_PHYSICAL_OBJECT':
        raise ValueError('explicit physical-object profile required')
    raw=profile.get('dimensions_m')
    if not isinstance(raw,(list,tuple)) or len(raw)!=3 or any(v is None for v in raw):
        raise ValueError('PHYSICAL_PAYLOAD_THICKNESS_OR_DIMENSIONS_REQUIRED')
    dims=np.asarray(raw,dtype=float)
    if not np.isfinite(dims).all() or np.any(dims<=0) or np.any(dims>1.):
        raise ValueError('invalid measured object dimensions')
    if profile.get('T_tcp_object') is None:raise ValueError('PHYSICAL_PAYLOAD_GRASP_ANCHOR_REQUIRED')
    local=_rigid(profile['T_tcp_object'],'T_tcp_object')
    padding=float(profile.get('inflation_m',.004))
    if not 0<=padding<=.05:raise ValueError('invalid payload padding')
    if not profile.get('revision'):raise ValueError('physical profile revision required')
    return dims,local,padding


def build_physical_attachment(profile, *, object_id, observation_id, T_body_tcp,T_link6_tcp,
                              points_body,pointcloud_sha256,protected_boxes=()):
    dims,local,padding=validate_profile(profile)
    body_tcp=_rigid(T_body_tcp,'T_body_tcp');tool=_rigid(T_link6_tcp,'T_link6_tcp')
    body=body_tcp@local
    geometry=SceneObject(object_id,SceneObjectRole.TARGET,'cuboid',
        PoseSE3('body',tuple(body[:3,3]),tuple(_quaternion_wxyz(body[:3,:3]))),
        tuple(dims),0.,observation_id)
    attached=AttachedObject(object_id,'right',
        PoseSE3('tcp',tuple(local[:3,3]),tuple(_quaternion_wxyz(local[:3,:3]))),geometry,profile['revision'])
    result=build_attached_collision(attached,tool.tolist(),inflation_m=padding)
    # Source samples establish ownership only INSIDE the physical object;
    # they never enlarge it. Protected support/structure samples stay protected.
    points=np.asarray(points_body,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():
        raise ValueError('finite observed payload source points required')
    member=np.all(np.abs((points-body[:3,3])@body[:3,:3])<=dims/2+1e-9,axis=1)
    member&=~inside_boxes(points,protected_boxes)
    if not member.any():raise RuntimeError('PHYSICAL_PAYLOAD_NO_SOURCE_POINT_BINDING')
    result=bind_owned_points(result,points[member],body_tcp@np.linalg.inv(tool),pointcloud_sha256=pointcloud_sha256)
    result['physical_model_provenance']={
        'profile_revision':profile['revision'],'geometry_source':profile['geometry_source'],
        'profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        'perception_cluster_defines_dimensions':False,'whole_object_included':True,
        'source_points_considered':len(points),'source_points_bound':int(member.sum())}
    return seal(result)


def demo_exposed_payload_override(legacy, *, T_body_grasp_tcp,T_body_grasp_link6,
                                  points_body,pointcloud_sha256,protected_boxes=(),
                                  reanchor_from_grasp=False):
    """Operator-sized Demo payload: exposed160x100, original height retained.

    Rear20mm remains explicitly represented in the common collision enclosure;
    it is NOT silently cut out merely because the fingers clamp it. The grasp
    reference and the old object's lateral/vertical alignment are preserved.
    Historical source artifacts and source dimensions are not overwritten.
    """
    from .attached_collision import verify_attached_collision
    verify_attached_collision(legacy)
    tcp=_rigid(T_body_grasp_tcp,'T_body_grasp_tcp')
    link=_rigid(T_body_grasp_link6,'T_body_grasp_link6')
    old=link@_rigid(legacy['T_link6_object'],'T_link6_object')
    rotation=old[:3,:3]
    grasp_local=rotation.T@(tcp[:3,3]-old[:3,3])
    exposed=old.copy()
    # Object +X denotes its longitudinal direction. Only that center is
    # reanchored; lateral and vertical center coordinates remain unchanged.
    if reanchor_from_grasp:
        exposed[:3,3]=tcp[:3,3]+rotation@np.array([.080,-grasp_local[1],-grasp_local[2]])
    clamped=exposed.copy();clamped[:3,3]=exposed[:3,3]-rotation[:,0]*.090
    height=float(legacy['object_dimensions_m'][2]);padding=float(legacy['inflation_m'])
    dims=np.array([.160,.100,height]);clamp_dims=np.array([.020,.100,height])
    to_link=np.linalg.inv(link)
    local=to_link@exposed;local_clamp=to_link@clamped
    result=dict(legacy)
    result.update(T_link6_object=local.tolist(),object_dimensions_m=dims.tolist())
    signs=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])
    corners=[]
    for transform,size in ((local,dims),(local_clamp,clamp_dims)):
        corners.extend((signs*(size/2+padding))@transform[:3,:3].T+transform[:3,3])
    lo,hi=np.min(corners,axis=0),np.max(corners,axis=0)
    result['link6_aabb']={'center_m':((lo+hi)/2).tolist(),'dims_m':(hi-lo).tolist(),
                          'half_extents_m':((hi-lo)/2).tolist()}
    result['clamped_segment']={'T_link6_object':local_clamp.tolist(),'dimensions_m':clamp_dims.tolist(),
                               'included_in_shared_collision_enclosure':True}
    result['geometry_policy']='DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2'
    result['physical_model_provenance']={
        'scope':'RIGHT_GRASP_PLACE_ROUNDTRIP_ONLY','operator_exposed_length_m':.160,
        'operator_width_m':.100,'operator_grasp_distance_from_rear_m':.020,
        'height_policy':'UNCHANGED_FROM_SOURCE','source_height_m':height,
        'original_attachment_revision':legacy['revision'],
        'original_dimensions_m':legacy['object_dimensions_m'],
        'source_cluster_does_not_define_length_or_width':True,
        'source_center_and_rotation_preserved':not reanchor_from_grasp,
        'grasp_anchor_translation_applied':reanchor_from_grasp,
        'longitudinal_axis':'SOURCE_OBJECT_POSITIVE_X_AT_GRASP',
        'physical_motion_authorized':False}
    result.pop('point_ownership',None)
    result=seal(result)
    points=np.asarray(points_body,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('finite source points required')
    member=np.zeros(len(points),dtype=bool)
    for transform,size in ((exposed,dims),(clamped,clamp_dims)):
        member|=np.all(np.abs((points-transform[:3,3])@transform[:3,:3])<=size/2+1e-9,axis=1)
    member&=~inside_boxes(points,protected_boxes)
    if not member.any():raise RuntimeError('PHYSICAL_PAYLOAD_NO_SOURCE_POINT_BINDING')
    return bind_owned_points(result,points[member],link,pointcloud_sha256=pointcloud_sha256)
