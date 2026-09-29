#!/usr/bin/env python3
"""Turn a hand-dragged tuck pose into a precise, level-preserving target.

The drag is a human's intent but not a precise pose: on 2026-09-28 it arrived
~3 deg off level.  This script regularises it without changing where the arm was
put:

* BODY height -> the contract shoulder height (1.20 m);
* tool Z -> BODY +Y (straight left), i.e. horizontal;
* tool roll/pitch -> exactly level.

Why that orientation is the level-preserving one
------------------------------------------------
A held object's orientation relative to the TCP is fixed by the grip.  Its
up-axis in the tool frame is therefore

    u_tool = R_grasp^T * z_body

and the object's tilt at any later pose is ``angle(R(t) * u_tool, z_body)``.
For the 2026-09-24 pick, R_grasp has tool Z = BODY +X and tool Y = BODY +Z, so
``u_tool = tool Y``: **the object is upright exactly when the tool's Y axis
points along BODY +Z.**

The regularised orientation is ``Rz(+90 deg) * R_grasp``: tool X = -BODY X,
tool Y = BODY +Z, tool Z = BODY +Y.  A pure yaw about the vertical cannot tilt
anything, so this satisfies "tool Z points left" and "the tray stays level"
simultaneously -- and it is the only orientation that does both.

Caveat, stated plainly: "u_tool = tool Y" rests on the object having been level
at the moment of grasp.  If the object was already tilted then, every tilt figure
here is offset by that same amount (the *changes* remain correct).
"""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ares_r.motion.grasp import rotation_matrix
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK

import place_ik_probe

#: Regularised BODY orientation: tool X = -BODY X, tool Y = BODY +Z, tool Z = BODY +Y.
REGULAR_BODY_ROTATION = np.asarray([[-1.0, 0.0, 0.0],
                                    [0.0, 0.0, 1.0],
                                    [0.0, 1.0, 0.0]])
#: The same rotation as ZYX (roll, pitch, yaw) in radians: pitch 0 = tool Z horizontal.
REGULAR_BODY_RPY = [math.pi / 2.0, 0.0, math.pi]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def zyx_to_matrix(roll, pitch, yaw):
    return np.asarray(rotation_matrix(roll, pitch, yaw), dtype=float)


def matrix_to_zyx(matrix):
    """Inverse of ``rotation_matrix`` for R = Rz(yaw) * Ry(pitch) * Rx(roll)."""
    pitch = math.asin(max(-1.0, min(1.0, -float(matrix[2][0]))))
    if abs(math.cos(pitch)) < 1e-9:
        roll, yaw = 0.0, math.atan2(-float(matrix[0][1]), float(matrix[1][1]))
    else:
        roll = math.atan2(float(matrix[2][1]), float(matrix[2][2]))
        yaw = math.atan2(float(matrix[1][0]), float(matrix[0][0]))
    return [roll, pitch, yaw]


def tilt_deg(rotation, up_tool=(0.0, 1.0, 0.0)):
    """Angle between the object's up-axis and BODY +Z, given the TCP rotation."""
    axis = np.asarray(rotation, dtype=float) @ np.asarray(up_tool, dtype=float)
    axis = axis / float(np.linalg.norm(axis))
    return math.degrees(math.acos(max(-1.0, min(1.0, float(axis[2])))))


