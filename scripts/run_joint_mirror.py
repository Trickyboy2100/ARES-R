#!/usr/bin/env python3
"""Owned mirror task. Solve and validate before one supervised JAKA MoveJ."""
import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation
import yaml

from ares_r.motion.joint_mirror import JointMirrorModel
from ares_r.motion.mirror_native import snapshot as native_snapshot, supervise
from ares_r.perception.robot_collision import (
    CollisionBox, build_geometry_snapshot, mutual_arm_collisions, obb_overlap,
    transform_xyz_rpy)


def tcp_arrival_verification(world, destination, plan, sample):
    values = sample.get('tcp_mm_rad')
    if values is None:
        return dict(tcp_mirror_verified=False, reason='MIRROR_TCP_ARRIVAL_PROOF_MISSING')
    if len(values) != 6 or not np.isfinite(np.asarray(values, dtype=float)).all():
        return dict(tcp_mirror_verified=False, reason='MIRROR_TCP_ARRIVAL_PROOF_INVALID')
    mount = world['arms'][destination]
    actual_body = transform_xyz_rpy(mount['base_xyz_m'], mount['base_rpy_rad']) @ transform_xyz_rpy(
        np.asarray(values[:3])*.001, values[3:])
    goal = np.asarray(plan['tcp_target_body'])
    pe = float(np.linalg.norm(actual_body[:3, 3]-goal[:3, 3])*1000.)
    oe = float(np.degrees(Rotation.from_matrix(goal[:3, :3].T @ actual_body[:3, :3]).magnitude()))
    passed = pe <= plan['tcp_position_tolerance_mm'] and oe <= plan['tcp_orientation_tolerance_deg']
    return dict(tcp_actual_body=actual_body.tolist(), tcp_target_body=goal.tolist(),
                tcp_position_error_mm=pe, tcp_orientation_error_deg=oe,
                tcp_mirror_verified=passed, reason=None if passed else 'MIRROR_TCP_ARRIVAL_MISMATCH')


