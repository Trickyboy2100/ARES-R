#!/usr/bin/env python3
"""demo-0 · 右臂从任意静止位姿用 cuRobo 规划回全局 named center。

设计要点
--------
- 目标来自 `ares_r.manipulation.task_contract.center_goal`（BODY TCP），与
  `check_center` 使用同一份合同，不另立一套 center 定义。
- 每轮都 `FORCE_RESCAN` 新扫描 + 新规划，并在 300 s 计划窗口内**当次派发**；
  绝不复用历史 plan。
- 站点速度上限必须是 `parameters.json` 要求的 0.2（读
  `config/jaka_mini2_motion.site.json`）；不满足就拒绝，而不是悄悄跑慢。
- 工具号/工具位姿一律实时读取并记录，不写死 tool_id（控制器 2026-11-04 起
  右臂工具为 tcp3）。
- 起点已与夹具干涉时（`INVALID_START_COLLISION`）直接拒绝，并打印穿透对象与
  深度，提示人工挪开后再跑；不做任何运动。
- 到位后按 center 合同（默认 3 mm / 3°）复核，写 `result.json` 与
  `last-run.json`（供控制台读取）。

用法
----
  PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --prepare
  PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --execute \
      --authorization 'RIGHT RETURN CENTER' --onsite-observer-confirmed
  PYTHONPATH=src .venv/bin/python scripts/run_return_center_demo.py --stop
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

DEMO_ID = 'right_arm_return_center_v1'
SITE_FILE = ROOT / 'config/jaka_mini2_motion.site.json'
PARAMETERS = ROOT / 'demos' / DEMO_ID / 'parameters.json'
EVIDENCE_ROOT = ROOT / 'worklog/evidence/demo-runs' / DEMO_ID
LAST_RUN = EVIDENCE_ROOT / 'last-run.json'
BASE_URL = os.environ.get('ARES_R_ROUNDTRIP_API_URL', 'http://127.0.0.1:8775').rstrip('/')
SCENE_CAPTURE = 'FORCE_RESCAN'

#: Only ``remaining_observed`` residual clusters this close may trigger the extra
#: FORCE_RESCAN attempt on an INVALID_START_COLLISION (see residual_start_collision).
RESIDUAL_START_OBJECT_PREFIXES = ('observed_remaining_observed_unknown_occupied_',)
RESIDUAL_START_CLEARANCE_M = 0.010
#: canonical_backend validates `/api/operations/execute` against this exact phrase
#: (canonical_backend.py:_motion_execute_once). The demo's own operator phrase is
#: `parameters.json:authorization_phrase`, checked before anything is planned.
MOTION_API_AUTHORIZATION = 'RIGHT SCENE_AWARE SUPERVISED'
#: `DemoConsole.permits()` only lets the owning job call these endpoints while the
#: console holds the execution resources; `console.command()` exports the token.
CONSOLE_TOKEN = os.environ.get('ARES_R_DEMO_CONSOLE_TOKEN')
TOKEN_ENDPOINTS = ('/api/operations/execute', '/api/operations/base-move')
#: Known controller transient: the sender aborts at servo activation, before any
#: motion sample, with this errcode. Retried exactly once, and only when the arm
#: provably has not moved (see `transient_zero_motion_failure`).
TRANSIENT_SAFETY_GATE = 'controller safety gate errcode=4128769'
UNMOVED_TOLERANCE_DEG = 0.2


class ApiError(RuntimeError):
    def __init__(self, path, code, body):
        self.path, self.code, self.body = path, code, body
        super().__init__('%s -> %s: %s' % (path, code, body[-1200:]))


def api(path, body=None, timeout=900):
    if body is not None and CONSOLE_TOKEN and path in TOKEN_ENDPOINTS:
        body = dict(body, demo_console_token=CONSOLE_TOKEN)
    data = None if body is None else json.dumps(body).encode()
    try:
        with urlopen(Request(BASE_URL + path, data=data,
                             headers={'Content-Type': 'application/json'}),
                    timeout=timeout) as stream:
            return json.load(stream)
    except HTTPError as exc:
        raise ApiError(path, exc.code, exc.read().decode()) from exc


def load(path, default=None):
    path = Path(path)
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')
    os.replace(temporary, path)


def emit(**values):
    print(json.dumps(values, ensure_ascii=False, default=str), flush=True)


# ---------------------------------------------------------------- site ceiling
def site_ceiling(required):
    """Read the site file the planner actually uses and assert the demo's ceiling."""
    value = load(SITE_FILE, {})
    velocities = [float(v) for v in value.get('max_velocity_rad_s') or []]
    accelerations = [float(v) for v in value.get('max_acceleration_rad_s2') or []]
    lowest = min(velocities) if velocities else None
    record = dict(site_file=str(SITE_FILE), max_velocity_rad_s=velocities,
                  max_acceleration_rad_s2=accelerations, required_rad_s=float(required),
                  effective_ceiling_rad_s=lowest, ok=lowest is not None)
    if lowest is None:
        raise SystemExit('site limits unavailable: %s' % SITE_FILE)
    if lowest > required + 1e-12:
        record.update(ok=False, reason='SITE_CEILING_ABOVE_DEMO_BUDGET')
        raise SystemExit(json.dumps(record, ensure_ascii=False))
    if lowest < required - 1e-12:
        # A lower ceiling would silently run the demo slower than commissioned.
        record.update(ok=False, reason='SITE_CEILING_BELOW_DEMO_REQUIREMENT')
        raise SystemExit(json.dumps(record, ensure_ascii=False))
    return record


