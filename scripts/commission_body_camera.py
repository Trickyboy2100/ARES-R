#!/usr/bin/env python3
"""Commission ``T_body_camera`` from the Epic hand-eye calibration and the site
arm-base definition, then prove it against the depth data.

Read-only with respect to every device: this script opens an already captured
point cloud and two config/evidence files. It never triggers a camera, a robot
or a planner. Writing the transform into config is behind ``--write`` and only
happens once both invariants pass.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ares_r.perception.body_camera import (body_camera_verdict, commission_record,
                                           compose_body_camera, dominant_plane,
                                           ground_height_m, support_tilt_deg)
from ares_r.timing import timestamp

REPOSITORY = Path(__file__).resolve().parents[1]


def _load_json(path, label):
    if not Path(path).is_file():
        raise SystemExit("%s not found: %s" % (label, path))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_ply_m(path, stride=1, unit_scale=0.001):
    """Binary little-endian XYZ float32 + RGB uint8 PLY, returned in metres."""
    import struct

    with open(path, "rb") as stream:
        header = []
        for _ in range(64):
            line = stream.readline()
            header.append(line)
            if line == b"end_header\n":
                break
        else:
            raise SystemExit("PLY header too long")
        text = b"".join(header).decode("ascii")
        if "format binary_little_endian 1.0" not in text:
            raise SystemExit("binary little-endian PLY required")
        if not all(key in text for key in ("property float x", "property float y",
                                          "property float z")):
            raise SystemExit("PLY must carry float32 xyz")
        count = int([line for line in text.splitlines()
                     if line.startswith("element vertex")][0].split()[2])
        record = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                           ("r", "u1"), ("g", "u1"), ("b", "u1")])
        data = np.fromfile(stream, dtype=record, count=count)
    points = np.stack([data["x"], data["y"], data["z"]], axis=1).astype(np.float64)
    valid = np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)
    return points[valid][::stride] * float(unit_scale)


def arm_base_transform(world, arm):
    """BODY <- controller base, from the site's level-base installation values."""
    geometry = world["arms"][arm]
    roll, pitch, yaw = (float(v) for v in geometry["base_rpy_rad"])
    if abs(roll) > 1e-12 or abs(pitch) > 1e-12:
        raise SystemExit("BODY<-base composition only supports level arm bases")
    cosine, sine = np.cos(yaw), np.sin(yaw)
    matrix = np.eye(4)
    matrix[:3, :3] = np.array([[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]])
    matrix[:3, 3] = [float(v) for v in geometry["base_xyz_m"]]
    return matrix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", default="right", choices=("left", "right"))
    parser.add_argument("--handeye", default=None,
                        help="Epic hand-eye evidence; defaults to the newest for --arm")
    parser.add_argument("--capture", required=True,
                        help="capture directory holding pointcloud.ply")
    parser.add_argument("--world", default="config/robot_world.json")
    parser.add_argument("--system", default="config/system.json")
    parser.add_argument("--stride", type=int, default=2)
    parser.add_argument("--max-tilt-deg", type=float, default=1.0)
    parser.add_argument("--max-ground-offset-m", type=float, default=0.03)
    parser.add_argument("--min-ground-points", type=int, default=500)
    parser.add_argument("--evidence-dir", default=None)
    parser.add_argument("--write", action="store_true",
                        help="also write epic_pointcloud.T_body_camera into config")
    args = parser.parse_args()

    handeye_path = Path(args.handeye) if args.handeye else None
    if handeye_path is None:
        candidates = sorted((REPOSITORY / "worklog/evidence").glob(
            "*/handeye-%s-*.json" % args.arm))
        if not candidates:
            raise SystemExit("no handeye-%s evidence under worklog/evidence" % args.arm)
        handeye_path = candidates[-1]
    handeye = _load_json(handeye_path, "hand-eye evidence")
    if float(handeye.get("calibration", {}).get("reprojection", {})
             .get("mean_rotation_deg", 1e9)) > 1.0:
        raise SystemExit("hand-eye calibration exceeds 1 deg mean reprojection")

    world = _load_json(REPOSITORY / args.world, "world geometry")
    T_base_camera = np.asarray(handeye["calibration"]["transform"], dtype=float)
    T_base_camera[:3, 3] /= 1000.0  # the calibration reports millimetres
    T_body_base = arm_base_transform(world, args.arm)
    composed = compose_body_camera(T_body_base, T_base_camera)
    transform = composed["transform"]

    cloud_path = Path(args.capture) / "pointcloud.ply"
    if not cloud_path.is_file():
        raise SystemExit("no pointcloud.ply in %s" % args.capture)
    points = load_ply_m(cloud_path, stride=args.stride)

    plane = dominant_plane(points)
    tilt = support_tilt_deg(transform, plane["normal"])
    body = (transform[:3, :3] @ points.T).T + transform[:3, 3]
    ground = ground_height_m(body, half_width_m=args.max_ground_offset_m * 2.0 + 0.02)
    verdict = body_camera_verdict(tilt, ground, args.max_tilt_deg,
                                  args.max_ground_offset_m, args.min_ground_points)

    print("EPIC 手眼 → T_body_camera 定案（只读；未触碰相机、机械臂、规划器）")
    print()
    try:
        shown = handeye_path.relative_to(REPOSITORY)
    except ValueError:
        shown = handeye_path
    print("手眼证据     : %s" % shown)
    print("  修订       : %s" % handeye.get("revision"))
    print("  重投影     : 均值 %.3f deg / %.3f mm" % (
        handeye["calibration"]["reprojection"]["mean_rotation_deg"],
        handeye["calibration"]["reprojection"]["mean_translation_mm"]))
    print("基座(控制器) : %s m" % list(world["arms"][args.arm]["base_xyz_m"]))
    print("捕获点云     : %s  (%d 点)" % (args.capture, len(points)))
    print()
    print("T_body_camera =")
    for row in transform:
        print("   [%9.6f %9.6f %9.6f %9.6f]" % tuple(row))
    print("相机在 BODY  : %s m" % np.round(transform[:3, 3], 4))
    print("正交化修正量 : base %.2e / hand-eye %.2e （界面只显示 4 位小数的舍入）"
          % (composed["base_orthonormalisation"],
             composed["camera_orthonormalisation"]))
    print()
    print("检验 1 —— 旋转：水平面必须仍是水平面（与 Epic 报的位姿无关）")
    print("  深度系主平面: %d 点 (%.1f%%)，法线 %s"
          % (plane["point_count"], 100 * plane["inlier_ratio"],
             np.round(plane["normal"], 4)))
    print("  映射到 BODY 后的倾角: %.4f deg" % tilt)
    print()
    print("检验 2 —— 平移：地面必须落在 BODY z = 0（BODY 原点的定义就是地面）")
    print("  z 在 0 附近的点: %d (%.1f%%)" % (ground["point_count"], 100 * ground["fraction"]))
    if ground["point_count"]:
        print("  中位高度: %+.4f m   平面度 ±%.4f m"
              % (ground["median_z_m"], ground["spread_m"]))
    print()
    print("判定: %s" % verdict)

    passed = verdict.startswith("通过")
    record = commission_record(
        T_body_base, T_base_camera, arm=args.arm,
        handeye_revision=str(handeye.get("revision")), tilt_deg=tilt, ground=ground,
        verdict=verdict,
        evidence=dict(handeye_evidence=str(handeye_path), capture=args.capture,
                      pointcloud_sha256=_sha256(cloud_path),
                      point_count=int(len(points)), stride=args.stride,
                      support_plane=dict(normal=[float(v) for v in plane["normal"]],
                                         inlier_ratio=plane["inlier_ratio"]),
                      world_geometry_file=args.world, method="hand-eye chain",
                      orthonormalisation_max_element=float(max(
                          composed["base_orthonormalisation"],
                          composed["camera_orthonormalisation"])),
                      why_not_fitted=("2026-09-17 的拟合路线在 17 deg yaw 与 233 mm "
                                      "平移上多解，未 commission；本次不重跑该路线"),
                      pointcloud_path=str(cloud_path)),
        recorded_at=timestamp()["wall_time_iso"])
    directory = (Path(args.evidence_dir) if args.evidence_dir
                 else REPOSITORY / "worklog/evidence"
                 / (timestamp()["wall_time_iso"][:10] + "-body-camera"))
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s-%s.json" % (args.arm, _stamp()))
    if target.exists():
        raise SystemExit("%s already exists; refusing to overwrite evidence" % target)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("\n证据已保存: %s" % target)
    print("修订: %s" % record["revision"])

    if args.write:
        if not passed:
            raise SystemExit("拒绝写入 config：判定未通过")
        system_path = REPOSITORY / args.system
        system = json.loads(system_path.read_text(encoding="utf-8"))
        system["epic_pointcloud"]["T_body_camera"] = record["T_body_camera"]
        system["epic_pointcloud"]["T_body_camera_revision"] = record["revision"]
        system_path.write_text(json.dumps(system, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print("已写入 %s -> epic_pointcloud.T_body_camera" % args.system)
    elif passed:
        print("\n（未写入 config；确认后加 --write 重跑）")
    return 0 if passed else 1


def _sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _stamp():
    return timestamp()["wall_time_iso"][:19].replace("T", "-").replace(":", "")


if __name__ == "__main__":
    sys.exit(main())