def body_to_controller_pose(body_m, body_rpy, arm):
    bx, by, bz = (float(v) for v in arm["base_xyz_m"])
    yaw_b = float(arm["base_rpy_rad"][2])
    cosine, sine = math.cos(yaw_b), math.sin(yaw_b)
    dx, dy = body_m[0] - bx, body_m[1] - by
    x = cosine * dx + sine * dy
    y = -sine * dx + cosine * dy
    z = body_m[2] - bz
    roll, pitch, yaw = body_rpy
    return [x, y, z, roll, pitch, yaw - yaw_b]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--teach", type=Path, required=True,
                        help="directory holding visibility_clear_pose.json")
    parser.add_argument("--template-plan", type=Path, required=True)
    parser.add_argument("--height-m", type=float, default=None,
                        help="regularised BODY height; defaults to the contract target_z_m")
    parser.add_argument("--radius-m", type=float, default=None,
                        help="override the dragged horizontal radius; the contract band is "
                             "0.35-0.60 m and the dragged 0.295 m sits inside it")
    parser.add_argument("--azimuth-deg", type=float, default=None,
                        help="override the dragged azimuth; the contract value is "
                             "body_azimuth_deg")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output directory already exists: %s" % args.output)
    args.output.mkdir(parents=True)

    record = load(args.teach / "visibility_clear_pose.json")
    parameters = load(ROOT / "config/tray_to_groove_v2.json")
    contract = parameters["visibility_clear"]
    height = float(contract["target_z_m"] if args.height_m is None else args.height_m)
    arm = load(ROOT / "config/robot_world.json")["arms"]["right"]
    template = load(args.template_plan / "planner_request.json")

    dragged_body = [float(v) for v in record["tcp_body_m"]]
    dragged_rpy = [float(v) for v in record["controller_tool_pose_mm_rad"][3:]]
    dragged_body_rpy = list(dragged_rpy)
    dragged_body_rpy[2] += float(arm["base_rpy_rad"][2])

    # Horizontal placement: keep what the human dragged unless a radius and/or
    # azimuth override is given.  The tuck only has to sit in the contract band
    # (0.35-0.60 m from the body centre) so the arm is not folded into itself.
    dragged_radius = math.hypot(dragged_body[0], dragged_body[1])
    dragged_azimuth = math.degrees(math.atan2(dragged_body[1], dragged_body[0]))
    radius_used = dragged_radius if args.radius_m is None else float(args.radius_m)
    azimuth_used = (dragged_azimuth if args.azimuth_deg is None
                    else float(args.azimuth_deg))
    radians = math.radians(azimuth_used)
    regular_body = [radius_used * math.cos(radians), radius_used * math.sin(radians),
                    height]
    regular_controller = body_to_controller_pose(regular_body, REGULAR_BODY_RPY, arm)

    ik = RuntimeGoalIK(template["robot_yaml_urdf"], template["T_body_model"],
                       template["T_link6_tcp"])
    start = np.asarray([float(v) for v in record["joints_rad"]])
    goal = ik.solve(np.asarray(regular_body), REGULAR_BODY_ROTATION, start)

    radius = math.hypot(regular_body[0], regular_body[1])
    azimuth = math.degrees(math.atan2(regular_body[1], regular_body[0]))
    low, high = (float(v) for v in contract["radial_range_m"])
    warnings = []
    if not low <= radius <= high:
        warnings.append("horizontal radius %.3f m is outside the contract %.2f-%.2f m"
                        % (radius, low, high))
    if abs(azimuth - float(contract["body_azimuth_deg"])) > 15.0:
        warnings.append("azimuth %.1f deg is more than 15 deg from the contract %.1f deg"
                        % (azimuth, float(contract["body_azimuth_deg"])))

    result = {
        "schema_version": 1,
        "label": "visibility_clear_regularised",
        "source_teach": str(args.teach / "visibility_clear_pose.json"),
        "source_teach_sha256": record.get("record_sha256"),
        "dragged": {
            "joints_rad": [float(v) for v in record["joints_rad"]],
            "controller_tool_pose_mm_rad": record["controller_tool_pose_mm_rad"],
            "tcp_body_m": dragged_body,
            "tcp_body_rpy": dragged_body_rpy,
            "object_tilt_deg": tilt_deg(zyx_to_matrix(*dragged_body_rpy)),
            "horizontal_radius_m": dragged_radius,
            "body_azimuth_deg": dragged_azimuth,
        },
        "horizontal_override": {
            "radius_m": radius_used, "azimuth_deg": azimuth_used,
            "radius_override_m": args.radius_m, "azimuth_override_deg": args.azimuth_deg,
            "shift_from_dragged_m": float(np.hypot(regular_body[0] - dragged_body[0],
                                                    regular_body[1] - dragged_body[1])),
        },
        "regularised": {
            "tcp_body_m": regular_body,
            "tcp_body_rpy_zyx": REGULAR_BODY_RPY,
            "controller_tool_pose_mm_rad": regular_controller,
            "object_tilt_deg": tilt_deg(REGULAR_BODY_ROTATION),
            "tool_axes_body": {"X": REGULAR_BODY_ROTATION[:, 0].tolist(),
                               "Y": REGULAR_BODY_ROTATION[:, 1].tolist(),
                               "Z": REGULAR_BODY_ROTATION[:, 2].tolist()},
        },
        "ik": {
            "goal_joints_rad": [float(v) for v in goal.joints_rad],
            "position_error_m": goal.position_error_m,
            "orientation_error_rad": goal.orientation_error_rad,
            "max_joint_excursion_from_dragged_deg":
                place_ik_probe.excursion_deg(start, goal.joints_rad),
            "j1_deg": math.degrees(float(goal.joints_rad[0])),
        },
        "contract": dict(contract),
        "contract_warnings": warnings,
        "contract_satisfied": not warnings,
        "level_rule": "object upright <=> tool Y axis along BODY +Z; tilt reported as the "
                      "angle between them",
    }
    (args.output / "visibility_clear_target.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "dragged_body_m": [round(v, 5) for v in dragged_body],
        "dragged_object_tilt_deg": round(result["dragged"]["object_tilt_deg"], 3),
        "regularised_body_m": [round(v, 5) for v in regular_body],
        "regularised_body_rpy_zyx": [round(v, 6) for v in REGULAR_BODY_RPY],
        "regularised_controller_pose_mm_rad": [round(v, 4) for v in regular_controller],
        "regularised_object_tilt_deg": round(result["regularised"]["object_tilt_deg"], 6),
        "tool_axes_body": {k: [round(v, 4) for v in axis]
                           for k, axis in result["regularised"]["tool_axes_body"].items()},
        "ik_goal_joints_rad": [round(v, 5) for v in goal.joints_rad],
        "ik_J1_deg": round(result["ik"]["j1_deg"], 3),
        "ik_position_error_m": goal.position_error_m,
        "ik_orientation_error_deg": math.degrees(goal.orientation_error_rad),
        "joint_excursion_from_dragged_deg":
            round(result["ik"]["max_joint_excursion_from_dragged_deg"], 2),
        "contract_warnings": warnings,
        "output": str(args.output / "visibility_clear_target.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