# ---------------------------------------------------------------------- state
def center_error(telemetry, goal):
    arm = telemetry['arms']['right']
    actual = np.asarray(arm['T_body_tcp'], dtype=float)
    position = float(np.linalg.norm(actual[:3, 3] - np.asarray(goal['position_m'])))
    angle = float(np.degrees(np.arccos(np.clip(
        (np.trace(actual[:3, :3].T @ np.asarray(goal['explicit_rotation'])) - 1) / 2, -1, 1))))
    return dict(position_m=position, orientation_deg=angle,
                position_mm=round(position * 1000.0, 3),
                tcp_body_m=[round(float(v), 6) for v in actual[:3, 3]])


def preflight(out):
    status = api('/api/operations/run-status', timeout=30) or {}
    save_json(out / 'run-status-before.json', status)
    if status.get('state') == 'RUNNING':
        raise SystemExit('another physical task is active: %s' % status)
    motion = api('/api/motion/status', timeout=30) or {}
    if str(motion.get('state')) == 'PLANNING':
        raise SystemExit('planner busy: %s' % motion.get('state'))
    telemetry = api('/api/operations/telemetry', {})
    save_json(out / 'telemetry-before.json', telemetry)
    if telemetry.get('errors'):
        raise SystemExit('telemetry errors, no trusted state: %r' % telemetry['errors'])
    arm = telemetry['arms']['right']
    controller = arm.get('controller_status') or {}
    bad = {k: controller.get(k) for k in ('errcode', 'emergency_stop', 'protective_stop',
                                          'drag_mode', 'on_soft_limit') if controller.get(k)}
    if bad:
        raise SystemExit('controller not clear on right arm: %s' % bad)
    if not controller.get('enabled'):
        raise SystemExit('right arm not enabled')
    if not isinstance(arm.get('tool_id'), int):
        raise SystemExit('right tool id unavailable: %r' % arm.get('tool_id'))
    return telemetry


def base_stationary():
    from ares_r.motion.live_state import base_stationarity
    value = base_stationarity(load(ROOT / 'config/system.json'))
    return value


# --------------------------------------------------------------------- plan
def payload(goal, mode, params, label, seeds=None):
    body = dict(arm=params['arm'],
                position_m=[float(v) for v in goal['position_m']],
                orientation='TERMINAL_EXPLICIT',
                explicit_rotation=goal['explicit_rotation'],
                speed_profile=params['speed_profile'],
                scene_policy=SCENE_CAPTURE,
                environment_avoidance=params['environment_avoidance'],
                planning_mode=mode,
                source=DEMO_ID.upper(),
                request_label='%s_%s' % (label, mode))
    rows = [[float(v) for v in row] for row in
            (params.get('ik_seeds_rad') or [] if seeds is None else seeds)]
    if rows:
        if len(rows) > 4 or any(len(row) != 6 for row in rows):
            raise SystemExit('ik_seeds_rad must hold at most four six-joint rows')
        body['ik_seed_joints_rad'] = rows
    return body


