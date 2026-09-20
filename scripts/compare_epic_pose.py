#!/usr/bin/env python3
"""Physical attitude comparison: which Euler convention does this camera speak?

The horizontality scan can only narrow the convention down, because several
orders stay indistinguishable while the pitch angle is small. The controller
already reports its TCP in a convention this repository has fixed, so putting
the gripper on the tray in the attitude a grasp would use and comparing the two
rotations settles it.

Order matters: the controller pose is read while the arm is still on the tray,
and the camera's numbers are never shown before that, so the operator cannot
position the arm by copying them. That circularity already wasted one session.

No motion is commanded here. The operator drags the arm by hand.
"""

import argparse
import json
import math
from pathlib import Path
import statistics
import time

from ares_r.adapters.epic import EpicClient
from ares_r.epic_frame_audit import (convention_verdict, match_orientation_convention,
                                     rotation_matrix_ordered, tool_axis_tilt_deg, write_evidence)
from ares_r.motion.pregrasp import read_live

#: A residual this small means the camera and the controller describe the same
#: physical attitude under this convention.
DEFAULT_MAX_RESIDUAL_DEG = 5.0
#: Below this gap between best and runner-up the measurement has not decided.
DEFAULT_MIN_MARGIN_DEG = 3.0


def load_config(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def read_controller_pose(config, arm, samples, max_spread_mm=2.0, max_spread_deg=0.5):
    """Controller TCP position and attitude. Read-only; nothing is commanded."""
    print("\n第一步：读取控制器 TCP（机械臂应正停在料盘抓取位姿上，且已退出拖动示教）")
    readings = []
    for index in range(samples):
        diagnostics = read_live(config, arm)
        values = [float(value) for value in diagnostics["tcp_position_mm_rad"][:6]]
        readings.append(values)
        print("  [%d/%d] pos (%8.2f, %8.2f, %8.2f) mm   rpy (%7.3f, %7.3f, %7.3f) deg"
              % (index + 1, samples, *values[:3], *[math.degrees(v) for v in values[3:6]]))
        time.sleep(0.2)
    columns = list(zip(*readings))
    spread = [max(column) - min(column) for column in columns]
    if max(spread[:3]) > max_spread_mm or max(math.degrees(value) for value in spread[3:]) > max_spread_deg:
        raise SystemExit("读数还在漂移（位置极差 %.2f mm，姿态极差 %.2f deg）；让机械臂静止后重试"
                         % (max(spread[:3]), max(math.degrees(value) for value in spread[3:])))
    mean = [statistics.mean(column) for column in columns]
    print("  均值 pos (%.2f, %.2f, %.2f) mm   rpy (%.3f, %.3f, %.3f) deg   工具号 %s"
          % (*mean[:3], *[math.degrees(v) for v in mean[3:6]],
             diagnostics.get("tool_id")))
    return dict(samples=samples, mean_mm_rad=mean, spread=spread,
                tool_id=diagnostics.get("tool_id"))


def detect_pose(config, samples, profile=None):
    """Camera grasp pose. The numbers stay hidden until the arm has been positioned."""
    epic = dict(config["epic"])
    if profile:
        epic["default_pick_profile"] = profile
    client = EpicClient(epic)
    try:
        readings, raws = [], []
        for index in range(samples):
            result = client.detect_pick()
            if not result.success:
                raise SystemExit("第 %d 次检测失败：%s" % (index + 1, result.error))
            pose = result.pose
            readings.append([pose.x, pose.y, pose.z, pose.rx, pose.ry, pose.rz])
            raws.append(result.raw_response)
            print("  [%d/%d] 已采集" % (index + 1, samples))
    finally:
        client.close()
    columns = list(zip(*readings))
    mean = [statistics.mean(column) for column in columns]
    spread = [max(column) - min(column) for column in columns]
    return dict(samples=samples, mean_m_rad=mean,
                mean_mm_deg=[mean[0] * 1000, mean[1] * 1000, mean[2] * 1000,
                             math.degrees(mean[3]), math.degrees(mean[4]), math.degrees(mean[5])],
                spread=spread, raw_responses=raws)


def tool_axes_in_base(camera_rpy, order):
    """The three tool axes of the matched convention, as base-frame unit vectors."""
    rotation = rotation_matrix_ordered(camera_rpy[0], camera_rpy[1], camera_rpy[2], order)
    axes = {}
    for name, column in (("x", 0), ("y", 1), ("z", 2)):
        for sign, label in ((1.0, "+"), (-1.0, "-")):
            axes[label + name] = [round(sign * rotation[row][column], 6) for row in range(3)]
    return axes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--arm", default="right", choices=("left", "right"))
    parser.add_argument("--profile", default="right_pick",
                        help="Epic task profile the detection uses")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--session", default=time.strftime("epic-attitude-%H%M%S"))
    parser.add_argument("--max-residual-deg", type=float, default=DEFAULT_MAX_RESIDUAL_DEG)
    parser.add_argument("--min-margin-deg", type=float, default=DEFAULT_MIN_MARGIN_DEG)
    args = parser.parse_args()
    if args.samples < 2:
        raise SystemExit("--samples must be at least 2")

    config = load_config(args.config)
    print("EPIC 姿态约定比对 —— 只读相机与控制器状态；本脚本不发任何运动指令")

    controller = read_controller_pose(config, args.arm, args.samples)
    input("\n  然后把机械臂移出相机视野（避免挡住料盘），到位后按回车做检测...")

    print("\n第二步：相机检测抓取位姿")
    camera = detect_pose(config, args.samples, args.profile)
    print("  相机位姿 pos (%8.2f, %8.2f, %8.2f) mm   rpy (%7.3f, %7.3f, %7.3f) deg"
          % tuple(camera["mean_mm_deg"]))

    position_error = [camera["mean_mm_deg"][index] - controller["mean_mm_rad"][index]
                      for index in range(3)]
    distance = math.sqrt(sum(value * value for value in position_error))

    camera_rpy = tuple(camera["mean_m_rad"][3:6])
    reference_rpy = tuple(controller["mean_mm_rad"][3:6])
    ranked = match_orientation_convention(camera_rpy, reference_rpy)
    sentence = convention_verdict(ranked, args.max_residual_deg, args.min_margin_deg)

    print("\n第三步：比对")
    print("  位置误差 (相机 - 控制器) = (%.2f, %.2f, %.2f) mm   |误差| = %.2f mm"
          % (*position_error, distance))
    print("  各欧拉顺序下的姿态残差（已容忍两指夹爪的 180 度对称）：")
    for item in ranked:
        branch = "   ← 夹爪半周分支" if item.get("half_turn") else ""
        print("    %-4s %8.3f deg%s" % (item["order"], item["residual_deg"], branch))
    print("\n  " + sentence)

    best = ranked[0]
    axes = tool_axes_in_base(camera_rpy, best["order"])
    radial = [camera["mean_m_rad"][index] / math.dist([0, 0, 0], camera["mean_m_rad"][:3])
              for index in range(3)]
    print("\n  胜出约定 %s 下的工具轴（基座坐标系）与「基座→料盘」方向的夹角：" % best["order"])
    for label in ("+x", "-x", "+y", "-y", "+z", "-z"):
        direction = axes[label]
        cosine = sum(direction[index] * radial[index] for index in range(3))
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        print("    %-3s (%7.4f, %7.4f, %7.4f)   水平倾斜 %+7.2f deg   与径向夹角 %6.1f deg"
              % (label, *direction, tool_axis_tilt_deg(
                  rotation_matrix_ordered(*camera_rpy, best["order"]), label), angle))
    print("\n  请判断：上表中哪一个轴是指向料盘内部（夹爪插入方向）？确认后写进 profile 的 approach_axis。")

    record = dict(
        schema_version=1, session=args.session, kind="epic_attitude_comparison",
        recorded_at=time.strftime("%Y-%m-%d %H:%M:%S"), recorded_at_unix=time.time(),
        arm=args.arm, epic_profile=args.profile,
        controller=controller, camera=camera,
        comparison=dict(position_error_mm=[round(v, 4) for v in position_error],
                        position_error_magnitude_mm=round(distance, 4),
                        ranked_conventions=ranked, verdict=sentence,
                        matched_order=best["order"], matched_residual_deg=best["residual_deg"],
                        min_margin_deg=args.min_margin_deg,
                        max_residual_deg=args.max_residual_deg,
                        tool_axes_in_base=axes),
        limitation=("位置比对只在机械臂确实停在相机报告的那个点上时才有意义；"
                    "本次由操作者按物理位置摆放，未使用相机数值。"),
        warning=("Read-only comparison. No arm, gripper or base command was issued. "
                 "Free-drive motion was performed by the operator, not by this script."))
    path = write_evidence(Path.cwd(), args.session, record)
    print("\n证据已保存：%s" % path)


if __name__ == "__main__":
    main()
