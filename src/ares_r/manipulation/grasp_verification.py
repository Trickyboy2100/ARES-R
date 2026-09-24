"""Local pre/post scene delta plus delayed gripper-readback grasp evidence."""

from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Callable, Mapping, Sequence


def _local_voxels(points, center, radius_m, voxel_m):
    center=tuple(float(v) for v in center)
    result=set()
    for point in points:
        row=tuple(float(v) for v in point)
        if len(row)!=3 or not all(math.isfinite(v) for v in row):
            continue
        if math.sqrt(sum((a-b)**2 for a,b in zip(row,center))) <= radius_m:
            result.add(tuple(math.floor((row[i]-center[i])/voxel_m) for i in range(3)))
    return result


def local_tcp_scene_delta(before_points: Sequence[Sequence[float]],
                          after_points: Sequence[Sequence[float]],
                          tcp_center_body_m: Sequence[float], *,
                          radius_m: float=.15, voxel_m: float=.005) -> dict:
    """Compare observed occupancy only inside a bounded BODY sphere."""
    if not .10 <= float(radius_m) <= .20:
        raise ValueError("local TCP delta radius must be 10..20 cm")
    if not .002 <= float(voxel_m) <= .02:
        raise ValueError("invalid local delta voxel size")
    before=_local_voxels(before_points,tcp_center_body_m,radius_m,voxel_m)
    after=_local_voxels(after_points,tcp_center_body_m,radius_m,voxel_m)
    removed=before-after;added=after-before;shared=before&after
    core={"schema_version":1,"frame":"BODY","tcp_center_body_m":list(tcp_center_body_m),
          "radius_m":float(radius_m),"voxel_m":float(voxel_m),
          "before_voxels":len(before),"after_voxels":len(after),
          "removed_voxels":len(removed),"added_voxels":len(added),
          "shared_voxels":len(shared),
          "removed_fraction":len(removed)/max(1,len(before)),
          "added_fraction":len(added)/max(1,len(after))}
    core["revision"]="sha256:"+hashlib.sha256(json.dumps(
        core,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return core


def delayed_gripper_readback(read_position: Callable[[], int], delays_s,
                             *, sleep: Callable[[float], None]=time.sleep,
                             clock: Callable[[], float]=time.time) -> list:
    previous=0.0;result=[]
    for delay in (float(value) for value in delays_s):
        if delay < previous or delay < 0:
            raise ValueError("readback delays must be nonnegative and ordered")
        sleep(delay-previous)
        position=read_position()
        if type(position) is not int or not 0 <= position <= 1000:
            raise RuntimeError("gripper readback outside 0..1000")
        result.append({"delay_s":delay,"captured_at_unix":clock(),"position_raw":position})
        previous=delay
    if len(result)<2:
        raise ValueError("at least two delayed gripper readbacks required")
    return result


def verify_grasp_v1(scene_delta: Mapping[str, object], readbacks,
                    parameters: Mapping[str, object]) -> dict:
    cfg=parameters["grasp_verification"];positions=[int(row["position_raw"]) for row in readbacks]
    scene_pass=(int(scene_delta["removed_voxels"])>=int(cfg["minimum_removed_voxels"])
                and float(scene_delta["removed_fraction"])>=float(cfg["minimum_removed_fraction"]))
    stable=max(positions)-min(positions)<=int(cfg["maximum_readback_spread_raw"])
    closed=int(parameters["gripper"]["raw_closed"])
    hold=min(positions)>closed+int(cfg["minimum_hold_above_closed_raw"])
    gates={"LOCAL_SCENE_OBJECT_REMOVED":scene_pass,"GRIPPER_DELAYED_READBACK_STABLE":stable,
           "GRIPPER_NOT_FULLY_CLOSED":hold}
    return {"schema_version":1,"verifier_revision":parameters["revision"]+":grasp-v1",
            "result":"PASS" if all(gates.values()) else "FAIL","gates":gates,
            "local_scene_delta_revision":scene_delta["revision"],"readbacks":list(readbacks),
            "rule":"scene delta AND delayed stable non-closed gripper; neither signal passes alone"}
