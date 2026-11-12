"""Versioned BODY-frame named-pose definitions and strict read-only validation."""
import json, math
from pathlib import Path

VALID_STATES={"design_target_uncommissioned","endpoint_verified_readonly_path_not_verified","commissioned"}

def load_named_poses(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!=1 or data.get("authoritative_frame")!="body": raise ValueError("named-pose schema/frame mismatch")
    poses=data.get("poses")
    if not isinstance(poses,dict) or not poses: raise ValueError("named poses must not be empty")
    for name,pose in poses.items():
        if pose.get("commissioning") not in VALID_STATES: raise ValueError("%s commissioning state invalid"%name)
        if set(pose.get("arms",{}))!={"left","right"}: raise ValueError("%s must define both arms"%name)
        for side,target in pose["arms"].items():
            keys=set(target)&{"joint_rad","body_tcp_target_m_rad"}
            if len(keys)!=1: raise ValueError("%s/%s needs exactly one authoritative target"%(name,side))
            values=target[next(iter(keys))]
            if len(values)!=6 or not all(math.isfinite(float(v)) for v in values): raise ValueError("%s/%s target invalid"%(name,side))
    return data

def pose_report(library,name=None,side=None):
    if name is None: return "\n".join("%-10s %s"%(k,v["commissioning"]) for k,v in library["poses"].items())
    if name not in library["poses"]: raise ValueError("unknown pose: "+name)
    pose=library["poses"][name]; arms=[side] if side else ["left","right"]
    if side not in (None,"left","right"): raise ValueError("arm must be left or right")
    lines=["POSE %s  state=%s"%(name,pose["commissioning"]),pose["description"]]
    for arm in arms: lines.append("%s: %s"%(arm,json.dumps(pose["arms"][arm],ensure_ascii=False)))
    if pose["commissioning"]!="commissioned": lines.append("EXECUTION BLOCKED: endpoint/path has not completed commissioning.")
    return "\n".join(lines)
