"""Isolated EpicEye SDK capture and dependency-free binary PLY audit."""
import hashlib
import json
import math
import re
import struct
import subprocess
import time
import uuid
from pathlib import Path


def inspect_ply(path):
    path=Path(path);header=[]
    with path.open("rb") as stream:
        for _ in range(128):
            line=stream.readline()
            if not line: raise ValueError("truncated PLY header")
            header.append(line)
            if line==b"end_header\n": break
        else: raise ValueError("PLY header too long")
        text=b"".join(header).decode("ascii")
        if "format binary_little_endian 1.0" not in text: raise ValueError("binary little-endian PLY required")
        match=re.search(r"^element vertex (\d+)$",text,re.MULTILINE)
        if not match: raise ValueError("PLY vertex count missing")
        count=int(match.group(1));expected=("property float x","property float y","property float z",
            "property uchar red","property uchar green","property uchar blue")
        if not all(item in text for item in expected): raise ValueError("expected XYZ float32 + RGB uint8 PLY")
        record=struct.Struct("<fffBBB");valid=0;mins=[math.inf]*3;maxs=[-math.inf]*3
        min_distance=math.inf;max_distance=0.0
        records_read=0
        while records_read<count:
            amount=min(65536,count-records_read)
            data=stream.read(record.size*amount)
            if not data: break
            if len(data)%record.size: raise ValueError("misaligned PLY payload")
            records_read+=len(data)//record.size
            for x,y,z,_,_,_ in struct.iter_unpack("<fffBBB",data):
                count_values=(x,y,z)
                if not all(math.isfinite(v) for v in count_values) or not any(v!=0 for v in count_values): continue
                valid+=1
                for i,value in enumerate(count_values): mins[i]=min(mins[i],value);maxs[i]=max(maxs[i],value)
                distance=math.sqrt(x*x+y*y+z*z);min_distance=min(min_distance,distance);max_distance=max(max_distance,distance)
        payload_bytes=path.stat().st_size-sum(len(line) for line in header)
    if payload_bytes!=count*record.size: raise ValueError("PLY payload size does not match vertex count")
    if not valid: raise ValueError("PLY contains no valid XYZ points")
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): digest.update(block)
    return dict(path=str(path.resolve()),format="binary_little_endian_xyz_f32_rgb_u8",width=_header_int(text,"num_cols"),
        height=_header_int(text,"num_rows"),vertex_count=count,valid_point_count=valid,
        valid_ratio=valid/count,source_coordinate_unit="mm",xyz_min_mm=mins,xyz_max_mm=maxs,
        xyz_min_m=[v/1000 for v in mins],xyz_max_m=[v/1000 for v in maxs],
        distance_range_mm=[min_distance,max_distance],unit_conversion_to_curobo_m=0.001,
        unit_plausible=100<=min_distance<=10000 and max_distance<=20000,
        bytes=path.stat().st_size,sha256=digest.hexdigest())


def _header_int(text,key):
    match=re.search(r"^obj_info %s (\d+)$"%re.escape(key),text,re.MULTILINE)
    return int(match.group(1)) if match else None


def planning_assessment(stats,config):
    pc=config["epic_pointcloud"];transform=pc.get("T_body_camera")
    calibrated=(isinstance(transform,list) and len(transform)==4 and all(isinstance(row,list) and len(row)==4 for row in transform))
    quality=stats["valid_ratio"]>=float(pc.get("minimum_valid_ratio",.5)) and stats["unit_plausible"]
    blockers=[]
    if not quality: blockers.append("pointcloud quality/unit plausibility gate failed")
    if not calibrated: blockers.append("T_body_camera is not commissioned")
    blockers.extend(["robot/tool self-filter is not commissioned","ground/ROI filtering is not commissioned",
        "pointcloud-to-inflated-cuboid conversion is not commissioned"])
    return dict(raw_pointcloud_direct_to_curobo=False,static_stop_plan_execute_route_feasible=True,
        current_planning_ready=False,quality_gate_passed=quality,camera_to_body_calibrated=calibrated,
        proposed_route=["Epic capture (mm)","remove invalid points","mm -> m","T_body_camera transform",
            "crop ROI/ground","remove robot and held tool","voxel downsample + cluster","inflate AABB/OBB",
            "transform BODY -> right URDF base","cuRobo update_world/plan","freeze scene during execution"],blockers=blockers)


def capture(config):
    pc=config["epic_pointcloud"];python=Path(pc["python"]);script=Path(pc["capture_script"])
    if pc.get("source_coordinate_unit")!="mm":
        raise RuntimeError("Epic capture source unit must be explicitly configured as mm")
    if not python.is_file() or not script.is_file(): raise RuntimeError("EpicEye SDK environment unavailable on this host")
    root=Path(config["logging"]["directory"])/"epic_captures"
    directory=root/(time.strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:8]);directory.mkdir(parents=True,exist_ok=False)
    started=time.time();result=subprocess.run([str(python),str(script),str(pc["endpoint"])],cwd=str(directory),
        capture_output=True,text=True,timeout=float(pc.get("timeout_s",120)))
    (directory/"capture.log").write_text(result.stdout+result.stderr,encoding="utf-8")
    if result.returncode: raise RuntimeError("Epic pointcloud capture failed; inspect %s"%(directory/"capture.log"))
    cloud=directory/"pointcloud.ply"
    if not cloud.is_file(): raise RuntimeError("capture returned without pointcloud.ply")
    stats=inspect_ply(cloud);frame=re.search(r"frameID:\s*(\S+)",result.stdout)
    manifest=dict(schema_version=1,captured_at_unix=started,elapsed_s=time.time()-started,
        endpoint=pc["endpoint"],frame_id=frame.group(1) if frame else None,
        coordinate_frame="Epic depth/pointcloud camera",stats=stats,
        artifacts={p.name:p.stat().st_size for p in directory.iterdir() if p.is_file()},
        planning=planning_assessment(stats,config))
    path=directory/"manifest.json";path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return path
