#!/usr/bin/env python3
"""Repeated Epic detections: is the camera reporting the same grasp point?

A single detection cannot be doubted. There is nothing to compare it against, so
a frame that jumped to a different candidate looks exactly like one that did not.
Repeating the same 320 command back to back and comparing the answers is what
turns that into a checkable claim.

Two things this deliberately does not do:

* It does not check correctness. Repeats can agree to a tenth of a millimetre and
  all sit away from the object, so this gate and the geometric gate stay separate.
* It does not compare against an earlier session. Absolute positions do not
  survive an object being moved (measured 2026-09-18 to 2026-09-20: a 97 mm and a
  172 mm shift with the height unchanged), so the comparison stays inside one
  burst and nothing is carried over.

No robot motion: the 5700 detection channel only.
"""

import argparse
import json
import math
from pathlib import Path
import time

from ares_r.adapters.epic import EpicClient
from ares_r.epic_frame_audit import (DEFAULT_REPEAT_POSITION_MM, DEFAULT_REPEAT_ROTATION_DEG,
                                     EULER_ORDERS, repeatability_verdict,
                                     rotation_difference_deg, rotation_matrix_ordered,
                                     summarize, write_evidence)

#: Evidence directory for this audit, so it does not share a folder with the
#: frame-displacement records.
EVIDENCE_KIND = "epic-repeatability"