def worst_start_collisions(body_text, limit=6):
    """Extract the object-level signed clearances from INVALID_START_COLLISION."""
    try:
        parsed = json.loads(body_text)
        text = parsed.get('error', body_text) if isinstance(parsed, dict) else body_text
    except ValueError:
        text = body_text
    marker = 'INVALID_START_COLLISION: '
    if marker not in text:
        return None
    try:
        table = json.loads(text[text.index(marker) + len(marker):])
    except ValueError:
        return None
    offenders = sorted(((k, float(v)) for k, v in table.items() if float(v) <= 0.0),
                       key=lambda item: item[1])
    return dict(checked_objects=len(table), penetrating_count=len(offenders),
                worst=[dict(object=k, clearance_m=round(v, 6),
                            clearance_mm=round(v * 1000.0, 2)) for k, v in offenders[:limit]])


def residual_start_collision(report):
    """True when every start-collision offender is a sub-centimetre residual cluster.

    ``observed_remaining_observed_unknown_occupied_*`` boxes are raw unclassified
    points; they are re-derived (and renumbered) on every capture. On 2026-11-11
    11:34 an unchanged pose planned fine from the first scan (171 cuboids) and then
    was refused from the rescan (125 cuboids) because a 28x22x22 mm cluster at BODY
    [459,-188,1191] mm sat 2.06 mm inside the robot. Such a report is retried with
    the next FORCE_RESCAN attempt instead of aborting the run; a collision with any
    other object class - or one that survives the rescan - still refuses with no
    motion.
    """
    worst = (report or {}).get('worst') or []
    if not (report or {}).get('penetrating_count') or not worst:
        return False
    if int(report['penetrating_count']) != len(worst):
        return False
    return all(str(row.get('object', '')).startswith(RESIDUAL_START_OBJECT_PREFIXES) and
               abs(float(row.get('clearance_m', 0.0))) <= RESIDUAL_START_CLEARANCE_M
               for row in worst)


def seed_travel_deg(seed, start_rad):
    """Per-joint travel from the measured start, wrapped to the nearest equivalent."""
    rows = []
    for a, b in zip(seed, start_rad):
        delta = math.degrees(float(a)) - math.degrees(float(b))
        rows.append(delta - 360.0 * round(delta / 360.0))
    return rows


def feasible_center_seeds(params, start_rad, limit_deg=150.0):
    """Which configured center IK branches fit the 150 deg per-leg packaging envelope.

    Each branch is re-expressed in the representation nearest the current joints
    (``seed_near_start``): -270 deg -> +43 deg and -270 deg -> -316 deg are the same
    physical center, but only the second one is a 47 deg move instead of 313 deg, and
    the packaging excursion check compares raw joint values.
    """
    rows = []
    for seed in params.get('ik_seeds_rad') or []:
        if len(seed) != 6:
            continue
        travel = seed_travel_deg(seed, start_rad)
        worst = abs(max(travel, key=abs))
        near = [float(start_rad[i]) + math.radians(travel[i]) for i in range(6)]
        rows.append(dict(seed=[float(v) for v in seed], seed_near_start=near,
                         travel_deg=[round(v, 2) for v in travel],
                         worst_deg=round(worst, 2),
                         feasible=bool(worst <= float(limit_deg) + 1e-9)))
    return rows


def excursion_report(artifact, limit_deg=150.0):
    """Per-joint travel of a rejected plan, so the operator knows what to move."""
    try:
        planning = load(Path(artifact) / 'planning.json')
        points = planning['trajectory_points_rad']
        start = np.asarray(points[0], dtype=float)
        goal = np.asarray(points[-1], dtype=float)
    except (OSError, KeyError, TypeError, ValueError):
        return None
    travel = np.degrees(goal - start)
    rows = [dict(joint='joint%d' % (i + 1), travel_deg=round(float(v), 2),
                 over_limit=bool(abs(float(v)) > limit_deg))
            for i, v in enumerate(travel)]
    over = [row for row in rows if row['over_limit']]
    return dict(limit_deg=limit_deg, joints=rows,
                exceeding=over,
                start_joints_deg=[round(float(v), 3) for v in np.degrees(start)],
                goal_joints_deg=[round(float(v), 3) for v in np.degrees(goal)])


