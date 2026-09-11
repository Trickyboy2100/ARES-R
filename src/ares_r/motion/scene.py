"""Legacy V1 manual-scene boundary; perception must enter via WorldModel."""
import hashlib
import json
import math
from pathlib import Path


def load_scene(config):
    path=config.get("motion",{}).get("scene_file")
    data=json.loads(Path(path).read_text()) if path else dict(schema_version=1,
        frame="urdf_base_link",source="manual",revision="empty-v1",cuboids={})
    scene_cuboids(data)
    data["digest"]=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!="digest"},sort_keys=True).encode()).hexdigest()
    return data


def scene_cuboids(data):
    source=data.get("source")
    if source=="epic_atom":
        raise ValueError("Epic/ATOM -> cuRobo direct loading is forbidden; register an ObservationEpoch in WorldModel (W4/W6 pending)")
    if data.get("schema_version")!=1 or data.get("frame")!="urdf_base_link" or source!="manual" or not data.get("revision"):
        raise ValueError("legacy V1 accepts explicit manual scenes in urdf_base_link only")
    allowed={"schema_version","frame","source","revision","cuboids","digest"}
    if set(data)-allowed:
        raise ValueError("unsupported scene fields; pointclouds are never silently ignored")
    output={}
    for name,box in data["cuboids"].items():
        if name=="virtual_block": raise ValueError("reserved obstacle name")
        dims=box["dims"];pose=box["pose"]
        if len(dims)!=3 or len(pose)!=7 or not all(math.isfinite(v) for v in dims+pose) or min(dims)<=0:
            raise ValueError("invalid cuboid geometry")
        if pose[3:]!=[1,0,0,0]: raise ValueError("only axis-aligned cuboids currently supported")
        output[name]=dict(dims=list(dims),pose=list(pose))
    return output
