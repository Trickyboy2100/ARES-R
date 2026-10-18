#!/usr/bin/env python3
"""Read-only 5700 dryer detection -> BODY point and BODY yaw.

Sends the configured 5700 Cartesian command (default ``320,2,4,1,1,0``: space 2,
object 4, camera 1) through the existing audited EpicClient, converts the single
returned end-effector pose from the declared arm-base frame into the ARES-R BODY
frame, and reports:

* the detected point in BODY,
* the tool local +Z axis in BODY, its yaw in the BODY XY plane and its tilt,
* the derived preland = detected point + ``--standoff-m`` along BODY +Z.

No motion, no planner, no scene.  The controller is only read for its TCP pose so
the detection can be cross-checked against the arm's own forward kinematics.

This mirrors the 2026-10-12 ``dryer_target_probe`` run whose result is kept at
``worklog/evidence/2026-10-12-onsite-preland/detect/dryer_detection.json``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ares_r.adapters.epic import EpicClient                       # noqa: E402
from ares_r.adapters.epic_protocol import parse_5700_response     # noqa: E402
from ares_r.motion.se3 import pose_mm_rad_to_matrix               # noqa: E402


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def body_base(world, side):
    arm = world["arms"][side]
    x, y, z = (float(v) for v in arm["base_xyz_m"])
    yaw = float(arm["base_rpy_rad"][2])
    c, s = math.cos(yaw), math.sin(yaw)
    return [[c, -s, 0, x], [s, c, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--command", default="320,2,4,1,1,0",
                        help="5700 command; default is the dryer probe (space 2, object 4)")
    parser.add_argument("--arm", default="right", choices=["left", "right"])
    parser.add_argument("--standoff-m", type=float, default=0.070,
                        help="preland height above the detected point (BODY +Z)")
    parser.add_argument("--output", type=Path,
                        default=REPO / "worklog/evidence/onsite-dryer-detect/detection.json")
    args = parser.parse_args()

    site = json.loads((REPO / "config/system.json").read_text())
    world = json.loads((REPO / "config/robot_world.json").read_text())

    space, obj, camera = (int(v) for v in args.command.split(",")[1:4])
    epic = copy.deepcopy(site["epic"])
    # Reuse the commissioned right-arm profile's metadata, but point it at the
    # dryer object the handoff specifies and at the arm it is declared for.
    template = epic["task_profiles"]["right_place_rightmost"]
    profile = dict(template)
    profile.update(command=args.command, object_id=obj, space_id=space,
                   camera_id=camera, arm=args.arm,
                   output_frame="%s_arm_base_candidate" % args.arm)
    epic["task_profiles"]["dryer_target_probe"] = profile

    client = EpicClient(epic)
    result = client._detect_profile("dryer_target_probe", "place:0")

    report = {
        "command": args.command, "arm": args.arm, "standoff_m": args.standoff_m,
        "space_id": space, "object_id": obj, "camera_id": camera,
        "success": bool(result.success), "error": result.error,
        "raw_response": result.raw_response, "meta": result.meta,
        "profile_state": profile.get("state"),
        "profile_commissioned": template.get("commissioned"),
    }
    if not result.success:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps(report, indent=1))
        return 2

    response = parse_5700_response(result.raw_response)
    values = [float(v) for v in response.poses[0][:6]]
    base_mm_rad = [values[0], values[1], values[2],
                   math.radians(values[3]), math.radians(values[4]), math.radians(values[5])]
    t_body_base = body_base(world, args.arm)
    t_body_tcp = matmul(t_body_base, pose_mm_rad_to_matrix(base_mm_rad))

    position = [t_body_tcp[i][3] for i in range(3)]
    z_axis = [t_body_tcp[i][2] for i in range(3)]
    yaw_deg = math.degrees(math.atan2(z_axis[1], z_axis[0]))
    tilt_deg = math.degrees(math.asin(max(-1.0, min(1.0, z_axis[2]))))
    preland = [position[0], position[1], position[2] + args.standoff_m]

    report.update(
        detected_base_mm_deg=values,
        detected_body_m=[round(v, 6) for v in position],
        tool_local_Z_in_body=[round(v, 6) for v in z_axis],
        tool_local_Z_yaw_deg_in_body_xy=round(yaw_deg, 4),
        tool_local_Z_tilt_deg=round(tilt_deg, 4),
        preland_body_m=[round(v, 6) for v in preland],
        frame_note="BODY = T_body_base(%s) @ controller_TCP; base yaw from "
                   "config/robot_world.json" % args.arm,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1) + "\n")

    print("raw response  : %s" % result.raw_response)
    print("detected base : %s mm/deg" % [round(v, 5) for v in values])
    print("detected BODY : %s m" % report["detected_body_m"])
    print("tool +Z BODY  : %s" % report["tool_local_Z_in_body"])
    print("  yaw         : %+.4f deg" % yaw_deg)
    print("  tilt        : %+.4f deg" % tilt_deg)
    print("preland BODY  : %s m   (+%.0f mm in BODY +Z)"
          % (report["preland_body_m"], 1000 * args.standoff_m))
    print("profile state : %s" % report["profile_state"])
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