def verify_endpoint(artifact, goal, tolerance_m):
    """FK the last planned sample and confirm it really is the center TCP pose."""
    from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
    artifact = Path(artifact)
    request = load(artifact / 'planner_request.json')
    planning = load(artifact / 'planning.json')
    ik = RuntimeGoalIK(request['robot_yaml_urdf'], request['T_body_model'],
                       request['T_link6_tcp'])
    pose = ik.fk(np.asarray(planning['trajectory_points_rad'][-1], dtype=float))
    error = float(np.linalg.norm(pose[:3, 3] - np.asarray(goal['position_m'])))
    angle = float(np.degrees(np.arccos(np.clip(
        (np.trace(pose[:3, :3].T @ np.asarray(goal['explicit_rotation'])) - 1) / 2, -1, 1))))
    return dict(position_error_m=error, position_error_mm=round(error * 1000.0, 3),
                orientation_error_deg=angle, passed=bool(error <= tolerance_m))


def plan_center(goal, params, out, quality_fallback=True):
    modes = list(params['planning_modes'])
    if not quality_fallback:
        modes = modes[:1]
    sequence = modes * max(1, int(params['planning_rounds']))
    deadline = float(load(ROOT / 'config/system.json')['curobo']['timeout_s'])
    attempts = []
    seeds_override = None
    for index, mode in enumerate(sequence, start=1):
        body = payload(goal, mode, params, 'RETURN_CENTER', seeds=seeds_override)
        started = time.monotonic()
        try:
            handle = api('/api/motion/plan', body, timeout=deadline + 120)
        except ApiError as exc:
            entry = dict(attempt=index, mode=mode,
                         elapsed_s=round(time.monotonic() - started, 3),
                         error=str(exc)[-1200:],
                         start_collision=worst_start_collisions(exc.body))
            attempts.append(entry)
            save_json(out / ('attempt%d.json' % index), entry)
            if entry['start_collision']:
                if residual_start_collision(entry['start_collision']) and index < len(sequence):
                    save_json(out / ('start-collision-rescan%d.json' % index), dict(
                        attempt=index, mode=mode, rescan_next=True,
                        note='only sub-centimetre residual clusters offend; the next attempt re-scans',
                        **entry['start_collision']))
                    continue
                raise SystemExit(json.dumps(dict(
                    reason='INVALID_START_COLLISION',
                    advice='move the arm 30-50 mm away from the fixture (or lift it) and re-run; '
                           'no motion was dispatched',
                    **entry['start_collision']), ensure_ascii=False))
            if index == len(sequence):
                raise
            continue
        entry = dict(attempt=index, mode=mode,
                     elapsed_s=round(time.monotonic() - started, 3),
                     plan_id=handle.get('plan_id'),
                     execution_package_ready=handle.get('execution_package_ready'),
                     execution_package_error=handle.get('execution_package_error'))
        attempts.append(entry)
        save_json(out / ('attempt%d.json' % index), entry)
        if not handle.get('execution_package_ready'):
            error_text = str(handle.get('execution_package_error') or '')
            if 'excursion cap' in error_text:
                artifact = Path(handle.get('plan_artifact') or '')
                if not artifact.is_absolute():
                    artifact = ROOT / artifact
                report = excursion_report(artifact)
                if report is not None:
                    save_json(out / 'excursion-report.json', report)
                    branches = []
                    if seeds_override is None:
                        before = load(out / 'telemetry-before.json', {})
                        start_rad = ((before.get('arms') or {}).get('right') or {}).get('joints_rad')
                        if start_rad:
                            branches = feasible_center_seeds(params, start_rad, report['limit_deg'])
                            save_json(out / 'center-branches.json',
                                      dict(limit_deg=report['limit_deg'],
                                           chosen_goal_joints_deg=report['goal_joints_deg'],
                                           branches=branches))
                    feasible = [row['seed_near_start'] for row in branches if row['feasible']]
                    if feasible and index < len(sequence):
                        # The planner picked a center IK branch that needs more travel
                        # than one supervised leg allows; seed the remaining attempts
                        # with the branch(es) that do fit instead of giving up.
                        save_json(out / ('excursion-seed-retry%d.json' % index), dict(
                            attempt=index, mode=mode, next_seeds=feasible,
                            note='re-planning with the center branch(es) inside the per-leg envelope',
                            branches=branches))
                        seeds_override = feasible
                        continue
                    raise SystemExit(json.dumps(dict(
                        reason='NATIVE_EXCURSION_CAP',
                        detail='one joint must travel more than the 150 deg per-leg envelope '
                               'in a single free-space plan; the sender itself allows 220 deg',
                        advice='rotate the over-limit joint back by hand (or jog it) and re-run, '
                               'or split the move into two supervised legs',
                        **report), ensure_ascii=False))
            if index == len(sequence):
                raise SystemExit('native package unavailable: %r' % error_text)
            continue
        save_json(out / 'plan_handle.json', handle)
        record = dict(handle=handle, mode=mode, attempts=attempts)
        save_json(out / 'plans.json', record)
        return record
    raise SystemExit('no accepted plan after %d attempts' % len(attempts))


