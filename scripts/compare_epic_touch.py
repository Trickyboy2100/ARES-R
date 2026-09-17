#!/usr/bin/env python3
"""Compare the camera's grasp point with the arm's own TCP readout.

The displacement test can only ever confirm a direction: without a tape measure
there is no absolute length, and therefore no way to prove the numbers are
millimetres. The arm supplies that missing reference for free -- it already
reports its TCP in the controller frame, in millimetres.

Put the gripper TCP on the point the camera named, read both, and the difference
is the transform that was missing. No motion is commanded by this script: the
operator drags the arm by hand in free-drive mode.
"""

import argparse
import json
import math
from pathlib import Path
import statistics
import time

from ares_r.adapters.epic import EpicClient
from ares_r.epic_frame_audit import write_evidence
from ares_r.motion.pregrasp import read_live


def load_config(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def detect_mean(config, samples):
    """Mean grasp point in the controller millimetre frame, plus raw frames."""
    client = EpicClient(config["epic"])
    try:
        points, raws = [], []
        for index in range(samples):
            result = client.detect_pick()
            if not result.success:
                raise SystemExit("第 %d 次检测失败：%s" % (index + 1, result.error))
            pose = result.pose
            points.append([pose.x * 1000.0, pose.y * 1000.0, pose.z * 1000.0])
            raws.append(result.raw_response)
            print("  [%d/%d] (%9.2f, %9.2f, %9.2f) mm" % (index + 1, samples, *points[-1]))
    finally:
        client.close()
    columns = list(zip(*points))
    return dict(samples=samples,
                mean_mm=[round(statistics.mean(column), 4) for column in columns],
                spread_mm=[round(max(column) - min(column), 4) for column in columns],
                raw_responses=raws)


def read_tcp_mean(config, arm, samples):
    """Mean live controller TCP. Read-only SDK calls, nothing is commanded."""
    points = []
    for index in range(samples):
        diagnostics = read_live(config, arm)
        points.append([float(value) for value in diagnostics["tcp_position_mm_rad"][:3]])
        print("  [%d/%d] (%9.2f, %9.2f, %9.2f) mm" % (index + 1, samples, *points[-1]))
        time.sleep(0.2)
    columns = list(zip(*points))
    spread = [max(column) - min(column) for column in columns]
    if max(spread) > 2.0:
        raise SystemExit("TCP 读数还在漂移（极差 %.2f mm），让机械臂静止后重试" % max(spread))
    return dict(samples=samples,
                mean_mm=[round(statistics.mean(column), 4) for column in columns],
                spread_mm=[round(value, 4) for value in spread],
                raw_responses=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--arm", default="right", choices=("left", "right"))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--session", default=time.strftime("epic-touch-%H%M%S"))
    parser.add_argument("--tolerance-mm", type=float, default=5.0)
    parser.add_argument("--tcp-first", action="store_true",
                        help="读取 TCP 在前。机械臂已经停在抓取点上时用这个顺序，"
                             "否则夹爪会挡住相机")
    args = parser.parse_args()

    config = load_config(args.config)
    print("EPIC TCP 比对 —— 只读相机与控制器状态；本脚本不发任何运动指令")
    print("坐标系 %r  已验收=%s  机械臂=%s" % (
        config["epic"].get("pose_frame"), config["epic"].get("pose_frame_verified"), args.arm))

    if args.tcp_first:
        print("\n第一步：读取控制器 TCP（机械臂应正停在抓取点上）")
        tcp = read_tcp_mean(config, args.arm, args.samples)
        input("  然后把机械臂移出相机视野（避免挡住料盘），到位后按回车做检测...")
        print("\n第二步：相机检测抓取点")
        epic = detect_mean(config, args.samples)
    else:
        print("\n第一步：相机检测抓取点")
        epic = detect_mean(config, args.samples)
        print("  相机抓取点 (%.2f, %.2f, %.2f) mm" % tuple(epic["mean_mm"]))
        print("\n第二步：把 TCP 拖到相机报告的那个点上")
        print("  - 在 JAKA APP 里切到拖动示教（free drive）")
        print("  - 用手把夹爪 TCP 移到 (%.1f, %.1f, %.1f) mm 这个位置" % tuple(epic["mean_mm"]))
        input("  到位后按回车读取控制器 TCP...")
        print("\n第三步：读取控制器 TCP")
        tcp = read_tcp_mean(config, args.arm, args.samples)

    print("\n相机抓取点 (%.2f, %.2f, %.2f) mm" % tuple(epic["mean_mm"]))
    print("控制器 TCP  (%.2f, %.2f, %.2f) mm" % tuple(tcp["mean_mm"]))

    error = [tcp["mean_mm"][index] - epic["mean_mm"][index] for index in range(3)]
    magnitude = math.sqrt(sum(value * value for value in error))
    report = dict(
        arm=args.arm,
        epic_mean_mm=epic["mean_mm"], tcp_mean_mm=tcp["mean_mm"],
        error_mm=[round(value, 4) for value in error],
        error_magnitude_mm=round(magnitude, 4),
        tolerance_mm=args.tolerance_mm,
        frame_confirmed=magnitude <= args.tolerance_mm,
        epic_spread_mm=epic["spread_mm"], tcp_spread_mm=tcp["spread_mm"],
    )
    print("\n误差 (TCP - 相机) = (%.2f, %.2f, %.2f) mm   |误差| = %.2f mm" % (*error, magnitude))
    if report["frame_confirmed"]:
        print("判定：坐标系一致（在 %.1f mm 内）—— 相机返回的就是%s臂基座坐标系的毫米值"
              % (args.tolerance_mm, "右" if args.arm == "right" else "左"))
    else:
        print("判定：超出 %.1f mm 容差。检查三件事：" % args.tolerance_mm)
        print("  1. 拖动示教的 TCP 是否真的是相机报告的那个抓取点")
        print("  2. 夹爪 TCP 标定号是否与规划用的工具号一致")
        print("  3. 两个坐标系的 z 参考面是否相同（基座安装面 / 台面）")

    record = dict(schema_version=1, session=args.session, kind="epic_tcp_comparison",
                  recorded_at=time.strftime("%Y-%m-%d %H:%M:%S"), recorded_at_unix=time.time(),
                  epic=epic, tcp=tcp, comparison=report,
                  warning=("Read-only comparison. No arm, gripper or base command was issued. "
                           "Free-drive motion was performed by the operator, not by this script."))
    path = write_evidence(Path.cwd(), args.session, record)
    print("\n证据已保存：%s" % path)
    if report["frame_confirmed"]:
        print("\n完成坐标系验收：把 %s 里 epic.pose_frame_verified 改为 true" % args.config)


if __name__ == "__main__":
    main()
