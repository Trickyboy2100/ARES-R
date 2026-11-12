#!/usr/bin/env python3
"""Collect controller forward-kinematics samples without commanding motion."""

import ctypes
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config/system.json").read_text(encoding="utf-8"))
SDK = CONFIG["jaka"]


def value(result, label):
    if not isinstance(result, (tuple, list)) or not result or int(result[0]) != 0:
        raise RuntimeError("%s failed: %r" % (label, result))
    return result[1] if len(result) > 1 else None


def samples(current):
    result = [("zero", [0.0] * 6), ("current", list(current))]
    for joint in range(6):
        for sign, label in ((1.0, "plus"), (-1.0, "minus")):
            pose = [0.0] * 6
            pose[joint] = sign * 0.25
            result.append(("j%d_%s" % (joint + 1, label), pose))
    result.extend([
        ("mix_a", [0.30, -0.25, 0.20, -0.15, 0.10, -0.05]),
        ("mix_b", [-0.20, 0.35, -0.30, 0.25, -0.15, 0.10]),
        ("mix_c", [0.15, 0.20, -0.10, -0.30, 0.25, -0.20]),
    ])
    return result


def main():
    ctypes.CDLL(str(SDK["sdk_library_path"]), mode=ctypes.RTLD_GLOBAL)
    sys.path.insert(0, str(SDK["sdk_python_path"]))
    jkrc = importlib.import_module("jkrc")
    output = {"schema_version": 1, "captured_at": datetime.now().astimezone().isoformat(),
              "method": "read-only jkrc.get_joint_position/get_tool_id/get_tool_data/get_dh_param/kine_forward",
              "warning": "No power, enable, move, servo, abort, gripper or base API is called.", "arms": {}}
    for side in ("left", "right"):
        robot = jkrc.RC(str(SDK["arms"][side]["ip"]))
        value(robot.login(), "%s login" % side)
        try:
            current = list(value(robot.get_joint_position(), "%s joints" % side))
            tool_id = int(value(robot.get_tool_id(), "%s tool id" % side))
            tool_raw = robot.get_tool_data(tool_id)
            dh_raw = robot.get_dh_param()
            rows = []
            for name, joints in samples(current):
                rows.append({"name": name, "joint_rad": joints,
                             "tcp_mm_rad": list(value(robot.kine_forward(joints), "%s FK %s" % (side, name)))})
            output["arms"][side] = {"current_joint_rad": current, "tool_id": tool_id,
                                     "tool_data_raw": list(tool_raw), "dh_param_raw": list(dh_raw),
                                     "samples": rows}
        finally:
            value(robot.logout(), "%s logout" % side)
    path = ROOT / "worklog" / ("jaka_fk_samples_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