# ----------------------------------------------------------------- dispatch
def dispatch(record, params, out, goal, timeout_s=600.0):
    from ares_r.motion.arrival_contract import check_start
    handle = record['handle']
    artifact = Path(handle['plan_artifact'])
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    live = api('/api/operations/telemetry', {})
    save_json(out / 'telemetry-dispatch.json', live)
    if (live['arms']['right'].get('controller_status') or {}).get('errcode'):
        raise SystemExit('controller errorcode appeared before dispatch: %r'
                         % live['arms']['right']['controller_status'])
    planning = load(artifact / 'planning.json')
    check_start(live['arms']['right']['joints_rad'], planning['trajectory_points_rad'][0])
    motion = api('/api/motion/status', timeout=30) or {}
    if motion.get('plan_id') != handle['plan_id'] or motion.get('state') != 'READY':
        raise SystemExit('plan is not the ready current plan: %s' % motion)

    marker = out / 'dispatched-once.json'
    if marker.exists():
        raise SystemExit('this output directory already dispatched: %s' % marker)
    body = dict(plan_id=handle['plan_id'], trajectory_hash=handle['trajectory_hash'],
                authorization=MOTION_API_AUTHORIZATION,
                onsite_observer_confirmed=True,
                command_id='%s_%d' % (DEMO_ID.upper(), int(time.time() * 1000)))
    save_json(out / 'execute-request.json', body)
    # Marker lands BEFORE the dispatch: a crash here is UNCERTAIN, never a silent re-dispatch.
    save_json(marker, dict(state='UNCERTAIN', at_unix=time.time(), body=body))
    dispatched = api('/api/operations/execute', body, timeout=120)
    save_json(out / 'execute-response.json', dispatched)
    emit(dispatched=dispatched)

    deadline = time.monotonic() + float(timeout_s)
    last = None
    execution = None
    while time.monotonic() < deadline:
        state = api('/api/operations/run-status', timeout=30) or {}
        label = (state.get('state'), state.get('current_stage'))
        if label != last:
            emit(**{k: state.get(k) for k in ('state', 'mode', 'current_stage', 'failure_reason')})
            last = label
        if state.get('state') != 'RUNNING':
            execution = state
            save_json(out / 'run-status.json', state)
            break
        time.sleep(0.5)
    if execution is None:
        raise SystemExit('motion did not reach a terminal state in %.0f s; do NOT re-dispatch'
                         % timeout_s)
    from ares_r.motion.arrival_confirmation import confirm_arrival
    error = confirm_arrival(lambda: api('/api/operations/telemetry', {}, timeout=5),
                            goal, live, params['arrival_tolerance'], execution)
    save_json(out / 'arrival-confirmation.json', error)
    save_json(out / 'center-check.json', error)
    save_json(marker, dict(state='DISPATCHED', at_unix=time.time(), body=body))
    if execution.get('state') != 'SUCCEEDED':
        diagnostic = dict(demo_id=DEMO_ID, result='EXECUTION_FAILED', physical_motion=True,
                          arm='right', pose_id='right/center', arrival=error, evidence=str(out),
                          failure_reason=execution.get('failure_reason'))
        save_json(out / 'result.json', diagnostic)
        emit(**diagnostic)
        raise SystemExit('motion ended in %s: %s' %
                         (execution.get('state'), execution.get('failure_reason')))
    return error


