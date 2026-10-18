"""Corner-relative offsets; detection and TCP origins are never equated."""
import hashlib
import json
import math
import time
import numpy as np
from .perception.robot_collision import transform_xyz_rpy

AXIS_REVISION='BODY_DETECTION_AXES_2026_10_16_V1'
# Columns are detection +X/+Y/+Z expressed in BODY.
R_BODY_DETECTION=np.array([[0.,0.,1.],[-1.,0.,0.],[0.,-1.,0.]])


def offset_context(state,scene=None,now=None):
    dryer=state['dryer'];anchor=dryer.get('anchor');scene=scene or {}
    now=time.time() if now is None else now
    valid=bool(anchor and scene.get('state')=='READY'
        and anchor.get('base_pose_revision')==scene.get('base_pose_revision')
        and anchor.get('observation_epoch')==scene.get('scene_epoch')
        and 0<=now-anchor.get('captured_at_unix',0)<=300)
    rotation=(np.asarray(anchor['T_body_corner'],dtype=float)[:3,:3]
              if valid else R_BODY_DETECTION)
    context={'axis_revision':AXIS_REVISION,'canonical_offset_frame':'DETECTION',
        'R_body_detection':rotation.tolist(),
        'R_body_detection_nominal':R_BODY_DETECTION.tolist(),
        'rotation_source':'FRESH_DETECTED_ANCHOR' if valid else 'OPERATOR_FRONT_ALIGNED_CONVENTION',
        'reference_point_label':dryer.get('reference_point_label','烘干机角点参考点'),
        'anchor_revision':dryer.get('anchor_revision') if valid else None,
        'base_pose_revision':scene.get('base_pose_revision'),'scene_epoch':scene.get('scene_epoch'),
        'live_anchor_valid':valid,'detection_frame_is_tcp_frame':False,
        'orientation_offset_semantics':'RELATIVE_ROTATION_INCREMENT_NOT_ABSOLUTE_BODY_RPY'}
    context['revision']='sha256:'+hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
    return context


def _rpy(rotation):
    pitch=math.atan2(-float(rotation[2,0]),math.hypot(float(rotation[0,0]),float(rotation[1,0])))
    if math.hypot(float(rotation[0,0]),float(rotation[1,0]))>1e-10:
        return [math.atan2(float(rotation[2,1]),float(rotation[2,2])),pitch,
                math.atan2(float(rotation[1,0]),float(rotation[0,0]))]
    return [math.atan2(-float(rotation[1,2]),float(rotation[1,1])),pitch,0.]


def convert_offset(value,from_frame,to_frame,rotation=R_BODY_DETECTION):
    if from_frame not in ('BODY','DETECTION') or to_frame not in ('BODY','DETECTION'):
        raise ValueError('offset frame must be BODY or DETECTION')
    v=np.asarray(value,dtype=float);r=np.asarray(rotation,dtype=float)
    if v.shape!=(6,) or not np.isfinite(v).all():raise ValueError('six finite offset values required')
    if r.shape!=(3,3) or not np.isfinite(r).all() or not np.allclose(r.T@r,np.eye(3),atol=1e-8) or not np.isclose(np.linalg.det(r),1,atol=1e-8):
        raise ValueError('proper right-handed frame rotation required')
    if from_frame==to_frame:return v.tolist()
    basis=r if from_frame=='DETECTION' else r.T
    delta=transform_xyz_rpy(v[:3],v[3:])
    return (basis@v[:3]).tolist()+_rpy(basis@delta[:3,:3]@basis.T)
