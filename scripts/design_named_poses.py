#!/usr/bin/env python3
"""READ-ONLY IK/FK probe for the ARES-R named-pose library."""
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ares_r.adapters.jaka_sdk import build_readonly_arms, _value
from ares_r.world_geometry import base_tcp_to_world, load_world_geometry


def rpy_matrix(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
            [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]


def matmul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose(a):
    return [list(row) for row in zip(*a)]


def matrix_rpy(m):
    pitch = math.asin(max(-1.0, min(1.0, -m[2][0])))
    return [math.atan2(m[2][1], m[2][2]), pitch, math.atan2(m[1][0], m[0][0])]


def world_to_controller(base, world_pose):
    bx, by, bz = base["base_xyz_m"]
    yaw = base["base_rpy_rad"][2]
    dx, dy, dz = world_pose[0]-bx, world_pose[1]-by, world_pose[2]-bz
    c, s = math.cos(yaw), math.sin(yaw)
    xyz_mm = [1000*(c*dx+s*dy), 1000*(-s*dx+c*dy), 1000*dz]
    rotation = matmul(transpose(rpy_matrix([0, 0, yaw])), rpy_matrix(world_pose[3:]))
    return xyz_mm + matrix_rpy(rotation)


def main():
    config = json.loads(Path("config/system.json").read_text())
    world = load_world_geometry(Path(config["world_geometry_file"]))
    limits = json.loads(Path(config["motion"]["limits_file"]).read_text())
    front_rpy = [-math.pi/2, 0.0, -math.pi/2]
    targets = {
        "ready": {"left": [.38, .16, 1.20] + front_rpy,
                  "right": [.38, -.16, 1.20] + front_rpy},
        "forward": {"left": [.60, .20, 1.20] + front_rpy,
                    "right": [.60, -.20, 1.20] + front_rpy},
        "up": {"left": [.08, .20, 1.72] + front_rpy,
               "right": [.08, -.20, 1.72] + front_rpy},
        "side": {"left": [.02, .70, 1.20, -math.pi/2, 0.0, 0.0],
                 "right": [.02, -.70, 1.20, -math.pi/2, 0.0, math.pi]},
    }
    arms = build_readonly_arms(config["jaka"])
    report = {"motion_api_called": False, "poses": {"zero": {}}}
    try:
        # Avoid get_robot_status(): the site SDK occasionally raises a
        # UnicodeDecodeError while decoding its textual status field.  The
        # pose-design probe needs only the numeric joint-position API.
        current = {
            side: {"joint_position_rad": list(_value(
                arm.robot.get_joint_position(), side + " joint position"))}
            for side, arm in arms.items()
        }
        for side, arm in arms.items():
            zero_tcp = list(_value(arm.robot.kine_forward([0.0]*6), side+" zero FK"))
            report["poses"]["zero"][side] = {
                "joint_rad": [0.0]*6,
                "controller_tcp_mm_rad": zero_tcp,
                "body_tcp_m_rad": base_tcp_to_world(world["arms"][side], zero_tcp),
            }
        for name, sides in targets.items():
            report["poses"][name] = {}
            for side, world_pose in sides.items():
                controller_pose = world_to_controller(world["arms"][side], world_pose)
                result = arm.robot.kine_inverse(current[side]["joint_position_rad"], controller_pose)
                row = {"requested_body_tcp_m_rad": world_pose,
                       "controller_tcp_request_mm_rad": controller_pose,
                       "ik_return": list(result) if isinstance(result, (tuple, list)) else result}
                if isinstance(result, (tuple, list)) and result and int(result[0]) == 0:
                    q = list(result[1])
                    actual = list(_value(arm.robot.kine_forward(q), side+" candidate FK"))
                    body = base_tcp_to_world(world["arms"][side], actual)
                    margin = limits["soft_limit_margin_rad"]
                    row.update(joint_rad=q, body_tcp_m_rad=body,
                        max_tcp_error_mm=1000*max(abs(a-b) for a,b in zip(body[:3],world_pose[:3])),
                        soft_limits_ok=all(lo+margin < v < hi-margin for v,lo,hi in zip(
                            q,limits["lower_rad"],limits["upper_rad"])),
                        center_zone_ok=body[1] > .07 if side == "left" else body[1] < -.07)
                    # Controller MoveJ interpolates in joint space. Sample the assumed
                    # straight joint path only as a rejection test, never as certification.
                    start = current[side]["joint_position_rad"]
                    ys=[]
                    for index in range(101):
                        t=index/100
                        sample=[a+(b-a)*t for a,b in zip(start,q)]
                        sample_tcp=list(_value(arm.robot.kine_forward(sample),side+" sampled FK"))
                        ys.append(base_tcp_to_world(world["arms"][side],sample_tcp)[1])
                    row["sampled_movej_body_y_range_m"]=[min(ys),max(ys)]
                    row["sampled_center_zone_clear_after_start"] = all(
                        y > .07 for y in ys[1:]) if side == "left" else all(y < -.07 for y in ys[1:])
                    if name == "ready" and side == "right":
                        row["sampled_monotonic_exit"] = all(b <= a+1e-6 for a,b in zip(ys,ys[1:]))
                report["poses"][name][side] = row
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for arm in arms.values():
            arm.close()


if __name__ == "__main__":
    main()