def transient_zero_motion_failure(out):
    """True only for the known zero-motion controller gate transient.

    Requires all four: the run ended FAULT with the safety-gate errcode, the
    native log produced **zero** samples, the controller now reads clean, and
    the joints are exactly where the plan started.  Anything else propagates.
    """
    state = load(Path(out) / 'run-status.json', {}) or {}
    reason = str(state.get('failure_reason') or '')
    if state.get('state') != 'FAULT' or TRANSIENT_SAFETY_GATE not in reason:
        return False
    if int((state.get('execution_result') or {}).get('sample_count') or 0) != 0:
        return False
    live = api('/api/operations/telemetry', {})
    right = live['arms']['right']
    controller = right.get('controller_status') or {}
    if (controller.get('errcode') or controller.get('emergency_stop')
            or controller.get('protective_stop') or controller.get('drag_mode')
            or controller.get('on_soft_limit')):
        return False
    before = (load(Path(out) / 'telemetry-dispatch.json', {}) or {}).get('arms', {})
    start = (before.get('right') or {}).get('joints_rad')
    now = right.get('joints_rad')
    if not start or not now:
        return False
    return max(abs(a - b) for a, b in zip(start, now)) * 180.0 / math.pi <= UNMOVED_TOLERANCE_DEG


def plan_and_verify(out, goal, params, required, quality_fallback):
    """Plan into `out` and refuse unless the package really is a 0.2-cap center plan."""
    record = plan_center(goal, params, out, quality_fallback=quality_fallback)
    handle = record['handle']
    artifact = Path(handle['plan_artifact'])
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    audit = load(artifact / 'native_package' / 'native_audit.json', {}) or {}
    save_json(out / 'native-audit.json', audit)
    cap = audit.get('speed_cap_rad_s')
    if cap is None or abs(float(cap) - required) > 1e-9:
        raise SystemExit('native package speed cap %r != required %.3f' % (cap, required))
    endpoint = verify_endpoint(artifact, goal,
                               float(params['arrival_tolerance']['position_m']))
    save_json(out / 'planned-endpoint.json', endpoint)
    if not endpoint['passed']:
        raise SystemExit('planned endpoint is not the center pose: %s' % endpoint)
    return record, audit, cap, endpoint


