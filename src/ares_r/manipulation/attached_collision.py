"""One attached-object geometry contract for planner, validator and SafetyKernel."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from typing import Mapping, Sequence


def _matrix_multiply(left, right):
    return [[sum(float(left[r][k])*float(right[k][c]) for k in range(4))
             for c in range(4)] for r in range(4)]


def _pose_matrix(pose):
    w,x,y,z=(float(v) for v in pose.quaternion_wxyz)
    rotation=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
              [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
              [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    value=[rotation[0]+[pose.xyz_m[0]],rotation[1]+[pose.xyz_m[1]],
           rotation[2]+[pose.xyz_m[2]],[0,0,0,1]]
    return value


def _transform_point(matrix, point):
    return [sum(float(matrix[r][k])*float(point[k]) for k in range(3)) +
            float(matrix[r][3]) for r in range(3)]


def _rigid_inverse(matrix):
    rotation=[[float(matrix[r][c]) for c in range(3)] for r in range(3)]
    transpose=[[rotation[c][r] for c in range(3)] for r in range(3)]
    translation=[float(matrix[r][3]) for r in range(3)]
    inverse_translation=[-sum(transpose[r][k]*translation[k] for k in range(3))
                         for r in range(3)]
    return [transpose[0]+[inverse_translation[0]],transpose[1]+[inverse_translation[1]],
            transpose[2]+[inverse_translation[2]],[0,0,0,1]]


def _quaternion_wxyz(rotation):
    trace=sum(float(rotation[i][i]) for i in range(3))
    if trace > 0:
        scale=math.sqrt(trace+1.0)*2
        value=[.25*scale,(rotation[2][1]-rotation[1][2])/scale,
               (rotation[0][2]-rotation[2][0])/scale,
               (rotation[1][0]-rotation[0][1])/scale]
    else:
        index=max(range(3),key=lambda i:rotation[i][i]);j=(index+1)%3;k=(index+2)%3
        scale=math.sqrt(1+rotation[index][index]-rotation[j][j]-rotation[k][k])*2
        xyz=[0.,0.,0.];xyz[index]=.25*scale
        xyz[j]=(rotation[j][index]+rotation[index][j])/scale
        xyz[k]=(rotation[k][index]+rotation[index][k])/scale
        w=(rotation[k][j]-rotation[j][k])/scale
        value=[w]+xyz
    norm=math.sqrt(sum(item*item for item in value))
    return tuple(item/norm for item in value)


def attach_scene_object(target, T_body_tcp, *, side: str, source_revision: str):
    """Create the canonical attachment using inverse(T_body_tcp)*T_body_object."""
    from ares_r.world import AttachedObject,PoseSE3
    if target.pose.frame_id != "body":
        raise ValueError("attachment target must be in BODY")
    T_body_object=_pose_matrix(target.pose)
    T_tcp_object=_matrix_multiply(_rigid_inverse(T_body_tcp),T_body_object)
    pose=PoseSE3("tcp",tuple(float(T_tcp_object[i][3]) for i in range(3)),
                 _quaternion_wxyz([row[:3] for row in T_tcp_object[:3]]))
    return AttachedObject(target.object_id,side,pose,target,source_revision)


def build_attached_collision(attached, T_link6_tcp: Sequence[Sequence[float]],
                             inflation_m: float=.008) -> dict:
    """Conservatively enclose an object's oriented cuboid in link6 coordinates."""
    if attached.collision_geometry.geometry_type != "cuboid":
        raise ValueError("attached collision v1 supports cuboids only")
    if attached.collision_geometry.object_id != attached.object_id:
        raise ValueError("attached object and collision identity differ")
    if attached.tcp_to_object.frame_id not in ("tcp", "tool", "link6_tcp"):
        raise ValueError("tcp_to_object must be expressed in the TCP frame")
    if not 0 <= float(inflation_m) <= .05:
        raise ValueError("invalid attached-object inflation")
    T_link6_object=_matrix_multiply(T_link6_tcp,_pose_matrix(attached.tcp_to_object))
    half=[float(v)/2+float(inflation_m) for v in attached.collision_geometry.dimensions_m]
    corners=[_transform_point(T_link6_object,[sx*half[0],sy*half[1],sz*half[2]])
             for sx,sy,sz in itertools.product((-1,1),repeat=3)]
    low=[min(row[i] for row in corners) for i in range(3)]
    high=[max(row[i] for row in corners) for i in range(3)]
    box={"center_m":[(a+b)/2 for a,b in zip(low,high)],
         "dims_m":[b-a for a,b in zip(low,high)]}
    core={"schema_version":1,"object_id":attached.object_id,
          "attached_to":attached.attached_to,"source_revision":attached.source_revision,
          "source_observation_id":attached.collision_geometry.source_observation_id,
          "T_link6_object":T_link6_object,"link6_aabb":box,
          "inflation_m":float(inflation_m),
          "geometry_policy":"TCP_LOCAL_CUBOID_TO_CONSERVATIVE_LINK6_AABB_V1"}
    core["revision"]="sha256:"+hashlib.sha256(json.dumps(
        core,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return core


def verify_attached_collision(value: Mapping[str, object], expected_revision=None):
    core=dict(value);revision=core.pop("revision",None)
    actual="sha256:"+hashlib.sha256(json.dumps(
        core,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if revision != actual or (expected_revision is not None and revision != expected_revision):
        raise ValueError("attached-object collision revision mismatch")
    box=core["link6_aabb"]
    if len(box["center_m"])!=3 or len(box["dims_m"])!=3 or any(
            not math.isfinite(float(v)) or float(v)<=0 for v in box["dims_m"]):
        raise ValueError("invalid attached-object link6 AABB")
    return True


def attached_spheres_body(attached_collision, T_body_link6, sphere_builder):
    """Produce SafetyKernel samples from the exact planner attachment contract."""
    verify_attached_collision(attached_collision)
    spheres=sphere_builder(attached_collision["link6_aabb"])
    result=[]
    for sphere in spheres:
        center=_transform_point(T_body_link6,sphere["center"])
        result.append({"center_body_m":center,"radius_m":float(sphere["radius"])})
    return result