def load_config(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def rotation_spread_deg(rotations, order):
    """Worst pairwise attitude gap, or ``None`` when the convention is unknown.

    Every sample comes from one profile, so a declared Euler order lets the
    triples be turned into rotations and compared properly. With an unknown
    order there is no honest way to do that, and the caller falls back to
    comparing the reported components and saying so.
    """
    if order not in EULER_ORDERS:
        return None
    matrices = [rotation_matrix_ordered(*triple, order) for triple in rotations]
    return max(rotation_difference_deg(matrices[first], matrices[second])
               for first in range(len(matrices)) for second in range(first + 1, len(matrices)))


def component_spread_deg(columns):
    """Fallback for an unknown convention: widest spread of the reported angles."""
    return max(max(column) - min(column) for column in columns)


def max_pairwise_mm(points_mm):
    """Widest gap between any two reported points; the number the gate is on."""
    return max(math.dist(points_mm[first], points_mm[second])
               for first in range(len(points_mm)) for second in range(first + 1, len(points_mm)))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/system.json")
    parser.add_argument("--arm", default="right", choices=("left", "right"))
    parser.add_argument("--profile", default=None,
                        help="Epic task profile to repeat; defaults to <arm>_pick")
    parser.add_argument("--samples", type=int, default=3,
                        help="repeat count (default 3); the first call also pays for the "
                             "TCP connect, so it is always the slowest")
    parser.add_argument("--max-position-mm", type=float, default=DEFAULT_REPEAT_POSITION_MM)
    parser.add_argument("--max-rotation-deg", type=float, default=DEFAULT_REPEAT_ROTATION_DEG)
    parser.add_argument("--session", default=time.strftime("epic-repeatability-%H%M%S"))
    parser.add_argument("--repository", default=".",
                        help="where worklog/evidence is written; defaults to the current directory")
    args = parser.parse_args()
    if args.samples < 2:
        raise SystemExit("--samples must be at least 2; one detection has nothing to compare against")

    config = load_config(args.config)
    profile_name = args.profile or ("%s_pick" % args.arm)
    profiles = config["epic"]["task_profiles"]
    if profile_name not in profiles:
        raise SystemExit("unknown Epic task profile %r; known: %s"
                         % (profile_name, ", ".join(sorted(profiles))))
    profile = profiles[profile_name]

    print("EPIC 重复性检查 —— 只发 320 检测命令；不驱动机械臂、夹爪或底盘")
    print("  profile %s   命令 %s" % (profile_name, profile["command"]))
    if profile["state"] != "COMMISSIONED":
        print("  注意：该 profile 状态是 %s。本检查只测重复性，不为它的正确性背书。"
              % profile["state"])
    print("  %d 次检测   门限 位置 %.3f mm / 姿态 %.3f deg"
          % (args.samples, args.max_position_mm, args.max_rotation_deg))
    if args.samples > 5 and (args.max_position_mm, args.max_rotation_deg) == (
            DEFAULT_REPEAT_POSITION_MM, DEFAULT_REPEAT_ROTATION_DEG):
        print("  注意：默认门限是按 3 次 burst 标定的，而最大两两距离会随次数上升"
              "（实测 3 次约 0.9 mm，20 次约 2.2 mm）。次数多时要么抬高门限，"
              "要么显式传 --max-position-mm。")

    client_config = dict(config["epic"])
    client_config["default_pick_profile"] = profile_name
    client = EpicClient(client_config)

    print("\n第一步：连续检测 %d 次" % args.samples)
    runs = []
    try:
        for index in range(args.samples):
            started = time.monotonic()
            result = client.detect_pick()
            elapsed = time.monotonic() - started
            run = dict(index=index, elapsed_s=round(elapsed, 3), success=bool(result.success),
                       error=result.error or None, raw_response=result.raw_response)
            if result.success:
                pose = result.pose
                run["pose_m_rad"] = [pose.x, pose.y, pose.z, pose.rx, pose.ry, pose.rz]
                run["pose_mm_deg"] = [pose.x * 1000.0, pose.y * 1000.0, pose.z * 1000.0,
                                      math.degrees(pose.rx), math.degrees(pose.ry),
                                      math.degrees(pose.rz)]
                print("  [%d/%d] %6.3f s  pos (%9.2f, %9.2f, %9.2f) mm  rpy (%8.3f, %8.3f, %8.3f) deg"
                      % (index + 1, args.samples, elapsed, *run["pose_mm_deg"][:3],
                         *run["pose_mm_deg"][3:]))
            else:
                print("  [%d/%d] %6.3f s  检测失败：%s"
                      % (index + 1, args.samples, elapsed, result.error))
                if not result.raw_response:
                    raise SystemExit(
                        "相机对 %s 没有任何应答（%s）。这是通道问题，不是抓取点不一致；"
                        "先确认 5700 在线再重跑。" % (profile["command"], result.error))
            runs.append(run)
    finally:
        client.close()

    good = [run for run in runs if run["success"]]
    failed = [run for run in runs if not run["success"]]
    failure_summary = "；".join(sorted({run["error"] or "未知" for run in failed}))
    rotation_method = None

    print("\n第二步：比较")
    if len(good) < 2:
        print("  成功检测只有 %d 次，无法比较。" % len(good))
        verdict = dict(ok=False, position_ok=False, rotation_ok=False,
                       samples=len(good), worst_position_mm=None, worst_rotation_deg=None,
                       max_position_mm=args.max_position_mm,
                       max_rotation_deg=args.max_rotation_deg,
                       sentence="只有 %d 次检测返回了抓取点，无法判断一致性" % len(good))
    else:
        summary = summarize([run["pose_mm_deg"][:3] for run in good])
        columns = list(zip(*[run["pose_mm_deg"] for run in good]))
        order = profile.get("orientation_convention")
        geodesic = rotation_spread_deg([run["pose_m_rad"][3:6] for run in good], order)
        if geodesic is None:
            rotation_method = "component-spread-in-%s (convention unknown)" % order
            worst_rotation = component_spread_deg(columns[3:6])
        else:
            rotation_method = "geodesic-in-%s" % order
            worst_rotation = geodesic

        print("  位置均值 (%9.2f, %9.2f, %9.2f) mm" % tuple(summary["mean_mm"]))
        print("  逐轴极差 (%6.3f, %6.3f, %6.3f) mm   最大两两距离 %.3f mm"
              % (*summary["spread_mm"], max_pairwise_mm([run["pose_mm_deg"][:3] for run in good])))
        print("  姿态极差 %.4f deg   （%s）" % (worst_rotation, rotation_method))
        verdict = repeatability_verdict(summary, worst_rotation, args.max_position_mm,
                                        args.max_rotation_deg)

    if failed:
        print("  失败 %d/%d 次：%s" % (len(failed), args.samples, failure_summary))
        verdict = dict(verdict, ok=False,
                       sentence=verdict["sentence"] + "；另外 %d/%d 次没有返回抓取点（%s）"
                                % (len(failed), args.samples, failure_summary))

    print("\n结论：" + verdict["sentence"])
    print("  提醒：这只证明这几次是同一个答案，不证明这个答案是对的。"
          "绝对位置不跨会话可比，所以本检查只在这一次 burst 内比较。")

    record = dict(
        schema_version=1, session=args.session, kind="epic_repeatability",
        recorded_at=time.strftime("%Y-%m-%d %H:%M:%S"), recorded_at_unix=time.time(),
        arm=args.arm, epic_profile=profile_name, command=profile["command"],
        profile_state=profile["state"], output_frame=profile["output_frame"],
        orientation_convention=profile["orientation_convention"],
        calibration_revision=profile["calibration_revision"],
        requested_samples=args.samples,
        thresholds=dict(max_position_mm=args.max_position_mm,
                        max_rotation_deg=args.max_rotation_deg),
        runs=runs,
        rotation_method=rotation_method,
        verdict=verdict,
        limitations=[
            "只检查重复性，不检查正确性：一致的检测仍可能整体偏离物体。",
            "只在本次 burst 内比较；不跨会话引用绝对位置。",
            "样本数远小于 20 时只能给出量级，不足以定容差或失败率，"
            "而且最大两两距离本身随样本数上升。",
        ],
        warning=("Detection channel only. No arm, gripper or base command was issued. "
                 "This record measures repeatability; it does not commission the profile."),
    )
    path = write_evidence(args.repository, args.session, record, EVIDENCE_KIND)
    print("\n证据已保存：%s" % path)
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