# --------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(
        description='demo-0 右臂任意位姿 → center（cuRobo，站点上限 0.2）',
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--prepare', action='store_true', help='只规划（默认）')
    group.add_argument('--execute', action='store_true', help='规划后当次派发并复核到位')
    group.add_argument('--stop', action='store_true')
    parser.add_argument('--authorization', default=None)
    parser.add_argument('--onsite-observer-confirmed', action='store_true')
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--required-site-velocity', type=float, default=None)
    parser.add_argument('--no-quality-fallback', action='store_true')
    parser.add_argument('--timeout-s', type=float, default=600.0)
    args = parser.parse_args()

    if args.stop:
        emit(stop=api('/api/operations/stop', {}, timeout=30))
        return 0

    params = load(PARAMETERS)
    if params.get('demo_id') != DEMO_ID:
        raise SystemExit('parameters demo_id mismatch: %r' % params.get('demo_id'))
    required = float(args.required_site_velocity
                     if args.required_site_velocity is not None
                     else params['required_site_max_velocity_rad_s'])
    execute = bool(args.execute)
    if execute:
        if args.authorization != params['authorization_phrase']:
            raise SystemExit('授权短语必须是 %r' % params['authorization_phrase'])
        if not args.onsite_observer_confirmed:
            raise SystemExit('实机派发需要 --onsite-observer-confirmed（现场确认）')

    out = Path(args.output) if args.output else (
        EVIDENCE_ROOT / ('run_%d' % time.time_ns()))
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    save_json(out / 'script.json', dict(
        demo_id=DEMO_ID, script=str(Path(__file__)), execute=execute,
        parameters=str(PARAMETERS), physical_motion=execute,
        started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), started_at_unix=time.time()))

    from ares_r.manipulation.task_contract import center_goal
    goal = center_goal(ROOT)
    save_json(out / 'center-goal.json', goal)
    ceiling = site_ceiling(required)
    save_json(out / 'site-ceiling.json', ceiling)
    emit(site_ceiling=ceiling, evidence=str(out), goal_position_m=goal['position_m'])

    telemetry = preflight(out)
    base = base_stationary()
    save_json(out / 'base-stationarity.json', base)
    if not base.get('stationary'):
        raise SystemExit('base is not stationary: %s' % base)

    error = center_error(telemetry, goal)
    save_json(out / 'start-error.json', error)
    tolerance = params['already_at_center_tolerance']
    if (error['position_m'] <= float(tolerance['position_m'])
            and error['orientation_deg'] <= float(tolerance['orientation_deg'])):
        result = dict(demo_id=DEMO_ID, result='ALREADY_AT_CENTER', physical_motion=False,
                      evidence=str(out), start_error=error, tool_id=telemetry['arms']['right'].get('tool_id'))
        save_json(out / 'result.json', result)
        save_json(LAST_RUN, dict(result, run_dir=str(out), at_unix=time.time()))
        emit(**result)
        return 0

    record, audit, cap, endpoint = plan_and_verify(out, goal, params, required,
                                                  not args.no_quality_fallback)
    handle = record['handle']

    prepared = dict(demo_id=DEMO_ID, result='PREPARED', physical_motion=False,
                    evidence=str(out), plan_id=handle['plan_id'],
                    trajectory_hash=handle['trajectory_hash'],
                    planning_mode=record['mode'], attempts=record['attempts'],
                    tool_id=telemetry['arms']['right'].get('tool_id'),
                    effective_speed_cap_rad_s=cap,
                    native_duration_s=audit.get('duration_s'),
                    native_samples=audit.get('sample_count'),
                    peak_joint_speed_rad_s=audit.get('max_joint_speed_rad_s'),
                    predicted_tracking_deg=audit.get('predicted_tracking_gate_deg'),
                    planned_endpoint=endpoint, start_error=error,
                    site_ceiling=ceiling)
    if not execute:
        save_json(out / 'result.json', prepared)
        save_json(LAST_RUN, dict(prepared, run_dir=str(out), at_unix=time.time()))
        emit(**prepared)
        return 0

    try:
        arrival = dispatch(record, params, out, goal, timeout_s=args.timeout_s)
    except SystemExit:
        if not transient_zero_motion_failure(out):
            raise
        retry = out / 'retry-1'
        retry.mkdir(parents=True, exist_ok=False)
        save_json(retry / 'retry-reason.json', dict(
            first_attempt=str(out),
            failure=load(out / 'run-status.json', {}).get('failure_reason'),
            policy='KNOWN_ZERO_MOTION_CONTROLLER_GATE; one fresh plan and one dispatch',
            at_unix=time.time()))
        emit(retry='known zero-motion controller gate; re-planning once')
        record, audit, cap, endpoint = plan_and_verify(retry, goal, params, required,
                                                      not args.no_quality_fallback)
        handle = record['handle']
        arrival = dispatch(record, params, retry, goal, timeout_s=args.timeout_s)
        out = retry
        prepared.update(evidence=str(out), plan_id=handle['plan_id'],
                        trajectory_hash=handle['trajectory_hash'],
                        planning_mode=record['mode'], attempts=record['attempts'],
                        effective_speed_cap_rad_s=cap,
                        native_duration_s=audit.get('duration_s'),
                        native_samples=audit.get('sample_count'),
                        peak_joint_speed_rad_s=audit.get('max_joint_speed_rad_s'),
                        predicted_tracking_deg=audit.get('predicted_tracking_gate_deg'),
                        planned_endpoint=endpoint)
    result = dict(prepared, result='AT_CENTER' if arrival['passed'] else 'CENTER_NOT_CONFIRMED',
                  physical_motion=True, arm='right', pose_id='right/center', arrival=arrival,
                  completed_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
    save_json(out / 'result.json', result)
    save_json(LAST_RUN, dict(result, run_dir=str(out), at_unix=time.time()))
    emit(**result)
    if not arrival['passed']:
        raise SystemExit('center not confirmed: %.3f mm / %.4f deg'
                         % (arrival['position_mm'], arrival['orientation_deg']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
