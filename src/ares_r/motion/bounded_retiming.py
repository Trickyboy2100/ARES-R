"""Same-cap native retiming; geometry changes require an explicit validator."""
import math
import numpy as np
from .native_demo import native_move_violations


def local_polyline(points,dt,speed,accel,max_duration):
    """Rest at every actual corner: exact path, bounded quintic edge timing."""
    q=np.asarray(points,dtype=float);rows=[q[0].tolist()]
    for a,b in zip(q,q[1:]):
        delta=np.abs(b-a)
        if np.max(delta)<1e-14:continue
        duration=max(np.max(1.875*delta/np.asarray(speed)),math.sqrt(np.max(5.774*delta/np.asarray(accel))))*1.01
        count=max(2,math.ceil(duration/dt));t=np.arange(1,count+1)/count
        s=10*t**3-15*t**4+6*t**5
        rows.extend((a+s[:,None]*(b-a)).tolist());rows[-1]=b.tolist()
        if (len(rows)-1)*dt>max_duration:raise ValueError('local retimer duration cap')
    if len(rows)<2:rows.append(q[-1].tolist())
    if native_move_violations(rows,dt,speed,accel):raise ValueError('local retimer dynamic violation')
    return rows


def _cubic_candidate(points,dt,speed,accel,max_duration,validator):
    if validator is None:raise ValueError('geometry validator required')
    from scipy.interpolate import CubicSpline
    q=np.asarray(points,dtype=float)
    lengths=np.linalg.norm(np.diff(q,axis=0)/np.asarray(speed),axis=1)
    keep=np.r_[True,lengths>1e-12];q=q[keep]
    if len(q)<2:return [points[0],points[-1]],validator([points[0],points[-1]])
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(q,axis=0)/np.asarray(speed),axis=1))]
    spline=CubicSpline(arc/arc[-1],q,bc_type='clamped')
    grid=np.linspace(0,1,min(10001,max(1001,len(q)*8)))
    duration=max(float(np.max(np.abs(spline(grid,1))/np.asarray(speed))),
        math.sqrt(float(np.max(np.abs(spline(grid,2))/np.asarray(accel)))))*1.03
    count=max(2,math.ceil(duration/dt))
    if count*dt>max_duration:raise ValueError('cubic retimer duration cap')
    sampled=spline(np.linspace(0,1,count+1));sampled[0]=q[0];sampled[-1]=q[-1]
    if native_move_violations(sampled.tolist(),dt,speed,accel):raise ValueError('cubic retimer dynamic violation')
    proof=validator(sampled.tolist())
    if not proof.get('passed'):raise ValueError('retimed geometry rejected')
    return sampled.tolist(),proof


def cubic_verified(points,dt,speed,accel,max_duration,validator):
    if validator is None:raise ValueError('geometry validator required')
    # A fixed, small candidate set suppresses dense IK knot jitter. Each changed
    # curve passes the same independent Cartesian/pose/collision proof.
    q=np.asarray(points,dtype=float);last=None
    for count in sorted(set((min(5,len(q)),min(9,len(q)),len(q)))):
        indices=np.unique(np.rint(np.linspace(0,len(q)-1,count)).astype(int))
        try:
            rows,proof=_cubic_candidate(q[indices].tolist(),dt,speed,accel,max_duration,validator)
            return rows,dict(proof,geometry_candidate_control_points=len(indices),source_control_points=len(q))
        except (ValueError,RuntimeError) as exc:last=exc
    raise ValueError('bounded cubic candidates rejected: '+str(last))
