"""Offline migration of recorded tmp waypoints into a stable, unit-safe contract.

Spline geometry adapted from tmp/make_spline_traj.py (see provenance document).
Not a cuRobo replacement, not collision-certified, and never an execution API.
"""
import json
import math
from pathlib import Path
from .curobo import ARM_NAMES,finite_joints


def load_waypoints(path):
    data=json.loads(Path(path).read_text())
    if data.get("arm") not in ("left","right"): raise ValueError("explicit arm required")
    if tuple(data.get("joint_names",[])) not in (ARM_NAMES,tuple("J%d"%i for i in range(1,7))):
        raise ValueError("unexpected joint order")
    rad=data.get("waypoints_rad")
    deg=data.get("waypoints_deg")
    if rad is None and deg is None: raise ValueError("explicit rad/deg field required")
    points=[finite_joints(q) for q in rad] if rad is not None else [finite_joints([math.radians(v) for v in q]) for q in deg]
    if len(points)<2: raise ValueError("at least two waypoints required")
    if deg is not None:
        degrees=[finite_joints(q) for q in deg]
        if len(points)!=len(degrees) or any(abs(a-math.radians(b))>1e-5 for q,d in zip(points,degrees) for a,b in zip(q,d)):
            raise ValueError("rad/deg fields disagree")
    return dict(schema_version=1,arm=data["arm"],joint_names=list(ARM_NAMES),waypoints_rad=points)


def catmull_rom(p0,p1,p2,p3,t,alpha=.5):
    """Centripetal Catmull-Rom, preserving geometry without joint-limit clipping."""
    def distance(a,b): return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
    if distance(p0,p1)<1e-12 and distance(p1,p2)<1e-12: return list(p2)
    t0=0.;t1=distance(p0,p1)**alpha;t2=t1+distance(p1,p2)**alpha;t3=t2+distance(p2,p3)**alpha
    u=t1+(t2-t1)*t
    def lerp(a,b,ta,tb):
        if abs(tb-ta)<1e-12:return list(a)
        f=(u-ta)/(tb-ta)
        return [x+(y-x)*f for x,y in zip(a,b)]
    a1=lerp(p0,p1,t0,t1);a2=lerp(p1,p2,t1,t2);a3=lerp(p2,p3,t2,t3)
    return lerp(lerp(a1,a2,t0,t2),lerp(a2,a3,t1,t3),t1,t2)


def export_geometry(source,output,limits,subdivisions=100):
    data=load_waypoints(source);wps=data["waypoints_rad"]
    points=[]
    for i in range(len(wps)-1):
        points.extend(catmull_rom(wps[max(0,i-1)],wps[i],wps[i+1],wps[min(len(wps)-1,i+2)],k/subdivisions)
                      for k in range(subdivisions))
    points.append(wps[-1])
    for p in points:
        finite_joints(p)
        if any(v<lo+limits.soft_limit_margin_rad or v>hi-limits.soft_limit_margin_rad for v,lo,hi in zip(p,limits.lower_rad,limits.upper_rad)):
            raise ValueError("spline crosses soft limit; rejected, never clipped")
    # Deliberately NOT Trajectory schema: no timing, collision certificate or execution route.
    data.update(kind="offline_waypoint_geometry",collision_checked=False,geometry_rad=points,
                warning="offline spline only; cuRobo planning and all execution gates remain required")
    with Path(output).open("x") as stream: json.dump(data,stream,indent=2)
    return Path(output)