def run(request_path, output, validate_only=False):
    request = json.loads(Path(request_path).read_text())
    root = Path(request["root"])
    output = Path(output)
    (output / "live").mkdir(parents=True, exist_ok=True)
    stop = output / "stop.request"

    def status(stage, **values):
        value = dict(stage=stage, updated_at_unix=time.time(), **values)
        temporary = output / "mirror-status.tmp"
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        temporary.replace(output / "mirror-status.json")

    status("SOLVING")
    model = JointMirrorModel(root)
    live = copy.deepcopy(request.get("telemetry") or {})
    if not isinstance(live.get('arms'), dict):
        live['arms'] = {}
    source, destination = request["source_arm"], request["destination_arm"]
    if not validate_only:
        native = root / 'native/jaka_joint_mirror'
        snapshots = {}
        for side in (source, destination):
            value = native_snapshot(native, side)
            snapshots[side] = value
            world = model.world['arms'][side]
            tcp = transform_xyz_rpy(np.asarray(value['tcp_mm_rad'][:3])*.001,
                                    value['tcp_mm_rad'][3:])
            T_body_tcp = transform_xyz_rpy(world['base_xyz_m'], world['base_rpy_rad']) @ tcp
            # The legacy Python SDK may have returned None for an arm. The
            # successful isolated native snapshot is authoritative here.
            previous = live['arms'].get(side)
            live['arms'][side] = dict(previous) if isinstance(previous, dict) else {}
            live['arms'][side].update(joints_rad=value['actual_rad'],
                T_body_tcp=T_body_tcp.tolist(), tool_id=value['tool_id'],
                source='LIVE_NATIVE_ACTUAL')
            model.audits[side]['diagnostics']['tool_data'] = {
                'tool_id': value['tool_id'], 'pose_mm_rad': value['tool_mm_rad']}
        (output / 'native-before.json').write_text(json.dumps(snapshots, indent=2))
    plan = model.solve(source, destination, live, match_tcp=request.get('match_tcp', False))
    (output / "mirror-plan.json").write_text(json.dumps(plan, indent=2))
    status("CHECKING_PATH", plan=plan)
    current, target = np.asarray(plan["start_rad"]), np.asarray(plan["target_rad"])
    samples = max(81, int(np.ceil(np.max(np.abs(target - current)) / np.radians(.5))) + 1)
    audits = copy.deepcopy(model.audits)
    for side in (source, destination):
        audits[side]["diagnostics"]["joint_position_rad"] = live["arms"][side]["joints_rad"]
    robot_yaml_path = Path(request.get('robot_yaml', '/home/yikun/ares-r-curobo-assets/robot/robot.yml'))
    robot_yaml = yaml.safe_load(robot_yaml_path.read_text())
    ignored = robot_yaml.get("robot_cfg", robot_yaml)["kinematics"]["self_collision_ignore"]
    scene = json.loads((Path(request["scene_dir"]) / "scene/scene_report.json").read_text())
    environment = []
    for item in scene["objects"]:
        if item["id"] in ("body/chassis", "body_chassis_lower"):
            continue
        if item["id"].startswith("inactive_") or item["id"] in ('body/central_exclusion', 'central_body_exclusion'):
            continue
        w, x, y, z = item.get("quaternion_wxyz", [1, 0, 0, 0])
        environment.append(CollisionBox(item["id"], "environment", "obstacle",
            tuple(item["center_m"]), tuple(map(tuple, Rotation.from_quat([x, y, z, w]).as_matrix())),
            tuple(np.asarray(item["dims_m"]) / 2 + item["inflation_m"])))
    for fraction in np.linspace(0, 1, samples):
        if stop.exists():
            raise RuntimeError("STOP_REQUESTED")
        q = current + fraction * (target - current)
        audits[destination]["diagnostics"]["joint_position_rad"] = q.tolist()
        geometry = build_geometry_snapshot(model.model, model.world, audits)
        collisions = mutual_arm_collisions(geometry, destination)
        if collisions:
            raise RuntimeError("MIRROR_MUTUAL_COLLISION: " + json.dumps(collisions[:2]))
        moving = [box for box in geometry.boxes if box.owner.startswith(destination + "_")
                  and box.kind != "tcp_site_marker"]
        for i, first in enumerate(moving):
            if request.get('central_exclusion_enabled'):
                extent_y = np.abs(np.asarray(first.rotation_body)[1]) @ np.asarray(first.half_extents_m)
                nearest_y = abs(first.center_body_m[1]) - extent_y
                if nearest_y <= .07:
                    raise RuntimeError('MIRROR_CENTRAL_EXCLUSION: ' + first.geometry_id)
            for second in moving[i + 1:]:
                a, b = first.geometry_id.split("/")[-1], second.geometry_id.split("/")[-1]
                a = "4C2_baselink" if a == "gripper" else a
                b = "4C2_baselink" if b == "gripper" else b
                if b not in ignored.get(a, []) and a not in ignored.get(b, []) and obb_overlap(first, second):
                    raise RuntimeError("MIRROR_SELF_COLLISION: " + first.geometry_id + " / " + second.geometry_id)
            for obstacle in environment:
                if obb_overlap(first, obstacle):
                    raise RuntimeError("MIRROR_PATH_COLLISION: " + first.geometry_id + " / " + obstacle.geometry_id)
    plan["validated_samples"] = samples
    plan["scene_snapshot_id"] = request["scene_snapshot_id"]
    plan["speed_rad_s"] = .08
    plan["chassis_policy"] = "GLOBAL_CHASSIS_DISABLED_OPERATOR_20261116_V1"
    (output / "mirror-plan.json").write_text(json.dumps(plan, indent=2))
    if validate_only:
        status("VALIDATED", plan=plan, execution_requested=False)
        return
    if stop.exists():
        raise RuntimeError("STOP_REQUESTED")
    values = output / "native-values.txt"
    contents = "\n".join(" ".join(map(str, row)) for row in
        (plan["start_rad"], plan["target_rad"])) + "\n"
    if plan.get('tool_binding'):
        tool = plan['tool_binding'][destination]
        contents += str(tool['tool_id']) + ' ' + ' '.join(map(str, tool['pose_mm_rad'])) + '\n'
    values.write_text(contents)
    status("EXECUTING", plan=plan)
    returncode = supervise(root / 'native/jaka_joint_mirror', destination, values, stop,
                           plan['source_joints_rad'], output / 'live/native_supervised.jsonl',
                           reference_tool_id=live['arms'][source].get('tool_id'))
    events = []
    for line in (output / "live/native_supervised.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    reached = returncode == 0 and bool(events) and events[-1].get("completed") is True
    failure = next((event.get('reason') for event in reversed(events) if event.get('event') == 'failed'), None)
    result = {"success": reached, "target_reached": reached, "returncode": returncode,
              "motion_api": "JAKA joint_move", "servo_mode_used": False,
              "source_arm": source, "destination_arm": destination,
              "reason": None if reached else (failure or "native MoveJ did not confirm arrival"),
              "final_sample": events[-1] if events else None}
    if reached:
        actual_points = model.frames(destination, events[-1]['actual_rad'])[:, :3, 3]
        result['joint_point_error_mm'] = (np.linalg.norm(actual_points - np.asarray(
            plan['target_joint_points_body_m']), axis=1) * 1000).tolist()
        if plan.get('tcp_target_body'):
            verification = tcp_arrival_verification(model.world, destination, plan, events[-1])
            reached = verification['tcp_mirror_verified']
            result.update(verification, success=reached, target_reached=reached)
    (output / "live/execution_result.json").write_text(json.dumps(result, indent=2))
    status("COMPLETED" if reached else "FAULT", plan=plan, result=result)
    if not reached:
        raise RuntimeError(result["reason"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        run(args.request, args.output, args.validate_only)
    except BaseException as error:
        output = Path(args.output)
        (output / "live").mkdir(parents=True, exist_ok=True)
        result_path = output / 'live/execution_result.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        result.update(success=False, target_reached=False, reason=str(error))
        result_path.write_text(json.dumps(result, indent=2))
        status_path = output / 'mirror-status.json'
        previous = json.loads(status_path.read_text()) if status_path.exists() else {}
        previous.update(stage='FAULT', error=str(error), failed_stage=previous.get('stage'))
        temporary = output / "mirror-status.tmp"
        temporary.write_text(json.dumps(previous, indent=2))
        temporary.replace(output / "mirror-status.json")
        raise
