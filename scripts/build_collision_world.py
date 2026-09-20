#!/usr/bin/env python3
"""Point cloud -> ATOM obstacle cuboids -> frozen SceneSnapshot.

Read-only with respect to every device: this consumes an already captured frame
and saved read-only robot diagnostics. It never triggers a camera, never reads a
robot, and never plans or moves anything.

Two gates decide whether the result may be called a planning snapshot at all:

* the commissioned ``T_body_camera`` must be present in config with its revision,
  because a snapshot built on an uncommissioned transform is exactly the failure
  the 2026-09-17 demo had to be discarded for;
* the robot spheres used by the self-filter must describe the arm pose *at the
  moment of capture*, otherwise the filter carves holes in the wrong place.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ares_r.perception.body_camera import dominant_plane
from ares_r.perception.obstacle_world import (aabb_from_points, crop_roi, joint_state_matches,
                                              remove_support, self_filter,
                                              self_filter_completeness, support_slab)
from ares_r.world import (CalibrationSet, PointCloudRef, PoseSE3, RobotState, SafetyConstraint,
                          SceneObject, SceneObjectRole, WorldModel, compile_snapshot,
                          snapshot_dict)
from ares_r.timing import timestamp

REPOSITORY = Path(__file__).resolve().parents[1]
PROVENANCE = "COMMISSIONED_BODY_CAMERA_2026-09-18"


def load_ply_m(path, stride=1):
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
        count = int([line for line in text.splitlines()
                     if line.startswith("element vertex")][0].split()[2])
        record = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                           ("r", "u1"), ("g", "u1"), ("b", "u1")])
        data = np.fromfile(stream, dtype=record, count=count)
    points = np.stack([data["x"], data["y"], data["z"]], axis=1).astype(np.float64)
    valid = np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 0)
    return points[valid][::stride] / 1000.0


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def arm_state(state, arm):
    values = state.get("arms", state)
    if arm not in values:
        raise SystemExit("robot state has no %s arm" % arm)
    entry = values[arm]
    joints = entry.get("joint_position_rad")
    if not joints:
        raise SystemExit("robot state %s arm needs joint_position_rad" % arm)
    if entry.get("joint_spread_rad") is not None \
            and float(entry["joint_spread_rad"]) > 0.0:
        raise SystemExit(
            "机械臂在拍照前后动了（关节最大变化 %.6f rad）。球体与点云不再是同一时刻，\n"
            "自滤波会挖错地方。请重拍。" % float(entry["joint_spread_rad"]))
    return [float(v) for v in joints]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--arm", default="right", choices=("left", "right"))
    parser.add_argument("--robot-geometry", required=True,
                        help="BODY collision spheres plus the joints they describe")
    parser.add_argument("--robot-state", required=True,
                        help="read-only diagnostics captured at the same time")
    parser.add_argument("--system", default="config/system.json")
    parser.add_argument("--pipeline", default="config/pointcloud_pipeline.site.json")
    parser.add_argument("--voxel-m", type=float, default=0.01)
    parser.add_argument("--cluster-tolerance-m", type=float, default=0.035)
    parser.add_argument("--min-cluster-points", type=int, default=10)
    parser.add_argument("--min-cluster-voxels", type=int, default=18)
    parser.add_argument("--self-filter-margin-m", type=float, default=0.025)
    parser.add_argument("--support-half-band-m", type=float, default=0.035)
    parser.add_argument("--support-thickness-m", type=float, default=0.05)
    parser.add_argument("--inflation-m", type=float, default=None)
    parser.add_argument("--joint-tolerance-rad", type=float, default=1e-3)
    parser.add_argument("--declare-stale-robot-geometry", action="store_true",
                        help="proceed although the spheres describe another pose; "
                             "the mismatch is recorded in the snapshot")
    parser.add_argument("--detection-id", default="")
    parser.add_argument("--grasp-point-mm", default=None,
                        help="camera grasp point in the arm base frame, mm; the cluster "
                             "containing it is the grasp target rather than an obstacle")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    system = json.loads((REPOSITORY / args.system).read_text(encoding="utf-8"))
    pipeline = json.loads((REPOSITORY / args.pipeline).read_text(encoding="utf-8"))
    pc_config = system["epic_pointcloud"]
    transform = pc_config.get("T_body_camera")
    revision = pc_config.get("T_body_camera_revision")
    if not transform or not revision:
        raise SystemExit("epic_pointcloud.T_body_camera is not commissioned; run "
                         "scripts/commission_body_camera.py --write first")
    T_body_camera = np.asarray(transform, dtype=float)

    geometry = json.loads(Path(args.robot_geometry).read_text(encoding="utf-8"))
    state = json.loads(Path(args.robot_state).read_text(encoding="utf-8"))
    joints = arm_state(state, args.arm)

    matched, worst = joint_state_matches(geometry["joint_position_rad"], joints,
                                         args.joint_tolerance_rad)
    if not matched and not args.declare_stale_robot_geometry:
        raise SystemExit(
            "机器人球体描述的是另一组关节（最大差 %.4f rad > %.4f）。用旧位姿做自滤波会在\n"
            "错误的位置挖洞，把真实障碍删掉。请先按当前位姿重新导出几何，\n"
            "或显式接受并加 --declare-stale-robot-geometry（该事实会写进快照）。"
            % (worst, args.joint_tolerance_rad))

    cloud_path = Path(args.capture) / "pointcloud.ply"
    points = load_ply_m(cloud_path)
    body = (T_body_camera[:3, :3] @ points.T).T + T_body_camera[:3, 3]
    stages = []

    roi = pipeline["roi_candidates"]["global"]
    roi_arm = pipeline["roi_candidates"].get(args.arm, roi)
    used_roi = roi if args.arm == "right" else roi_arm
    cropped, record = crop_roi(body, used_roi["min_m"], used_roi["max_m"])
    stages.append(record)

    spheres = geometry["spheres"]
    filtered, record = self_filter(cropped, spheres, args.self_filter_margin_m)
    stages.append(record)

    plane = dominant_plane(filtered, threshold_m=0.02)
    support_top = float(np.median(filtered[np.abs(filtered[:, 2]
                                                   - plane["centre"][2]) < 0.02][:, 2]))
    residual, record = remove_support(filtered, support_top, args.support_half_band_m)
    stages.append(record)

    import open3d as o3d
    voxel_cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(residual))
    voxel_cloud = voxel_cloud.voxel_down_sample(args.voxel_m)
    voxels = np.asarray(voxel_cloud.points)
    labels = np.asarray(voxel_cloud.cluster_dbscan(eps=args.cluster_tolerance_m,
                                                  min_points=args.min_cluster_points,
                                                  print_progress=False))
    stages.append(dict(stage="voxel_and_cluster", before=int(len(residual)),
                       after=int(len(voxels)), voxel_m=args.voxel_m,
                       tolerance_m=args.cluster_tolerance_m,
                       clusters=int(len(set(labels.tolist()) - {-1}))))

    inflation = (float(args.inflation_m) if args.inflation_m is not None
                 else float(pipeline.get("aabb_inflation_candidate_m", 0.02)))
    target_box = None
    if args.grasp_point_mm:
        grasp_mm = np.asarray([float(v) for v in args.grasp_point_mm.split(",")])
        if grasp_mm.shape != (3,):
            raise SystemExit("--grasp-point-mm needs three comma separated millimetres")
        # The camera reports in the arm base frame; the clusters live in BODY.
        base = np.eye(4)
        base_geometry = json.loads((REPOSITORY / "config/robot_world.json")
                                   .read_text(encoding="utf-8"))["arms"][args.arm]
        roll, pitch, yaw = (float(v) for v in base_geometry["base_rpy_rad"])
        cosine, sine = np.cos(yaw), np.sin(yaw)
        base[:3, :3] = np.array([[cosine, -sine, 0.0], [sine, cosine, 0.0],
                                 [0.0, 0.0, 1.0]])
        base[:3, 3] = [float(v) for v in base_geometry["base_xyz_m"]]
        target_body = base[:3, :3] @ (grasp_mm / 1000.0) + base[:3, 3]
        print("抓取点 BODY     : %s m" % np.round(target_body, 4))

    boxes, rejected = [], 0
    for label in sorted(set(labels.tolist()) - {-1}):
        member = voxels[labels == label]
        if len(member) < args.min_cluster_voxels:
            rejected += 1
            continue
        box = aabb_from_points(member, inflation, args.min_cluster_voxels)
        if box is None:
            rejected += 1
            continue
        box["id"] = "unknown_%03d" % label
        box["role"] = "OBSTACLE"
        boxes.append(box)
    if target_body is not None and boxes:
        # The gripper has to enter the object it is about to grasp, so the cluster
        # holding the grasp point cannot also be a solid obstacle. Pick the one
        # whose box contains the point, else the nearest -- and say which.
        def distance(box):
            low = np.asarray(box["min_m"]) - inflation
            high = np.asarray(box["max_m"]) + inflation
            return float(np.linalg.norm(np.maximum(np.maximum(low - target_body, 0.0),
                                                   target_body - high)))
        chosen = min(boxes, key=distance)
        chosen["role"] = "TARGET"
        chosen["target_gap_m"] = round(distance(chosen), 6)
        target_box = chosen
        print("抓取目标簇      : %s（到抓取点 %.4f m）" % (chosen["id"], distance(chosen)))
    stages.append(dict(stage="aabb", before=int(len(voxels)),
                       after=sum(b["point_count"] for b in boxes),
                       kept=int(len(boxes)), rejected=int(rejected),
                       inflation_m=inflation,
                       target_box=target_box["id"] if target_box else None))

    coverage = self_filter_completeness(
        geometry.get("covers_parts")
        or pipeline.get("self_filter", {}).get("covers_parts", []))
    support = support_slab([used_roi["min_m"][0], used_roi["min_m"][1]],
                           [used_roi["max_m"][0], used_roi["max_m"][1]],
                           support_top, args.support_thickness_m)

    runtime = "site-" + revision.split(":")[-1][:12]
    wall_ns, mono_ns = time.time_ns(), time.monotonic_ns()
    model = WorldModel(runtime_id=runtime, snapshot_ttl_s=3600, environment_ttl_s=3600)
    model.update_robot_state(RobotState(
        wall_ns, mono_ns, runtime,
        right_joints_rad=tuple(joints) if args.arm == "right" else None,
        left_joints_rad=tuple(joints) if args.arm == "left" else None,
        source_revisions=(("provenance", PROVENANCE),
                          ("robot_state", str(args.robot_state)))))
    observation = model.begin_observation("OBS_" + Path(args.capture).name, wall_ns, mono_ns)
    cloud_ref = PointCloudRef(Path(args.capture).name, _sha256(cloud_path), "body")
    model.register_pointcloud(observation, cloud_ref)

    objects = [SceneObject("known_support_table", SceneObjectRole.FIXED, "cuboid",
                           PoseSE3("body", tuple(support["center_m"]), (1.0, 0.0, 0.0, 0.0)),
                           tuple(support["dims_m"]), 0.0, observation)]
    for box in boxes:
        role = (SceneObjectRole.TARGET if box.get("role") == "TARGET"
                else SceneObjectRole.OBSTACLE)
        objects.append(SceneObject(box["id"], role, "cuboid",
                                   PoseSE3("body", tuple(box["center_m"]),
                                           (1.0, 0.0, 0.0, 0.0)),
                                   tuple(box["dims_m"]), float(box["inflation_m"]),
                                   observation))
    model.register_obstacles(observation, objects, cloud_ref.pointcloud_id, cloud_ref.sha256)
    model.register_calibration(observation, CalibrationSet((
        ("T_body_camera", revision),
        ("robot_geometry", str(geometry.get("revision", Path(args.robot_geometry).name))),
        ("self_filter_coverage", "PARTIAL:" + ",".join(coverage["missing"]) if coverage["missing"]
         else "COMPLETE"),
        ("robot_geometry_joint_mismatch_rad", "%.6f" % worst),
        ("provenance", PROVENANCE))))
    if args.detection_id:
        model.register_detections(observation, [args.detection_id])
    model.commit_observation(observation)

    snapshot = model.freeze_snapshot(geometry["robot_model_sha256"], revision,
                                     constraints=(SafetyConstraint(
                                         "central_slab", "body_y_forbidden",
                                         (("half_width_m", 0.07),)),))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    payload = snapshot_dict(snapshot)
    (output / "snapshot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)
                                          + "\n", encoding="utf-8")
    compiled = compile_snapshot(snapshot, args.arm, geometry["T_body_model"])
    (output / "compiled_scene.json").write_text(json.dumps(compiled, indent=2) + "\n",
                                                encoding="utf-8")
    report = dict(schema_version=1, provenance=PROVENANCE, arm=args.arm,
                  capture=args.capture, pointcloud_sha256=cloud_ref.sha256,
                  T_body_camera_revision=revision, stages=stages,
                  known_support=support, unknown_residual_aabbs=boxes,
                  grasp_target=target_box["id"] if target_box else None,
                  self_filter=dict(coverage=coverage, sphere_count=len(spheres),
                                   joint_mismatch_rad=round(worst, 9),
                                   geometry_matches_capture=bool(matched),
                                   margin_m=args.self_filter_margin_m),
                  snapshot_id=snapshot.snapshot_id,
                  planning_context_digest=snapshot.planning_context_digest,
                  compiled_scene_digest=compiled["digest"],
                  recorded_at=timestamp()["wall_time_iso"],
                  limits=["planning only; execution_enabled stays false",
                          "self-filter coverage is recorded above and may be partial"])
    (output / "obstacle_world.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("点云 → 障碍 → 冻结快照（只读；未触碰相机、机械臂、规划器）")
    print("捕获            : %s" % args.capture)
    print("T_body_camera   : %s" % revision)
    print("机器人球体      : %d 个，关节最大差 %.6f rad（%s）"
          % (len(spheres), worst, "与捕获时刻一致" if matched else "**与捕获时刻不一致**"))
    print("自滤波覆盖      : %s" % ("完整" if coverage["complete"]
                                    else "**不完整，缺 %s**" % ",".join(coverage["missing"])))
    print()
    for item in stages:
        print("  %-18s %8d → %8d" % (item["stage"], item["before"], item["after"]))
    print()
    print("支撑面顶面      : BODY z = %.4f m" % support_top)
    print("未知残差 AABB   : %d 个" % len(boxes))
    for box in boxes[:8]:
        print("    %s  中心 %s  尺寸 %s"
              % (box["id"], np.round(box["center_m"], 3), np.round(box["dims_m"], 3)))
    print()
    print("快照 ID         : %s" % snapshot.snapshot_id)
    print("规划上下文摘要  : %s" % snapshot.planning_context_digest)
    print("产物            : %s" % output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
