#!/usr/bin/env python3
"""Right-only READ-ONLY URDF versus controller FK audit. No control API calls."""

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from ares_r.adapters.jaka_sdk import JakaSdkArm, _value


def pose(values):
    x, y, z, r, p, yaw = values
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(yaw), math.sin(yaw)
    m = np.eye(4)
    m[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                 [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
    m[:3, 3] = [x, y, z]
    return m


def urdf_fk(root, q):
    result = np.eye(4)
    for i in range(1, 7):
        joint = root.find("joint[@name='joint%d']" % i)
        if joint.find("axis").get("xyz") != "0 0 1":
            raise ValueError("unexpected joint axis")
        origin = joint.find("origin")
        values = [float(v) for v in (origin.get("xyz") + " " + origin.get("rpy")).split()]
        result = result @ pose(values) @ pose([0, 0, 0, 0, 0, q[i-1]])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--config", default="config/system.json")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite audit output")
    root = ET.parse(args.urdf).getroot()
    config = json.loads(Path(args.config).read_text())["jaka"]
    arm = JakaSdkArm("right", config["arms"]["right"], config)
    try:
        diagnostics = arm.diagnostics()
        tool = list(diagnostics["tool_data"]["pose_mm_rad"])
        tool[:3] = [v/1000 for v in tool[:3]]
        tool_matrix = pose(tool)
        samples = [[0.0]*6, diagnostics["joint_position_rad"]]
        for index in range(6):
            for delta in (-0.25, 0.25):
                q = [0.0]*6; q[index] = delta; samples.append(q)
        measured = []
        for q in samples:
            sdk = list(_value(arm.robot.kine_forward(q), "right FK"))
            sdk[:3] = [v/1000 for v in sdk[:3]]
            measured.append(pose(sdk))
        correction = measured[0] @ np.linalg.inv(urdf_fk(root, samples[0]) @ tool_matrix)
        rows = []
        for q, actual in zip(samples, measured):
            predicted = correction @ urdf_fk(root, q) @ tool_matrix
            relative = actual[:3, :3].T @ predicted[:3, :3]
            rows.append({"q_rad": q,
                         "position_error_mm": float(np.linalg.norm(actual[:3, 3]-predicted[:3, 3])*1000),
                         "orientation_error_deg": math.degrees(math.acos(float(np.clip((np.trace(relative)-1)/2, -1, 1))))})
        report = {"arm": "right", "method": "zero-pose base correction, 13 independent read-only SDK FK checks",
                  "T_controller_model": correction.tolist(), "samples": rows, "diagnostics": diagnostics,
                  "max_position_error_mm": max(row["position_error_mm"] for row in rows),
                  "max_orientation_error_deg": max(row["orientation_error_deg"] for row in rows),
                  "collision_model_commissioned": False}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps({key: report[key] for key in ("max_position_error_mm", "max_orientation_error_deg")}))
    finally:
        arm.close()


if __name__ == "__main__":
    main()
