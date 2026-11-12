"""Payload identity and point ownership shared by live and replay scenes.

Only source-observed payload samples may own points. Nearby support/structure
always wins over payload attribution. There is no TCP-radius blanket deletion.
"""
import hashlib
import json
import numpy as np
from .attached_collision import verify_attached_collision


def seal(value):
    core=dict(value);core.pop('revision',None)
    return dict(core,revision='sha256:'+hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest())


def bind_owned_points(attached, points_body, T_body_link6, *, pointcloud_sha256, voxel_m=.004):
    verify_attached_collision(attached)
    points=np.asarray(points_body,dtype=float).reshape(-1,3)
    if not len(points) or not np.isfinite(points).all():raise ValueError('observed payload samples required')
    transform=np.asarray(T_body_link6,dtype=float)
    local=(points-transform[:3,3])@transform[:3,:3]
    _,indices=np.unique(np.floor(local/voxel_m).astype(np.int64),axis=0,return_index=True)
    if len(indices)>8192:raise ValueError('payload ownership sample budget exceeded')
    core=dict(attached);core['point_ownership']={'policy':'SOURCE_OBSERVED_PAYLOAD_V1',
        'object_id':attached['object_id'],'source_observation_id':attached['source_observation_id'],
        'source_pointcloud_sha256':str(pointcloud_sha256),'points_link6_m':local[indices].tolist(),
        'matching_distance_m':.006}
    return seal(core)


def inside_boxes(points,boxes):
    protected=np.zeros(len(points),dtype=bool)
    for box in boxes:
        if 'observed_bounds_m' in box:
            lo,hi=np.asarray(box['observed_bounds_m'],dtype=float)
            protected|=np.all((points>=lo-.002)&(points<=hi+.002),axis=1)
        else:
            center=np.asarray(box.get('center_body_m',box.get('center_m')),dtype=float)
            rotation=np.asarray(box.get('rotation_body',np.eye(3)),dtype=float)
            half=np.asarray(box['half_extents_m'] if 'half_extents_m' in box else np.asarray(box['dims_m'])/2,dtype=float)
            protected|=np.all(np.abs((points-center)@rotation)<=half+.002,axis=1)
    return protected


def filter_attached_points(points_body,attached,T_body_link6,protected_boxes=()):
    verify_attached_collision(attached)
    points=np.asarray(points_body,dtype=float).reshape(-1,3)
    ownership=attached.get('point_ownership') or {}
    if ownership.get('policy')!='SOURCE_OBSERVED_PAYLOAD_V1' or ownership.get('object_id')!=attached['object_id']:
        raise RuntimeError('ATTACHMENT_OWNERSHIP_TEMPLATE_REQUIRED')
    samples=np.asarray(ownership['points_link6_m'],dtype=float)
    radius=float(ownership['matching_distance_m'])
    if samples.ndim!=2 or samples.shape[1]!=3 or not 1<=len(samples)<=8192 or not np.isfinite(samples).all() or not 0<radius<=.01:
        raise ValueError('invalid bounded payload ownership')
    from scipy.spatial import cKDTree
    transform=np.asarray(T_body_link6,dtype=float)
    local=(points-transform[:3,3])@transform[:3,:3]
    distance,_=cKDTree(samples).query(local,distance_upper_bound=radius)
    candidate=np.isfinite(distance);protected=inside_boxes(points,protected_boxes)
    remove=candidate&~protected
    return ~remove,{'object_id':attached['object_id'],'attachment_revision':attached['revision'],
        'policy':ownership['policy'],'input_points':len(points),'removed_points':int(remove.sum()),
        'protected_points':int(protected.sum()),'ambiguous_preserved':int((candidate&protected).sum()),
        'removed_indices':np.flatnonzero(remove).tolist(),'retained_points':int((~remove).sum())}


def verify_world_identity(compiled,attached):
    if attached is None:
        if compiled.get('attached_object_revision'):raise RuntimeError('SCENE_ATTACHMENT_STATE_MISMATCH')
        return
    verify_attached_collision(attached)
    if compiled.get('attached_object_revision')!=attached['revision']:
        raise RuntimeError('SCENE_ATTACHMENT_REVISION_MISMATCH')
    # Only the exact stable identity may be absent. Prefix deletion is forbidden.
    if attached['object_id'] in compiled['cuboids']:
        raise RuntimeError('DUPLICATE_ATTACHED_WORLD_OBJECT')


def snapshot_attachment(attached,T_link6_tcp,T_body_link6):
    from ares_r.world import AttachedObject,PoseSE3,SceneObject,SceneObjectRole
    from ares_r.world.scene_compiler import _quaternion_wxyz
    verify_attached_collision(attached)
    local=np.linalg.inv(np.asarray(T_link6_tcp))@np.asarray(attached['T_link6_object'])
    body=np.asarray(T_body_link6)@np.asarray(attached['T_link6_object'])
    shape=SceneObject(attached['object_id'],SceneObjectRole.TARGET,'cuboid',
        PoseSE3('body',tuple(body[:3,3]),tuple(_quaternion_wxyz(body[:3,:3]))),
        tuple(attached['object_dimensions_m']),0.,attached['source_observation_id'])
    return AttachedObject(attached['object_id'],attached['attached_to'],
        PoseSE3('tcp',tuple(local[:3,3]),tuple(_quaternion_wxyz(local[:3,:3]))),shape,attached['revision'])
