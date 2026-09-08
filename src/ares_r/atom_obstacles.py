"""Validated ATOM AABB handoff into an arm-local cuRobo cuboid scene."""
import json
import math
from pathlib import Path


def load_atom_obstacles(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or data.get("source")!="epic_atom":
        raise ValueError("expected schema_version=1 and source=epic_atom")
    if data.get("frame")!="body":
        raise ValueError("ATOM obstacles must be calibrated into ARES-R BODY frame")
    if not data.get("capture_time") or not data.get("calibration_revision"):
        raise ValueError("capture_time and calibration_revision are required")
    obstacles=data.get("obstacles")
    if not isinstance(obstacles,list) or not obstacles:
        raise ValueError("at least one obstacle is required")
    names=set()
    for obstacle in obstacles:
        if set(obstacle)-{"id","type","center_m","dims_m","inflation_m","confidence"}:
            raise ValueError("unsupported obstacle field")
        name=obstacle.get("id")
        if not isinstance(name,str) or not name or name in names or name=="virtual_block":
            raise ValueError("obstacle id must be unique and non-empty")
        names.add(name)
        if obstacle.get("type")!="aabb":
            raise ValueError("phase-1 route accepts AABB only; OBB is not commissioned")
        center=obstacle.get("center_m");dims=obstacle.get("dims_m")
        inflation=obstacle.get("inflation_m");confidence=obstacle.get("confidence")
        values=(center or [])+(dims or [])+[inflation,confidence]
        if len(center or [])!=3 or len(dims or [])!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
            raise ValueError("center/dims/inflation/confidence must be finite SI values")
        if min(dims)<=0 or inflation<0 or not 0<=confidence<=1:
            raise ValueError("invalid obstacle dimensions, inflation, or confidence")
    return data


def to_arm_scene(data,world,side):
    """Conservatively rotate BODY AABBs into an arm-base AABB scene."""
    if side not in ("left","right"): raise ValueError("side must be left or right")
    base=world["arms"][side];bx,by,bz=base["base_xyz_m"];yaw=float(base["base_rpy_rad"][2])
    cosine,sine=math.cos(yaw),math.sin(yaw);cuboids={}
    for obstacle in data["obstacles"]:
        x,y,z=obstacle["center_m"];dx,dy,dz=obstacle["dims_m"];pad=float(obstacle["inflation_m"])
        local_x=cosine*(x-bx)+sine*(y-by)
        local_y=-sine*(x-bx)+cosine*(y-by)
        # An enclosing arm-base AABB remains valid after rotating a BODY AABB.
        local_dx=abs(cosine)*dx+abs(sine)*dy+2*pad
        local_dy=abs(sine)*dx+abs(cosine)*dy+2*pad
        cuboids[obstacle["id"]]=dict(dims=[local_dx,local_dy,dz+2*pad],
            pose=[local_x,local_y,z-bz,1,0,0,0])
    return dict(schema_version=1,frame="urdf_base_link",source="epic_atom",
        revision="%s:%s"%(data["calibration_revision"],data["capture_time"]),
        capture_time=data["capture_time"],calibration_revision=data["calibration_revision"],
        arm=side,cuboids=cuboids)


def convert_file(source,output,world_path,side,commissioned_revisions):
    data=load_atom_obstacles(source)
    if data["calibration_revision"] not in commissioned_revisions:
        raise RuntimeError("ATOM calibration revision is not commissioned in config/system.json")
    world=json.loads(Path(world_path).read_text(encoding="utf-8"))
    scene=to_arm_scene(data,world,side)
    Path(output).write_text(json.dumps(scene,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return scene
