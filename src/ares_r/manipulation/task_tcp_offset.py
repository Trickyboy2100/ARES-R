"""BODY-frame task-goal correction, never a controller tool/TCP calibration."""
import hashlib,json,math
import numpy as np

def validate_offset(values):
    if not isinstance(values,(list,tuple)) or len(values)!=6:
        raise ValueError('six task TCP offset values required')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):
        raise ValueError('finite numeric task TCP offsets required')
    return [float(x) for x in values]

def offset_revision(values):
    return 'sha256:'+hashlib.sha256(json.dumps(validate_offset(values),separators=(',',':')).encode()).hexdigest()

def apply_task_pose(xyz,rotation,values):
    """Add BODY XYZ; left-compose BODY-axis XYZ Euler rotation. No orbiting XYZ."""
    from scipy.spatial.transform import Rotation
    values=validate_offset(values)
    position=np.asarray(xyz,dtype=float).copy();orientation=np.asarray(rotation,dtype=float).copy()
    if any(values):
        position+=np.asarray(values[:3])
        orientation=Rotation.from_euler('xyz',values[3:]).as_matrix()@orientation
    return position,orientation

def demo_local_rotation(rotation, parameters, *, inverse=False):
    """Optional right roundtrip-only command compensation; raw data unchanged."""
    value=parameters.get('demo_tcp_orientation_compensation') or {}
    if not value.get('enabled',False):return np.asarray(rotation,dtype=float).copy()
    if (value.get('scope')!='right_arm_grasp_place_roundtrip_v1' or
            value.get('axis')!='TCP_LOCAL_Z' or
            value.get('operator_physical_level_confirmed') is not True):
        raise ValueError('invalid demo-only orientation compensation contract')
    angle=value.get('angle_deg')
    if isinstance(angle,bool) or not isinstance(angle,(int,float)) or not math.isfinite(angle) or abs(angle)>15:
        raise ValueError('invalid demo local orientation compensation')
    from scipy.spatial.transform import Rotation
    correction=Rotation.from_euler('z',(-1 if inverse else 1)*angle,degrees=True).as_matrix()
    return np.asarray(rotation,dtype=float)@correction

def validate_body_descent(points,fk,distance_m,*,tolerance_m=.003):
    rows=np.asarray(points,dtype=float)
    if rows.ndim!=2 or rows.shape[1]!=6 or len(rows)<2:raise ValueError('dense six-joint descent path required')
    dense=np.concatenate([a+(b-a)*np.arange(4)[:,None]/4 for a,b in zip(rows,rows[1:])]+[rows[-1:]])
    xyz=np.asarray([fk(q)[:3,3] for q in dense]);delta=xyz-xyz[0]
    lateral=float(np.linalg.norm(delta[:,:2],axis=1).max());down=-delta[:,2]
    if (lateral>tolerance_m or abs(float(down[-1])-distance_m)>tolerance_m or
            down.min() < -tolerance_m or down.max()>distance_m+tolerance_m or
            np.diff(down).min() < -.001):
        raise RuntimeError('PLACE_DESCENT_NOT_BODY_Z_LINEAR')
    return {'passed':True,'axis_body':[0,0,-1],'distance_m':distance_m,
        'lateral_error_m':lateral,'axial_distance_m':float(down[-1]),'tolerance_m':tolerance_m}
