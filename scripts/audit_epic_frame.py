#!/usr/bin/env python3
"""Interactive displacement test for the Epic pose frame. Camera captures only.

Move the tray by a distance you can measure, and this records what the camera
reported before and after. That is the only way to tell whether the millimetre
triple lives in the arm base frame the planner assumes.
"""

import argparse
import json
from pathlib import Path
import time

from ares_r.adapters.epic import EpicClient
from ares_r.epic_frame_audit import build_record, compare, summarize, verdict, write_evidence


def load_config(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def capture(client, samples, label):
    """Repeated detections of a stationary tray, with the raw frames kept."""
    points, raws = [], []
    print("\n%s：连续采集 %d 次" % (label, samples))
    for index in range(samples):
        result = client.detect_pick()
        if not result.success:
            raise SystemExit("  第 %d 次检测失败：%s" % (index + 1, result.error))
        point = result.pose
        points.append([point.x * 1000.0, point.y * 1000.0, point.z * 1000.0])
        raws.append(result.raw_response)
        print("  [%d/%d] (%9.2f, %9.2f, %9.2f) mm   空间ID=%s" % (
            index + 1, samples, points[-1][0], points[-1][1], points[-1][2],
            result.meta.get("space_id")))
    summary = summarize(points)
    summary["raw_responses"] = raws
    print("  均值 (%9.2f, %9.2f, %9.2f) mm   最大极差 %.2f mm" % (
        summary["mean_mm"][0], summary["mean_mm"][1], summary["mean_mm"][2],
        summary["worst_spread_mm"]))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--samples", type=int, default=5,
                        help="detections per station; 5 is enough to see the noise floor")
    parser.add_argument("--session", default=time.strftime("epic-frame-%H%M%S"))
    parser.add_argument("--note", default="", help="what was physically moved, in your words")
    args = parser.parse_args()
    if args.samples < 2:
        raise SystemExit("--samples must be at least 2; a single sample cannot show noise")

    config = load_config(args.config)
    epic = config["epic"]
    print("EPIC FRAME AUDIT — 只触发相机，不会操作机械臂、夹爪或底盘")
    print("坐标系 %r  已验收=%s  检测指令=%s" % (
        epic.get("pose_frame"), epic.get("pose_frame_verified"), epic.get("pick_command")))

    client = EpicClient(epic)
    try:
        before = capture(client, args.samples, "起点")

        print("\n把料盘沿一个方向平移一段距离，越远越好。")
        raw = input("平移距离 (mm)（不知道就按回车，只测方向）: ").strip()
        try:
            distance = float(raw) if raw else None
        except ValueError:
            raise SystemExit("平移距离必须是数字，或直接按回车跳过尺度验证")
        direction = input("方向说明（例如：车体前方 / 沿地面向右）: ").strip()
        input("移动完成后按回车采集终点...")

        after = capture(client, args.samples, "终点")
    finally:
        client.close()

    try:
        report = compare(before, after, distance, direction)
    except ValueError as exc:
        raise SystemExit("无法比较：%s" % exc)

    print("\n" + verdict(report))
    if report["scale"] is None:
        print("位移向量 (%.2f, %.2f, %.2f) mm   物理距离未知，尺度未验证" % tuple(report["delta_mm"]))
    else:
        print("位移向量 (%.2f, %.2f, %.2f) mm   比例 %.4f   残差 %.2f mm" % (
            report["delta_mm"][0], report["delta_mm"][1], report["delta_mm"][2],
            report["scale"], report["residual_mm"]))

    record = build_record(args.session, "displacement", before, after, report, args.note)
    path = write_evidence(Path.cwd(), args.session, record)
    print("\n证据已保存：%s" % path)
    if report["scale_within_tolerance"]:
        print("\n比例接近 1，按下面两步完成坐标系验收：")
        print("  1. 把 %s 里 epic.pose_frame 改成实测的坐标系名（空间2 用 right_arm_base）" % args.config)
        print("  2. 把 epic.pose_frame_verified 改成 true")
    else:
        print("\n尺度仍未验证。绝对长度只能靠外部基准，最省事的是用机器人自己：")
        print("  - JAKA APP 里切到拖动示教，把 TCP 拉到料盘参考点")
        print("  - 回读控制器 TCP，与相机报告的抓取点比对（不需要尺子）")


if __name__ == "__main__":
    main()
