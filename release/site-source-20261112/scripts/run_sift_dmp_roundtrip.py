#!/usr/bin/env python3
"""demo-4 · SIFT筛网抓取 → 抬升230mm → 底盘转场(SIFT→DMP) → DMP筛网放置 → 回center.

四个阶段互不重复实现已有能力：
  1) pick    完全复用 demo3 链路（`scripts/prepare_sift_lift_hold.py` +
             `scripts/run_sift_lift_hold.py`），本 Demo 只做编排与证据汇总
  2) transit 读 `config/manipulation_stations.json`，先原地旋转到目标 yaw，
             再按 BODY 相对方向平移；站位可被操作员随时重新登记
  3) place   5700 抓取配置 ID2 检测 → 预放置点（检测点 + 可配偏移）→
             cuRobo 规划（硬水平 + FAST→QUALITY→QUALITY 重试）→
             下降（默认 60 mm，BODY −Z）→ 松爪
  4) center  回到全局 center（`task_contract.center_goal`）

安全：必须 `--execute --onsite-observer-confirmed`；每个输出目录只允许派发一次；
控制器 errcode/保护停未清零时拒绝任何运动；执行前用当次最新扫描复核目标碰撞。

用法：
  干跑（只做检测与规划，不动）：python scripts/run_sift_dmp_roundtrip.py \
      --output worklog/evidence/demo-runs/right_arm_sift_dmp_roundtrip_v1/<run> --stage all
  实机：加 --execute --onsite-observer-confirmed
  单段：--stage place   /   --stage transit   /   --stage center   /   --stage pick
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

DEMO_ID = 'right_arm_sift_dmp_roundtrip_v1'
BASE_URL = 'http://127.0.0.1:8775'
PICK_PREPARE = ROOT / 'scripts/prepare_sift_lift_hold.py'
PICK_RUN = ROOT / 'scripts/run_sift_lift_hold.py'
GRIPPER = ROOT / 'scripts/gripper_direct_once.py'


# --------------------------------------------------------------------------- io
def api(path, body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(Request(BASE_URL + path, data=data,
                             headers={'Content-Type': 'application/json'}),
                    timeout=timeout) as stream:
            return json.load(stream)
    except HTTPError as exc:
        raise SystemExit('%s -> %s: %s' % (path, exc.code, exc.read().decode()[-800:])) from exc


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')
    temporary.replace(path)


def load(path):
    return json.loads(Path(path).read_text())


def telemetry():
    return api('/api/operations/telemetry', {}, timeout=40)


def tcp_of(state, arm='right'):
    return np.asarray(state['arms'][arm]['T_body_tcp'], dtype=float)


def controller_guard(state, arm='right'):
    status = state['arms'][arm]['controller_status']
    bad = {k: status.get(k) for k in ('errcode', 'emergency_stop', 'protective_stop',
                                      'on_soft_limit') if status.get(k)}
    if bad:
        raise SystemExit('controller not clear on %s arm: %s' % (arm, bad))
    if not status.get('enabled'):
        raise SystemExit('%s arm not enabled' % arm)


def inactive_arm_guard(state, reference, arm='left'):
    current, before = state['arms'][arm], reference['arms'][arm]
    if current['tool_id'] != before['tool_id']:
        raise SystemExit('%s arm tool changed' % arm)
    if any(abs(a - b) > math.radians(0.02)
           for a, b in zip(current['joints_rad'], before['joints_rad'])):
        raise SystemExit('%s arm moved' % arm)


# ------------------------------------------------------------------- planning
def level_orientation(state, yaw_rad=None):
    from ares_r.motion.tcp_orientation import (level_rotation, nearest_level_roll_branch,
                                               tcp_yaw_rad)
    rotation = tcp_of(state)[:3, :3]
    yaw = tcp_yaw_rad(rotation) if yaw_rad is None else float(yaw_rad)
    branch = nearest_level_roll_branch(rotation)
    return np.asarray(level_rotation(yaw, branch), dtype=float), yaw, branch


def prove_plan(record, label, out, *, tolerance_deg, final_yaw_rad=None,
               descent_m=None, strict_descent=False):
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    from ares_r.motion.tcp_orientation import validate_level_path
    artifact = ROOT / record['plan_artifact']
    plan = load(artifact / 'planning.json')
    request = load(artifact / 'planner_request.json')
    ik = RuntimeGoalIK(request['robot_yaml_urdf'], request['T_body_model'],
                       request['T_link6_tcp'])
    points = plan['trajectory_points_rad']
    level = validate_level_path(ik.fk, points, tolerance_deg=float(tolerance_deg),
                                subdivisions=4, final_yaw_rad=final_yaw_rad)
    save(out / ('%s.level.json' % label), level)
    if not level.get('passed'):
        raise SystemExit('%s: hard-horizontal failed %s'
                         % (label, {k: level.get(k) for k in
                                    ('max_level_error_deg', 'final_yaw_error_deg')}))
    if descent_m is None:
        return level
    from ares_r.manipulation.task_tcp_offset import validate_body_descent
    try:
        proof = validate_body_descent(points, ik.fk, float(descent_m), tolerance_m=0.003)
    except Exception as exc:                                  # noqa: BLE001
        save(out / ('%s.axis-proof.json' % label), dict(passed=False, error=str(exc)))
        if strict_descent:
            raise SystemExit('%s: descent axis proof failed: %s' % (label, exc)) from exc
        print('%s: WARNING not a straight BODY -Z line (%s); net displacement verified '
              'after execution' % (label, exc), flush=True)
        return dict(passed=False)
    save(out / ('%s.axis-proof.json' % label), proof)
    return proof


def plan_leg(payload, label, out, deadline_s, *, tolerance_deg, final_yaw_rad=None,
             descent_m=None, rounds=3, strict_descent=False):
    scene_before = api('/api/scene/status')['base_pose_revision']
    history = []
    for attempt in range(1, max(1, rounds) + 1):
        tag = '%s_r%d' % (label, attempt)
        for index, mode in enumerate(('FAST', 'QUALITY', 'QUALITY'), start=1):
            if api('/api/scene/status')['base_pose_revision'] != scene_before:
                raise SystemExit('base pose changed during planning; target invalid')
            trial = dict(payload, planning_mode=mode, request_label='%s_TRY%d' % (tag, index))
            started = time.monotonic()
            try:
                handle = api('/api/motion/plan', trial, timeout=deadline_s + 120)
            except SystemExit as exc:
                history.append(dict(round=attempt, attempt=index, mode=mode,
                                    error=str(exc)[-300:]))
                save(out / ('%s.attempt%d.json' % (tag, index)), history[-1])
                continue
            step = dict(round=attempt, attempt=index, mode=mode,
                        elapsed_s=round(time.monotonic() - started, 3),
                        plan_id=handle.get('plan_id'), ready=handle.get('execution_package_ready'),
                        error=handle.get('execution_package_error'))
            history.append(step)
            save(out / ('%s.attempt%d.json' % (tag, index)), step)
            if not handle.get('execution_package_ready'):
                continue
            record = dict(plan_id=handle['plan_id'], trajectory_hash=handle['trajectory_hash'],
                          scene_snapshot_id=handle.get('scene_snapshot_id'),
                          plan_artifact=handle.get('plan_artifact'), planning_mode=mode,
                          attempts=history)
            try:
                prove_plan(record, tag, out, tolerance_deg=tolerance_deg,
                           final_yaw_rad=final_yaw_rad, descent_m=descent_m,
                           strict_descent=strict_descent)
            except SystemExit as exc:
                step['rejected'] = str(exc)[-300:]
                save(out / ('%s.attempt%d.json' % (tag, index)), step)
                continue
            save(out / ('%s.plan_handle.json' % tag), handle)
            return record
    save(out / ('%s.failed.json' % label), history)
    raise SystemExit('%s: no accepted plan after %d rounds' % (label, rounds))


def execute_plan(record, label, out, timeout_s=600):
    body = dict(plan_id=record['plan_id'], trajectory_hash=record['trajectory_hash'],
                authorization=record['authorization'], onsite_observer_confirmed=True,
                command_id='%s_%s_%d' % (DEMO_ID.upper(), label.upper(), int(time.time() * 1000
                                                                              % 10 ** 9)))
    save(out / ('%s.start.json' % label), api('/api/operations/execute', body, timeout=120))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = api('/api/operations/run-status', timeout=30)
        if state.get('state') != 'RUNNING':
            save(out / ('%s.result.json' % label), state)
            if state.get('state') != 'SUCCEEDED':
                raise SystemExit('%s failed: %s / %s' % (label, state.get('state'),
                                                         state.get('study_error')))
            result = state.get('execution_result') or {}
            print(json.dumps(dict(label=label, state=state['state'],
                                  elapsed_s=result.get('elapsed_s'),
                                  tracking_error_deg=(result.get('tracking_error_deg') or {}
                                                      ).get('max')),
                             ensure_ascii=False), flush=True)
            return state
        time.sleep(0.8)
    raise SystemExit('%s: timeout without terminal state' % label)


# ------------------------------------------------------------------- stage 1
def stage_pick(params, out, execute):
    stage = params['stages']['sift_pick_lift230']
    out.mkdir(parents=True, exist_ok=False)
    prepared = subprocess.run([sys.executable, str(PICK_PREPARE)], cwd=ROOT,
                              capture_output=True, text=True, timeout=1800)
    (out / 'prepare.log').write_text(prepared.stdout + prepared.stderr)
    if prepared.returncode:
        raise SystemExit('pick/lift preparation failed: %s' % prepared.stderr[-800:])
    record = json.loads(prepared.stdout.strip().splitlines()[-1])
    save(out / 'preparation.json', record)
    print('prepared:', record['prepared'], flush=True)
    if not execute:
        print(json.dumps(dict(stage='pick', state='PREPARED_ONLY',
                              prepared=record['prepared']), ensure_ascii=False))
        return dict(state='PREPARED_ONLY', prepared=record['prepared'])
    run = subprocess.run([sys.executable, str(PICK_RUN), '--prepared', record['prepared'],
                          '--output', str(out / 'hold'), '--authorization',
                          stage['authorization'], '--onsite-observer-confirmed'],
                         cwd=ROOT, capture_output=True, text=True, timeout=3600)
    (out / 'hold.log').write_text(run.stdout + run.stderr)
    if run.returncode:
        raise SystemExit('pick/lift hold failed: %s' % run.stderr[-1200:])
    hold = load(Path(record['prepared']) / 'hold-contract.json') \
        if (Path(record['prepared']) / 'hold-contract.json').exists() else {}
    save(out / 'hold-contract-copy.json', hold)
    print(json.dumps(dict(stage='pick', state='HOLDING', prepared=record['prepared']),
                     ensure_ascii=False))
    return dict(state='HOLDING', prepared=record['prepared'])


# ------------------------------------------------------------------- stage 2
def base_pose():
    state = telemetry()
    info = (state.get('base') or {}).get('info') or {}
    if 'x' not in info:
        raise SystemExit('AMR base pose unavailable')
    return (float(info['x']), float(info['y']), float(info['yawNumber'])), info


def base_samples(count=8, interval_s=0.5):
    rows = []
    for index in range(count):
        pose, info = base_pose()
        rows.append(dict(pose=pose, confidence=info.get('confidence')))
        if index + 1 < count:
            time.sleep(interval_s)
    return rows


def base_stability(profile, label, out, *, required):
    """采样多个 SLAM 帧，判定报告位姿是否稳定；不稳定则默认拒绝运动。"""
    rows = base_samples(int(profile.get('samples', 8)), float(profile.get('interval_s', 0.5)))
    xs = [r['pose'][0] for r in rows]
    ys = [r['pose'][1] for r in rows]
    yaws = [r['pose'][2] for r in rows]
    span = dict(x_m=max(xs) - min(xs), y_m=max(ys) - min(ys),
                yaw_deg=max(yaws) - min(yaws))
    confidence = min(float(r['confidence']) for r in rows if r['confidence'] is not None) \
        if any(r['confidence'] is not None for r in rows) else None
    stable = (span['x_m'] <= float(profile.get('max_span_m', 0.04))
              and span['y_m'] <= float(profile.get('max_span_m', 0.04))
              and span['yaw_deg'] <= float(profile.get('max_span_yaw_deg', 1.0))
              and (confidence is None or confidence >= float(profile.get('min_confidence', 35))))
    record = dict(label=label, stable=stable, samples=len(rows), span=span,
                  min_confidence=confidence,
                  mean_pose=[sum(xs) / len(xs), sum(ys) / len(ys), sum(yaws) / len(yaws)],
                  thresholds=profile, required=bool(required))
    save(out / ('base-stability-%s.json' % label), record)
    if required and not stable:
        raise SystemExit('BASE_LOCALIZATION_UNSTABLE at %s: span=%s confidence=%s '
                         '(relocalize the AMR first)' % (label, span, confidence))
    if not stable:
        print('WARNING base localization unstable at %s: span=%s' % (label, span), flush=True)
    return record


def wrap_deg(angle):
    return (angle + 180.0) % 360.0 - 180.0


def remaining_body(target, current):
    dx, dy = target[0] - current[0], target[1] - current[1]
    yaw = math.radians(current[2])
    return (dx * math.cos(yaw) + dy * math.sin(yaw),
            -dx * math.sin(yaw) + dy * math.cos(yaw),
            wrap_deg(target[2] - current[2]))


def stage_transit(params, out, execute, from_station, to_station):
    stage = params['stages']['base_transit']
    out.mkdir(parents=True, exist_ok=False)
    stations = load(ROOT / stage['stations_config'])['stations']
    target = tuple(float(stations[to_station]['slam_pose'][k]) for k in ('x_m', 'y_m', 'yaw_deg'))
    current, info = base_pose()
    save(out / 'transit-contract.json', dict(
        from_station=from_station, to_station=to_station, target=target,
        start_pose=current, order=stage['order'], linear_mps=stage['linear_mps'],
        max_translation_leg_m=stage['max_translation_leg_m'],
        max_rotation_leg_deg=stage['max_rotation_leg_deg'],
        position_tolerance_m=stage['position_tolerance_m'],
        yaw_tolerance_deg=stage['yaw_tolerance_deg'],
        authorization=stage['authorization'], execute=bool(execute),
        stations_revision=load(ROOT / stage['stations_config']).get('revision')))
    legs = []
    simulated = current
    stability = params['platform'].get('base_stability') or {}
    if execute and stability:
        base_stability(stability, 'pre-transit', out, required=True)
    for index in range(1, int(stage['max_legs']) + 1):
        current, info = (base_pose() if execute else (simulated, info))
        body_x, body_y, dyaw = remaining_body(target, current)
        distance = math.hypot(body_x, body_y)
        if distance <= stage['position_tolerance_m'] and abs(dyaw) <= stage['yaw_tolerance_deg']:
            save(out / 'transit-result.json', dict(state='CONVERGED', final_pose=current,
                                                   legs=legs))
            print(json.dumps(dict(stage='transit', state='CONVERGED',
                                  pose=[round(v, 4) for v in current]), ensure_ascii=False))
            return dict(state='CONVERGED', final_pose=current)
        if abs(dyaw) > stage['yaw_tolerance_deg']:          # 先旋转
            step = max(-stage['max_rotation_leg_deg'],
                       min(stage['max_rotation_leg_deg'], dyaw))
            command = dict(x_m=0.0, y_m=0.0, yaw_deg=round(step, 6),
                           linear_mps=stage['linear_mps'])
            kind = 'ROTATE'
        else:                                               # 再平移
            step = min(stage['max_translation_leg_m'], distance)
            command = dict(x_m=round(body_x / distance * step, 6),
                           y_m=round(body_y / distance * step, 6),
                           yaw_deg=0.0, linear_mps=stage['linear_mps'])
            kind = 'TRANSLATE'
        preview = api('/api/operations/base-preview', command, timeout=120)
        leg = dict(leg=index, kind=kind, command=command, preview=preview,
                   before_pose=current, remaining=dict(body_x=body_x, body_y=body_y,
                                                       dyaw_deg=dyaw, distance_m=distance))
        if not execute:
            legs.append(leg)
            yaw_now = math.radians(current[2])
            if kind == 'ROTATE':
                simulated = (current[0], current[1], wrap_deg(current[2] + step))
            else:
                simulated = (current[0] + command['x_m'] * math.cos(yaw_now)
                             - command['y_m'] * math.sin(yaw_now),
                             current[1] + command['x_m'] * math.sin(yaw_now)
                             + command['y_m'] * math.cos(yaw_now),
                             current[2])
            continue
        if stage['invalidate_scene_before_motion']:
            api('/api/scene/invalidate', {'reason': 'BASE_TRANSIT_%d' % index}, timeout=60)
        dispatch = dict(command, authorization=stage['authorization'],
                        command_id='%s_TRANSIT_%d_%d' % (DEMO_ID.upper(), int(time.time()), index))
        started = time.monotonic()
        leg['result'] = api('/api/operations/base-move', dispatch, timeout=300)
        time.sleep(float(stage['settle_s']))
        after, after_info = base_pose()
        reported = (after[0] - current[0], after[1] - current[1])
        commanded = (command['x_m'], command['y_m'])
        yaw_now = math.radians(current[2])
        commanded_map = (commanded[0] * math.cos(yaw_now) - commanded[1] * math.sin(yaw_now),
                         commanded[0] * math.sin(yaw_now) + commanded[1] * math.cos(yaw_now))
        consistency = math.hypot(reported[0] - commanded_map[0], reported[1] - commanded_map[1])
        leg.update(after_pose=after, wall_s=round(time.monotonic() - started, 3),
                   after_confidence=after_info.get('confidence'),
                   reported_displacement_m=reported, commanded_displacement_m=commanded_map,
                   consistency_error_mm=round(consistency * 1000, 1))
        legs.append(leg)
        save(out / ('leg-%d.json' % index), leg)
        print(json.dumps({k: leg[k] for k in ('leg', 'kind', 'command', 'after_pose')},
                         ensure_ascii=False), flush=True)
        if leg['result'].get('state') != 'SUCCEEDED':
            save(out / 'transit-result.json', dict(state='FAULT', legs=legs))
            raise SystemExit('base leg %d not SUCCEEDED: %s' % (index, leg['result'].get('state')))
        if stability:
            base_stability(stability, 'leg%d' % index, out, required=False)
    save(out / 'transit-result.json', dict(state='PREVIEW_ONLY' if not execute else 'INCOMPLETE',
                                           legs=legs))
    if not execute:
        print(json.dumps(dict(stage='transit', state='PREVIEW_ONLY', legs=len(legs)),
                         ensure_ascii=False))
        return dict(state='PREVIEW_ONLY')
    raise SystemExit('base transit did not converge in %d legs' % stage['max_legs'])


# ------------------------------------------------------------------- stage 3
def detect_place_target(params, out):
    from ares_r.adapters.epic import EpicClient
    from ares_r.motion.grasp import rotation_matrix
    from ares_r.perception.robot_collision import transform_xyz_rpy
    from ares_r.world_geometry import base_tcp_to_world

    stage = params['stages']['dmp_place']
    config = load(ROOT / 'config/system.json')
    profile = config['epic']['task_profiles'][stage['epic_profile']]
    profile['space_id'] = int(stage['epic_space_id'])
    profile['object_id'] = int(stage['epic_grasp_config_id'])
    profile['camera_id'] = int(stage['epic_camera_id'])
    profile['command'] = '320,%d,%d,%d,1,0' % (stage['epic_space_id'],
                                               stage['epic_grasp_config_id'],
                                               stage['epic_camera_id'])
    epic = EpicClient(config['epic'])
    try:
        detection = epic._detect_profile(stage['epic_profile'], 'dmp-place')
    finally:
        epic.close()
    record = dict(epic_command=profile['command'], success=bool(detection.success),
                  raw_response=detection.raw_response,
                  error=None if detection.success else str(detection.error),
                  captured_at_unix=time.time())
    if not detection.success:
        save(out / 'detection.json', record)
        raise SystemExit('place detection failed: %s' % record['error'])
    pose = [float(v) for v in detection.pose.values()]
    world = load(ROOT / 'config/robot_world.json')
    body = base_tcp_to_world(world['arms']['right'],
                             [v * 1000.0 for v in pose[:3]] + pose[3:])
    record.update(detection_pose_mm_rad=pose, detection_body_m_rad=body,
                  detection_rotation=np.asarray(rotation_matrix(*pose[3:])).tolist(),
                  detection_body_rpy_deg=[math.degrees(v) for v in pose[3:]])
    save(out / 'detection.json', record)
    print(json.dumps(dict(stage='place', state='DETECTED',
                          detection_body_m_rad=[round(v, 5) for v in body[:3]]),
                     ensure_ascii=False))
    return record


def stage_place(params, out, execute, offset_override=None, descent_override=None,
                yaw_override=None):
    stage = params['stages']['dmp_place']
    platform = params['platform']
    out.mkdir(parents=True, exist_ok=False)
    deadline = float(load(ROOT / 'config/system.json')['curobo']['timeout_s'])
    offset = [float(v) for v in (offset_override or stage['preplace_offset_body_m'])]
    descent = float(descent_override if descent_override is not None else stage['descent_m'])

    detection = detect_place_target(params, out)
    base_point = [float(v) for v in detection['detection_body_m_rad'][:3]]
    preplace = [base_point[0] + offset[0], base_point[1] + offset[1], base_point[2] + offset[2]]
    place = [preplace[0], preplace[1], preplace[2] - descent]

    state = telemetry()
    controller_guard(state)
    reference = dict(arms=state['arms'])
    yaw_requested = yaw_override if yaw_override is not None else stage.get('yaw_target_deg')
    rotation, yaw, branch = level_orientation(
        state, None if yaw_requested is None else math.radians(float(yaw_requested)))
    save(out / 'place-contract.json', dict(
        detection_body_m_rad=base_point, offset_body_m=offset, preplace_body_m=preplace,
        place_body_m=place, descent_m=descent, yaw_target_rad=yaw, roll_branch=branch,
        release_raw=stage['release_raw'], level_tolerance_deg=platform['level_tolerance_deg'],
        planning_modes=platform['planning_modes'], rounds=platform['planning_rounds'],
        authorization=stage['authorization'], execute=bool(execute)))

    def payload(position, label, scene_policy):
        body = dict(arm='right', position_m=[float(v) for v in position],
                    orientation='TERMINAL_EXPLICIT', explicit_rotation=rotation.tolist(),
                    speed_profile=platform['motion_speed_profile'], scene_policy=scene_policy,
                    environment_avoidance=platform['environment_avoidance'],
                    source=DEMO_ID.upper(), request_label=label)
        return body

    common = dict(tolerance_deg=platform['level_tolerance_deg'], final_yaw_rad=yaw,
                  rounds=int(platform['planning_rounds']))
    pre = plan_leg(payload(preplace, 'DMP_PREPLACE', platform['scene_policy_transit']),
                   'preplace', out, deadline, **common)
    pre['authorization'] = stage['authorization']
    descending = plan_leg(payload(place, 'DMP_DESCENT', platform['scene_policy_transit']),
                          'descend', out, deadline, descent_m=descent, **common)
    descending['authorization'] = stage['authorization']
    center_point = None
    if params['stages']['return_center']['enabled']:
        from ares_r.manipulation.task_contract import center_goal
        goal = center_goal(ROOT)
        center_point = dict(position_m=goal['position_m'],
                            explicit_rotation=goal['explicit_rotation'])
        save(out / 'center-goal.json', goal)
    save(out / 'plans.json', dict(preplace={k: v for k, v in pre.items() if k != 'attempts'},
                                  descend={k: v for k, v in descending.items() if k != 'attempts'}))
    if not execute:
        print(json.dumps(dict(stage='place', state='PLANNED_ONLY',
                              preplace=pre['plan_id'], descend=descending['plan_id'],
                              preplace_body_m=[round(v, 5) for v in preplace],
                              place_body_m=[round(v, 5) for v in place]),
                         ensure_ascii=False))
        return dict(state='PLANNED_ONLY')

    execute_plan(pre, 'preplace', out)
    arrived = tcp_of(telemetry())[:3, 3]
    error = float(np.linalg.norm(arrived - np.asarray(preplace)))
    save(out / 'preplace-arrival.json', dict(target=preplace, tcp=arrived.tolist(), error_m=error))
    if error > platform['arrival_tolerance_m']:
        raise SystemExit('preplace arrival error %.1f mm' % (error * 1000))

    execute_plan(descending, 'descend', out)
    before = tcp_of(telemetry())[:3, 3]
    delta = before - arrived
    save(out / 'descent-check.json', dict(before_m=arrived.tolist(), after_m=before.tolist(),
                                          delta_m=delta.tolist(), target_m=place))
    if (abs(delta[0]) > platform['descent_tolerance_m']
            or abs(delta[1]) > platform['descent_tolerance_m']
            or abs(delta[2] + descent) > platform['descent_tolerance_m']):
        raise SystemExit('descent is not a %.0f mm BODY -Z move: %s'
                         % (descent * 1000, np.round(delta, 4).tolist()))

    subprocess.run([sys.executable, str(GRIPPER), 'move', '--raw', str(stage['release_raw'])],
                   cwd=ROOT, capture_output=True, text=True, timeout=40)
    time.sleep(1.0)
    status = subprocess.run([sys.executable, str(GRIPPER), 'status'], cwd=ROOT,
                            capture_output=True, text=True, timeout=40)
    raw = None
    try:
        raw = json.loads(status.stdout.strip().splitlines()[-1]).get('position_raw')
    except ValueError:
        pass
    save(out / 'release.json', dict(target_raw=stage['release_raw'], readback_raw=raw,
                                    stdout=status.stdout.strip()[-300:]))
    if raw is None or abs(float(raw) - float(stage['release_raw'])) > float(
            stage['release_readback_tolerance_raw']):
        raise SystemExit('release not confirmed: readback %s' % raw)
    inactive_arm_guard(telemetry(), reference)
    print(json.dumps(dict(stage='place', state='PLACED_AND_RELEASED',
                          tcp=[round(v, 5) for v in before]), ensure_ascii=False))
    return dict(state='PLACED_AND_RELEASED', center_goal=center_point)


# ------------------------------------------------------------------- stage 4
def stage_center(params, out, execute):
    from ares_r.manipulation.task_contract import center_goal
    stage = params['stages']['return_center']
    platform = params['platform']
    out.mkdir(parents=True, exist_ok=False)
    deadline = float(load(ROOT / 'config/system.json')['curobo']['timeout_s'])
    goal = center_goal(ROOT)
    state = telemetry()
    controller_guard(state)
    payload = dict(arm='right', position_m=[float(v) for v in goal['position_m']],
                   orientation='TERMINAL_EXPLICIT',
                   explicit_rotation=goal['explicit_rotation'],
                   speed_profile=platform['motion_speed_profile'],
                   scene_policy=platform['scene_policy_center'],
                   environment_avoidance=platform['environment_avoidance'],
                   source=DEMO_ID.upper(), request_label='RETURN_CENTER')
    record = plan_leg(payload, 'center', out, deadline, tolerance_deg=90.0, rounds=1)
    record['authorization'] = stage['authorization']
    save(out / 'center-goal.json', goal)
    if not execute:
        print(json.dumps(dict(stage='center', state='PLANNED_ONLY',
                              plan_id=record['plan_id']), ensure_ascii=False))
        return dict(state='PLANNED_ONLY')
    execute_plan(record, 'center', out)
    from ares_r.manipulation.task_contract import check_center, load_contract
    final = telemetry()
    check = check_center(ROOT, final, load_contract(ROOT))
    save(out / 'center-check.json', check)
    print(json.dumps(dict(stage='center', state='AT_CENTER',
                          position_error_mm=round(check['position_error_m'] * 1000, 3),
                          orientation_error_deg=round(check['orientation_error_deg'], 4)),
                     ensure_ascii=False))
    return dict(state='AT_CENTER', check=check)


# ---------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True, help='本次运行的证据根目录')
    parser.add_argument('--stage', choices=('all', 'pick', 'transit', 'place', 'center'),
                        default='all')
    parser.add_argument('--from-station', default=None)
    parser.add_argument('--to-station', default=None)
    parser.add_argument('--preplace-offset', type=float, nargs=3, default=None,
                        help='覆盖预放置点偏移（BODY 相对检测点，米）')
    parser.add_argument('--descent-m', type=float, default=None)
    parser.add_argument('--yaw-deg', type=float, default=None,
                        help='覆盖放置目标偏航（BODY 度）')
    parser.add_argument('--parameters', type=Path,
                        default=ROOT / 'demos' / DEMO_ID / 'parameters.json')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--onsite-observer-confirmed', action='store_true')
    args = parser.parse_args()

    params = load(args.parameters)
    if args.execute and not args.onsite_observer_confirmed:
        raise SystemExit('实机执行需要 --onsite-observer-confirmed（现场确认）')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    marker = out / 'demo-run.json'
    if args.execute:
        if marker.exists():
            raise SystemExit('该输出目录已派发过，拒绝重复执行：%s' % marker)
        status = api('/api/operations/run-status', timeout=30)
        if status.get('state') == 'RUNNING':
            raise SystemExit('another physical task running: %s' % status)
        save(marker, dict(armed_at_unix=time.time(), demo_id=DEMO_ID, stage=args.stage,
                          parameters=str(args.parameters),
                          overrides=dict(preplace_offset=args.preplace_offset,
                                         descent_m=args.descent_m, yaw_deg=args.yaw_deg)))
    else:
        save(out / 'dry-run.json', dict(at_unix=time.time(), demo_id=DEMO_ID,
                                        stage=args.stage))

    results = {}
    run_pick = args.stage in ('all', 'pick')
    run_transit = args.stage in ('all', 'transit')
    run_place = args.stage in ('all', 'place')
    run_center = args.stage in ('all', 'center')
    if run_pick:
        results['pick'] = stage_pick(params, out / '01-sift-pick-lift230', args.execute)
    if run_transit:
        from_station = args.from_station or params['stages']['base_transit']['from_station']
        to_station = args.to_station or params['stages']['base_transit']['to_station']
        results['transit'] = stage_transit(params, out / '02-base-transit', args.execute,
                                           from_station, to_station)
    if run_place:
        results['place'] = stage_place(params, out / '03-dmp-place', args.execute,
                                       args.preplace_offset, args.descent_m, args.yaw_deg)
    if run_center:
        results['center'] = stage_center(params, out / '04-return-center', args.execute)
    save(out / 'summary.json', results)
    print(json.dumps(dict(demo_id=DEMO_ID, output=str(out),
                          states={k: v.get('state') for k, v in results.items()}),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
