#!/usr/bin/env python3
"""demo-5 · DMP 抓取站：专机放置（下降 60 mm → 松爪）→ 回全局 center。

同一脚本也承载 demo-6 `right_arm_liaopan_dmp_place_v1`（料盘放置除尘收料专机）：
两者代码路径完全相同，差异只在 `demos/<demo_id>/parameters.json`；用
`--demo-id right_arm_liaopan_dmp_place_v1` 切换（参数默认路径与证据目录都跟着切）。
demo-6：夹持物为料盘；**直放模式** `plan_direct_to_place: true`——取消预放置点，
`preplace_offset_body_m=[0,0,0]` 且 `descent_m=0`，只有一条 cuRobo 腿，目标就是
放置点 = 5700 检测返回点，到位即松爪（不再有预放置抬高，也没有控制器 ModeL 下降段）。

来源
----
本脚本是 demo-4 `right_arm_sift_dmp_roundtrip_v1` 中
`stages.dmp_place`（5700 抓取配置 ID2 检测 → 预放置点 → cuRobo 规划 →
下降 60 mm → 松爪）与 `stages.return_center`（回全局 center + `check_center`）
两段的独立拷贝，行为与 demo-4 保持一致；**不含抓取段（pick）与底盘转场**：
起点就是 DMP 抓取站，底盘全程不动。

开工前自检（每次运行都做，不满足即拒绝，不运动）
----------------------------------------------
- 站点速度上限：`config/jaka_mini2_motion.site.json` 的 `max_velocity_rad_s` 必须
  等于 `parameters.json:required_site_max_velocity_rad_s`（0.2 rad/s）；
- 控制器 TCP：`/api/operations/telemetry` 右臂 `tool_id` 必须等于
  `parameters.json:required_tool_id`（3 = tcp3）；
- 控制器 `errcode` / `emergency_stop` / `protective_stop` / `drag_mode` /
  `on_soft_limit` 必须全清。

前提（操作员保证，代码只记录不替代）
------------------------------------
- 右臂已持住待放置的物件（demo-5：筛网；demo-6：料盘；由其它链路完成抓取）；
- 左臂保持当前姿态不动；现场监督与急停可用；
- **底盘已停在 DMP 抓取站并静止**（本 Demo 不发任何底盘指令）。

放置段
------
5700 抓取配置 ID2 检测 → 预放置点（检测点 + `preplace_offset_body_m`）→
cuRobo 规划（硬水平门限 + FAST→QUALITY→QUALITY 多轮重试）→ 下降
（默认 60 mm，BODY −Z，控制器原生 MoveL）→ 松爪并回读确认
（±`release_readback_tolerance_raw`）→ 沿 BODY x− 后退（`post_release_retreat`）。

直放模式（`stages.dmp_place.plan_direct_to_place=true`，demo-6 2026-11-09 现场要求）：
取消预放置点——`place = detection + offset`（demo-6 的 offset 为 0，即检测点），
只规划一条腿，`descent` 强制为 0，**没有下降段**；到位后直接松爪 → 后退 → 回 center。
下发到 `/api/motion/plan` 的腿标签变为 `place`（证据 `place_r*/place-arrival.json`、
`descent-skipped.json`）。

回 center 段
------------
`ares_r.manipulation.task_contract.center_goal` 是唯一目标；`FORCE_RESCAN`
每轮新扫描 + 新规划并于当次派发，到位后按 center 合同（3 mm / 3°）复核。

安全
----
实机必须 `--execute` + `--authorization '<authorization_phrase>'` +
`--onsite-observer-confirmed`；每个输出目录只允许派发一次；控制器未清零时
拒绝任何运动；规划阶段用当次最新扫描判定目标碰撞，失败即中止不绕过。

用法
----
  干跑（只检测 + 规划，不动）：PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stage all
  实机：加 --execute --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
  单段：--stage place   /   --stage center   /   --stage place_center
  停止：PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stop
"""
import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

#: 默认 demo（demo-5）。demo-6 `right_arm_liaopan_dmp_place_v1` 是本脚本的参数级拷贝，
#: 通过 `--demo-id` 选择自己的 `parameters.json` 与证据目录；代码路径完全共用。
DEMO_ID = 'right_arm_dmp_place_v1'
PARAMETERS = ROOT / 'demos' / DEMO_ID / 'parameters.json'
EVIDENCE_ROOT = ROOT / 'worklog/evidence/demo-runs' / DEMO_ID
LAST_RUN = EVIDENCE_ROOT / 'last-run.json'
BASE_URL = os.environ.get('ARES_R_ROUNDTRIP_API_URL', 'http://127.0.0.1:8775').rstrip('/')
SITE_FILE = ROOT / 'config/jaka_mini2_motion.site.json'
GRIPPER = ROOT / 'scripts/gripper_direct_once.py'
#: canonical_backend validates `/api/operations/execute` against exactly this
#: phrase (canonical_backend.py:_motion_execute_once). The operator-facing phrase
#: (`parameters.json:authorization_phrase`) only guards this CLI and must never
#: be sent on the wire.
MOTION_API_AUTHORIZATION = 'RIGHT SCENE_AWARE SUPERVISED'
#: 规划器同一时刻只能处理一个请求；命中 `PLANNER_BUSY: no queue` 时等一会儿重试，
#: 不把它当作「该模式失败」（否则 9 次尝试会在 1 秒内全部烧完）。
PLANNER_BUSY_WAIT_S = 3.0
PLANNER_BUSY_MAX_WAITS = 100
#: 阻塞式等待（规划 / 原生执行）期间的心跳间隔，便于现场看到「现在在做什么、花了多久」。
PROGRESS_HEARTBEAT_S = 5.0
#: 已知控制器瞬态：派发瞬间在 servo 激活前被拒，`errcode=4128769`，0 采样、无运动。
#: 只在这种情况 **且** 关节确实未动时，重新规划 + 重新派发一次（同 demo-0）。
TRANSIENT_SAFETY_GATE = 'controller safety gate errcode=4128769'
UNMOVED_TOLERANCE_DEG = 0.2
#: `DemoConsole.permits()` only lets the owning job call these endpoints while the
#: console holds the execution resources; `console.command()` exports the token.
CONSOLE_TOKEN = os.environ.get('ARES_R_DEMO_CONSOLE_TOKEN')
TOKEN_ENDPOINTS = ('/api/operations/execute', '/api/operations/base-move')


class ApiError(RuntimeError):
    def __init__(self, path, code, body):
        self.path, self.code, self.body = path, code, body
        super().__init__('%s -> %s: %s' % (path, code, body[-1200:]))


def error_digest(exc, limit=400000):
    """保留完整错误体：干涉表很长，截断会把中间的负间隙和错误类型一起吃掉。"""
    text = str(getattr(exc, 'body', '') or exc)
    if len(text) <= limit:
        return text
    return text[:limit // 2] + ' ... [truncated] ... ' + text[-limit // 2:]


# --------------------------------------------------------------------------- io
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


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')
    temporary.replace(path)


def load(path, default=None):
    path = Path(path)
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def emit(**values):
    print(json.dumps(values, ensure_ascii=False, default=str), flush=True)


class Progress:
    """阶段耗时与累计计时：每段都打印一行 JSON，阻塞时定期心跳。

    输出行统一带 `stage` / `phase` / `kind` / `prepare_elapsed_s` /
    `planning_elapsed_s` / `total_elapsed_s`，控制台按这些字段显示
    「当前阶段」与「准备/规划累计」。
    """

    def __init__(self):
        self.t0 = time.monotonic()
        self.stage = None
        self.phase = None
        self.kind = None
        self.phase_t0 = self.t0
        self.prepare_s = 0.0
        self.planning_s = 0.0
        self.execute_s = 0.0

    def _accumulate(self):
        if self.stage is None:
            return
        elapsed = time.monotonic() - self.phase_t0
        if self.kind == 'plan':
            self.planning_s += elapsed
        elif self.kind == 'execute':
            self.execute_s += elapsed
        else:
            self.prepare_s += elapsed

    def _payload(self, event, phase_elapsed_s):
        return dict(progress=event, stage=self.stage, phase=self.phase, kind=self.kind,
                    phase_elapsed_s=round(phase_elapsed_s, 2),
                    prepare_elapsed_s=round(self.prepare_s, 2),
                    planning_elapsed_s=round(self.planning_s, 2),
                    execute_elapsed_s=round(self.execute_s, 2),
                    total_elapsed_s=round(time.monotonic() - self.t0, 2))

    def begin(self, stage, phase=None, kind='prep'):
        self._accumulate()
        if self.stage is not None:
            emit(**self._payload('END', time.monotonic() - self.phase_t0))
        self.stage, self.phase, self.kind = stage, phase or stage, kind
        self.phase_t0 = time.monotonic()
        emit(**self._payload('BEGIN', 0.0))

    def heartbeat(self, **extra):
        payload = self._payload('HEARTBEAT', time.monotonic() - self.phase_t0)
        payload.update(extra)
        emit(**payload)

    def finish(self):
        self._accumulate()
        payload = self._payload('END', time.monotonic() - self.phase_t0)
        self.stage = None
        emit(**payload)

    def timings(self):
        return dict(prepare_s=round(self.prepare_s, 2),
                    planning_s=round(self.planning_s, 2),
                    execute_s=round(self.execute_s, 2),
                    total_s=round(time.monotonic() - self.t0, 2))


def run_with_heartbeat(progress, call, interval=PROGRESS_HEARTBEAT_S, **extra):
    """跑一个阻塞调用，期间每 `interval` 秒打印一行心跳。"""
    box = {}

    def worker():
        try:
            box['value'] = call()
        except BaseException as exc:                             # noqa: BLE001
            box['error'] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(interval)
        if thread.is_alive():
            progress.heartbeat(**extra)
    if 'error' in box:
        raise box['error']
    return box['value']


def telemetry():
    return api('/api/operations/telemetry', {}, timeout=40)


def tcp_of(state, arm='right'):
    return np.asarray(state['arms'][arm]['T_body_tcp'], dtype=float)


def controller_guard(state, arm='right'):
    status = state['arms'][arm]['controller_status']
    bad = {k: status.get(k) for k in ('errcode', 'emergency_stop', 'protective_stop',
                                      'drag_mode', 'on_soft_limit') if status.get(k)}
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


# ------------------------------------------------- 开工自检（站点速度 / 控制器 TCP）
def tilt_of(rotation):
    """与 `validate_level_path` 同口径：approach(+Z) 与 finger(X) 轴相对水平面的倾斜。"""
    rotation = np.asarray(rotation, dtype=float)
    return dict(forward_tilt_deg=round(math.degrees(math.asin(
                    min(1.0, abs(float(rotation[2, 2]))))), 3),
                finger_axis_tilt_deg=round(math.degrees(math.asin(
                    min(1.0, abs(float(rotation[2, 0]))))), 3),
                yaw_deg=round(math.degrees(math.atan2(float(rotation[1, 2]),
                                                      float(rotation[0, 2]))), 3))


def start_tilt_guard(state, tolerance_deg, out=None):
    """起点姿态已经超过水平门限时，直接拒绝（否则每一轮规划都必然被同一原因拒掉）。"""
    tilt = tilt_of(tcp_of(state)[:3, :3])
    tilt['max_tilt_deg'] = max(tilt['forward_tilt_deg'], tilt['finger_axis_tilt_deg'])
    tilt['tolerance_deg'] = float(tolerance_deg)
    tilt['passed'] = bool(tilt['max_tilt_deg'] <= float(tolerance_deg))
    if out is not None:
        save(Path(out) / 'start-tilt.json', tilt)
    if not tilt['passed']:
        raise SystemExit(json.dumps(dict(
            tilt, reason='START_POSE_NOT_LEVEL',
            detail='起点 TCP 已倾斜 %.3f°，超过水平门限 %.2f°。水平门限量的是整条路径（含起点），'
                   '所以任何规划都会被拒——先把手臂调平再跑（例如先跑 demo-0 回 center，'
                   '或示教器手动调平），确需带倾斜起步时用 --level-tolerance 显式放宽。'
                   % (tilt['max_tilt_deg'], float(tolerance_deg))),
            ensure_ascii=False))
    return tilt


def site_ceiling(required):
    """Read the site file the planner actually uses and assert the demo ceiling."""
    required = float(required)
    value = load(SITE_FILE, {}) or {}
    velocities = [float(v) for v in value.get('max_velocity_rad_s') or []]
    accelerations = [float(v) for v in value.get('max_acceleration_rad_s2') or []]
    lowest = min(velocities) if velocities else None
    record = dict(site_file=str(SITE_FILE), max_velocity_rad_s=velocities,
                  max_acceleration_rad_s2=accelerations, required_rad_s=required,
                  effective_ceiling_rad_s=lowest, ok=False)
    if lowest is None:
        raise SystemExit(json.dumps(dict(record, reason='SITE_LIMITS_UNAVAILABLE'),
                                    ensure_ascii=False))
    if lowest > required + 1e-12:
        raise SystemExit(json.dumps(dict(
            record, reason='SITE_CEILING_ABOVE_DEMO_BUDGET',
            detail='站点允许比本 Demo 验收值 %.2f rad/s 更快；先确认/调整站点文件再跑'
                   % required), ensure_ascii=False))
    if lowest < required - 1e-12:
        raise SystemExit(json.dumps(dict(
            record, reason='SITE_CEILING_BELOW_DEMO_REQUIREMENT',
            detail='站点上限低于本 Demo 验收值 %.2f rad/s，会静默降速；先确认站点文件'
                   % required), ensure_ascii=False))
    record['ok'] = True
    return record


def tool_guard(state, required, arm='right'):
    """Assert the controller TCP (tool id) is the one this demo was commissioned on."""
    required = int(required)
    arm_state = state['arms'].get(arm) or {}
    tool_id = arm_state.get('tool_id')
    record = dict(arm=arm, required_tool_id=required, tool_id=tool_id,
                  controller_status=arm_state.get('controller_status'))
    if tool_id is None:
        raise SystemExit(json.dumps(dict(record, reason='CONTROLLER_TOOL_ID_UNAVAILABLE'),
                                    ensure_ascii=False))
    if int(tool_id) != required:
        raise SystemExit(json.dumps(dict(
            record, reason='CONTROLLER_TOOL_NOT_COMMISSIONED',
            detail='控制器 %s 臂 TCP 现在是 tool_id=%s，本 Demo 验收用 tool_id=%d；'
                   '请先在示教器切回该工具再跑（本次未做任何运动）'
                   % (arm, tool_id, required)), ensure_ascii=False))
    return record


# --------------------------------------------------------------- 夹爪（只读记录）
def grip_snapshot(out, label):
    """Record the gripper readback so the run shows whether the payload was held.

    Informational only: a raw above the open threshold prints a warning, it never
    blocks, because an empty-close and a light hold read similarly.
    """
    record = dict(label=label, captured_at_unix=time.time(), demo_id=DEMO_ID)
    try:
        status = subprocess.run([sys.executable, str(GRIPPER), 'status'], cwd=ROOT,
                                capture_output=True, text=True, timeout=40)
        parsed = json.loads(status.stdout.strip().splitlines()[-1])
        record.update(position_raw=parsed.get('position_raw'), forced=parsed.get('forced'),
                      temperature_c=parsed.get('temperature_c'))
    except Exception as exc:                                     # noqa: BLE001
        record.update(error=str(exc)[-300:])
    raw = record.get('position_raw')
    record['looks_open'] = bool(raw is not None and float(raw) > 600)
    save(Path(out) / ('gripper-%s.json' % label), record)
    if record['looks_open']:
        print('WARNING gripper reads raw %s (>600): payload may not be held' % raw, flush=True)
    return record


# ------------------------------------------------------------------- planning
def level_orientation(state, yaw_rad=None):
    from ares_r.motion.tcp_orientation import (level_rotation, nearest_level_roll_branch,
                                               tcp_yaw_rad)
    rotation = tcp_of(state)[:3, :3]
    yaw = tcp_yaw_rad(rotation) if yaw_rad is None else float(yaw_rad)
    branch = nearest_level_roll_branch(rotation)
    return np.asarray(level_rotation(yaw, branch), dtype=float), yaw, branch


def descent_axis_metrics(ik, points, descent_m):
    """下降段的 TCP 形状：横向偏移、中途最低 z、净位移。

    2026-11-09 实机教训：一条横向偏移 263 mm、中途比目标 z 还低 8 mm 的绕行路径
    通过了只告警的旧校验，执行时撞到结构。现在把这两个量做成硬门限。
    """
    xyz = np.array([np.asarray(ik.fk(np.asarray(q, dtype=float)), dtype=float)[:3, 3]
                    for q in points], dtype=float) * 1000.0
    start, end = xyz[0], xyz[-1]
    lateral = np.hypot(xyz[:, 0] - start[0], xyz[:, 1] - start[1])
    return dict(descent_mm=round(float(descent_m) * 1000.0, 1),
                start_mm=[round(float(v), 1) for v in start],
                end_mm=[round(float(v), 1) for v in end],
                lateral_max_mm=round(float(lateral.max()), 1),
                z_min_mm=round(float(xyz[:, 2].min()), 1),
                z_min_below_goal_mm=round(float(xyz[:, 2].min() - end[2]), 1),
                net_descent_mm=round(float(start[2] - end[2]), 1),
                net_lateral_mm=round(float(np.hypot(end[0] - start[0],
                                                    end[1] - start[1])), 1))


def prove_plan(record, label, out, *, tolerance_deg, final_yaw_rad=None,
               descent_m=None, strict_descent=False, descent_limits=None):
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
    limits = dict(descent_limits or {})
    gate_enabled = bool(limits.pop('enabled', True))
    metrics = descent_axis_metrics(ik, points, descent_m)
    lateral_limit = float(limits.get('lateral_mm', 20.0))
    dip_limit = float(limits.get('min_below_goal_mm', -2.0))
    metrics.update(lateral_limit_mm=lateral_limit, min_below_goal_limit_mm=dip_limit,
                   gate_enabled=gate_enabled)
    metrics['passed'] = bool(metrics['lateral_max_mm'] <= lateral_limit
                             and metrics['z_min_below_goal_mm'] >= dip_limit)
    save(out / ('%s.descent-axis.json' % label), metrics)
    if not metrics['passed']:
        message = ('%s: descent is not a usable vertical line: lateral_max=%.1f mm '
                   '(limit %.1f), z_min_below_goal=%.1f mm (limit %.1f)'
                   % (label, metrics['lateral_max_mm'], lateral_limit,
                      metrics['z_min_below_goal_mm'], dip_limit))
        # platform.descent_axis_gate_enabled=false（2026-11-09 现场关）时只告警：
        # 指标仍逐次写入 <label>.descent-axis.json，便于事后复核。
        if gate_enabled:
            raise SystemExit(message + ' — 这种绕行路径不派发')
        print(message + ' — WARNING 垂直门限已关闭，不阻断派发', flush=True)
    from ares_r.manipulation.task_tcp_offset import validate_body_descent
    try:
        proof = validate_body_descent(points, ik.fk, float(descent_m), tolerance_m=0.003)
    except Exception as exc:                                     # noqa: BLE001
        save(out / ('%s.axis-proof.json' % label), dict(passed=False, error=str(exc)))
        if strict_descent:
            raise SystemExit('%s: descent axis proof failed: %s' % (label, exc)) from exc
        print('%s: WARNING not a straight BODY -Z line (%s); lateral %.1f mm / dip %.1f mm '
              'within limits, net displacement verified after execution'
              % (label, exc, metrics['lateral_max_mm'], metrics['z_min_below_goal_mm']),
              flush=True)
        return dict(proof=dict(passed=False), metrics=metrics)
    save(out / ('%s.axis-proof.json' % label), proof)
    return dict(proof=proof, metrics=metrics)


def plan_request(trial, deadline_s, tag, mode, progress=None):
    """POST /api/motion/plan，遇到 PLANNER_BUSY 就等一会儿再试同一模式。

    规划器同一时刻只能跑一个请求（`PLANNER_BUSY: no queue`）。旧写法把 busy 当成
    「该模式失败」→ 9 次尝试 1 秒内全部烧完（2026-11-06 实测），所以这里改成等待。
    """
    started = time.monotonic()
    waits = 0
    while True:
        try:
            call = lambda: api('/api/motion/plan', trial, timeout=deadline_s + 120)  # noqa: E731
            if progress is None:
                return call(), None, waits
            return run_with_heartbeat(progress, call, mode=mode, label=tag), None, waits
        except (ApiError, SystemExit) as exc:
            if 'PLANNER_BUSY' in str(exc) and waits < PLANNER_BUSY_MAX_WAITS:
                waits += 1
                print(json.dumps(dict(label=tag, mode=mode, state='PLANNER_BUSY_WAIT',
                                      waited_s=round(time.monotonic() - started, 1),
                                      retry='%d/%d' % (waits, PLANNER_BUSY_MAX_WAITS)),
                                 ensure_ascii=False), flush=True)
                time.sleep(PLANNER_BUSY_WAIT_S)
                continue
            return None, error_digest(exc), waits


def goal_collision_report(error_text, label, descent_m, out):
    """把 `INVALID_GOAL_COLLISION` 的干涉表解析成可操作结论。

    返回穿透深度、以及两个可选修法：最大可行下降深度 / 预放置点最少抬高量。
    不是这种错误就返回 None。
    """
    import re
    marker = 'INVALID_GOAL_COLLISION: '
    text = str(error_text)
    if marker not in text:
        return None
    raw = text[text.index(marker) + len(marker):]
    # 错误体是逐层 JSON 序列化的，里面的引号带反斜杠转义；先还原再解析。
    raw = raw.replace('\\\\"', '"').replace('\\"', '"')
    table = None
    try:
        table = json.loads(raw[:raw.rindex('}]') + 2])
    except (ValueError, IndexError):
        table = None
    if not isinstance(table, dict):
        table = {name: float(value) for name, value in
                 re.findall(r'"([A-Za-z0-9_.]+)"\s*:\s*(-?\d+\.?\d*)', raw)}
    offenders = sorted(((k, float(v)) for k, v in table.items() if float(v) <= 0.0),
                       key=lambda item: item[1])
    if not offenders:
        return None
    penetration_mm = round(-offenders[0][1] * 1000.0, 2)
    descent_mm = round(float(descent_m) * 1000.0, 1)
    record = dict(
        label=label, reason='INVALID_GOAL_COLLISION',
        descent_mm=descent_mm, penetration_mm=penetration_mm,
        offenders=[dict(object=name, clearance_mm=round(value * 1000.0, 2))
                   for name, value in offenders[:50]],
        suggested_max_descent_mm=round(descent_mm - penetration_mm - 1.0, 1),
        suggested_preplace_lift_mm=round(penetration_mm + 1.0, 1),
        advice='下降落点比观测到的支撑面深 %.2f mm。二选一：把下降量降到 ≤%.1f mm，'
               '或把预放置点抬高 ≥%.1f mm（stages.dmp_place.preplace_offset_body_m 的 z '
               '或 --preplace-offset），不要让工具压进台面。'
               % (penetration_mm, descent_mm - penetration_mm - 1.0, penetration_mm + 1.0))
    save(Path(out) / ('%s-goal-collision.json' % label), record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def _balanced_object(text, start):
    """Return the first complete JSON object starting at ``start`` (string aware)."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def start_collision_report(error_text, label, out):
    """提取 INVALID_START_COLLISION 的穿透对象（起点自检，逐对象签名净空）。

    与 INVALID_GOAL_COLLISION 不同，这里的表是「对象名 → 签名净空」的**平表**，
    并非逐候选的列表。负值 = 穿透，单位米。
    """
    import re
    marker = 'INVALID_START_COLLISION: '
    text = str(error_text)
    if marker not in text:
        return None
    raw = text[text.index(marker) + len(marker):]
    raw = raw.replace('\\\\"', '"').replace('\\"', '"')
    table = None
    if '{' in raw:
        body = _balanced_object(raw, raw.index('{'))
        if body:
            try:
                table = json.loads(body)
            except ValueError:
                table = None
    if not isinstance(table, dict):
        table = {name: float(value) for name, value in
                 re.findall(r'"([A-Za-z0-9_.]+)"\s*:\s*(-?\d+\.?\d*)', raw)}
    offenders = sorted(((k, float(v)) for k, v in table.items() if float(v) <= 0.0),
                       key=lambda item: item[1])
    if not offenders:
        return None
    record = dict(
        label=label, reason='INVALID_START_COLLISION',
        checked_objects=len(table),
        penetration_mm=round(-offenders[0][1] * 1000.0, 2),
        offenders=[dict(object=name, clearance_mm=round(value * 1000.0, 2))
                   for name, value in offenders[:50]],
        nearest=[dict(object=name, clearance_mm=round(value * 1000.0, 2))
                 for name, value in sorted(table.items(), key=lambda kv: float(kv[1]))[:6]],
        advice='当前起点位姿与观测体素重叠 %.2f mm。优先手动把手臂挪开 30~50 mm 重跑；'
               '仅当现场确认该体素为误检时，才允许把这个对象从碰撞世界排除后重规划。'
               % (-offenders[0][1] * 1000.0))
    save(Path(out) / ('start-collision-%s.json' % label), record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def waiver_admit(waiver, report):
    """判断本次落点穿透是否可豁免：只豁免前缀白名单内、深度 ≤ 上限的对象。

    返回要加入 `ignore_cuboid_ids` 的对象名列表；任一对象超出策略范围则返回 []，
    即整次「不豁免」（fail-closed，不会部分豁免）。
    """
    if not waiver or not waiver.get('enabled') or not report:
        return []
    limit = float(waiver.get('max_penetration_mm', 10.0))
    prefixes = tuple(waiver.get('allowed_prefixes') or ())
    names = []
    for row in report.get('offenders') or []:
        name = str(row['object'])
        depth = -float(row['clearance_mm'])
        if depth > limit or (prefixes and not name.startswith(prefixes)):
            return []
        names.append(name)
    return names


def waiver_rejection(waiver, report):
    """豁免被拒时的具体原因（空字符串 = 可以豁免）。

    观测体素的名字会随每次扫描重新编号（`component_00` / `component_01`、
    `..._occupied_101` / `_104`），所以“前缀不匹配”是现场最常见的一条；
    把它直接打印出来，避免只能从一长串干涉表里翻。
    """
    limit = float((waiver or {}).get('max_penetration_mm') or 0.0)
    prefixes = tuple((waiver or {}).get('allowed_prefixes') or ())
    for row in (report or {}).get('offenders') or []:
        name = str(row['object'])
        depth = -float(row['clearance_mm'])
        if depth > limit:
            return ('%s penetrates %.2f mm > max_penetration_mm %.2f'
                    % (name, depth, limit))
        if prefixes and not name.startswith(prefixes):
            return ('%s does not match allowed_prefixes %s'
                    % (name, [p for p in prefixes]))
    return ''


def false_positive_voxel_ids(error_text, prefixes):
    """从规划错误的净空表里取出「白名单前缀」命名的全部对象。

    现场确认某个家族体素是误检时，仅豁免“落点穿透的那几个”是不够的：
    同一个鬼影簇会在下一次扫描里重新编号，变成**路径上的限隙对象**
    （2026-11-09 实测：落点穿透的是 `..._component_01_`，而限制路径的是同族的
    `..._component_02_`，净空 1.3 mm → cuRobo 绕 244 mm → 末端倾倒 17°）。
    这里按前缀把整族一次性排除，名称仍然取自**当次真实场景**（worker 对未知名字 fail-closed）。
    """
    prefixes = tuple(prefixes or ())
    if not prefixes:
        return []
    marker = 'INVALID_GOAL_COLLISION: '
    text = str(error_text)
    if marker not in text:
        return []
    raw = text[text.index(marker) + len(marker):].replace('\\\\"', '"').replace('\\"', '"')
    if '{' not in raw:
        return []
    body = _balanced_object(raw, raw.index('{'))
    if not body:
        return []
    try:
        table = json.loads(body)
    except ValueError:
        return []
    if not isinstance(table, dict):
        return []
    return sorted(name for name in table if str(name).startswith(prefixes))


def plan_leg(payload, label, out, deadline_s, *, tolerance_deg, final_yaw_rad=None,
             descent_m=None, rounds=3, strict_descent=False, progress=None, waiver=None,
             start_waiver=None, descent_limits=None, ignore_ids=(), fp_prefixes=()):
    scene_before = api('/api/scene/status')['base_pose_revision']
    history = []
    previous_signature = None
    #: 已确认误检的体素（整个家族）+ 落点豁免追加的对象，同时在每一条试用请求上下发。
    ignored_ids = {str(v) for v in (ignore_ids or ())}
    for attempt in range(1, max(1, rounds) + 1):
        tag = '%s_r%d' % (label, attempt)
        signature = []
        for index, mode in enumerate(('FAST', 'QUALITY', 'QUALITY'), start=1):
            if api('/api/scene/status')['base_pose_revision'] != scene_before:
                raise SystemExit('base pose changed during planning; target invalid')
            trial = dict(payload, planning_mode=mode, request_label='%s_TRY%d' % (tag, index))
            if ignored_ids:
                trial['ignore_cuboid_ids'] = sorted(ignored_ids)
            started = time.monotonic()
            handle, error, busy_waits = plan_request(trial, deadline_s, tag, mode, progress)
            if handle is None:
                signature.append('%s:%s' % (mode, error))
                # 一次规划失败可能**依次**出现多个可豁免原因（2026-11-09 实测：
                # 先「落点穿透」→ 豁免后重规划 → 起点又被鬼影穿透 1.26 mm）。
                # 所以这里用循环逐次处理，而不是 if/elif 二选一。
                for extra in range(3):
                    if handle is not None:
                        break
                    text = str(error)
                    added = []
                    if 'INVALID_GOAL_COLLISION' in text:
                        report = goal_collision_report(error, label, descent_m or 0.0, out)
                        # 现场确认的误检家族：整族排除（不只落点穿透的那几个），
                        # 否则下一次扫描重新编号后会变成路径上的限隙对象。
                        family = false_positive_voxel_ids(error, fp_prefixes)
                        if family:
                            new = [n for n in family if n not in ignored_ids]
                            ignored_ids.update(family)
                            added.extend(new)
                            save(out / ('false-positive-voxels-%s.json' % label), dict(
                                label=label, mode=mode, policy_prefixes=list(fp_prefixes),
                                ignored_cuboid_ids=sorted(ignored_ids), added=new,
                                note='现场确认这些观测体素为误检：按前缀整族从碰撞世界排除，'
                                     '名称取自当次规划请求的净空表（worker 对未知名字 fail-closed）'))
                            print(json.dumps(dict(label=label,
                                                  state='FALSE_POSITIVE_VOXELS_EXCLUDED',
                                                  added=len(new), total=len(ignored_ids)),
                                             ensure_ascii=False), flush=True)
                        admitted = waiver_admit(waiver, report)
                        if admitted:
                            waived = sorted(set(ignored_ids) | set(admitted))
                            ignored_ids.update(admitted)
                            added.extend(admitted)
                            waiver.setdefault('names', []).extend(
                                name for name in admitted
                                if name not in waiver.get('names', []))
                            save(out / ('goal-collision-waiver-%s.json' % label), dict(
                                label=label, mode=mode, ignored_cuboid_ids=waived,
                                admitted=admitted, policy=dict(waiver.get('policy') or {}),
                                penetration=report.get('offenders'),
                                note='现场确认这些体素为误检，已从碰撞世界排除后重新规划同一段'))
                            print(json.dumps(dict(label=label, state='GOAL_COLLISION_WAIVED',
                                                  ignored_cuboid_ids=waived),
                                             ensure_ascii=False), flush=True)
                        elif not family and waiver.get('enabled'):
                            # 豁免开着但这次不能给（对象不在白名单/超深）——把原因说清楚。
                            reason = waiver_rejection(waiver, report)
                            offenders = [dict(object=row.get('object'),
                                              clearance_mm=row.get('clearance_mm'))
                                         for row in (report.get('offenders') or [])]
                            save(out / ('goal-collision-waiver-rejected-%s.json' % label),
                                 dict(label=label, mode=mode,
                                      state='GOAL_COLLISION_WAIVER_REJECTED',
                                      rejection=reason, offenders=offenders,
                                      policy=dict(waiver.get('policy') or {})))
                            print(json.dumps(dict(label=label,
                                                  state='GOAL_COLLISION_WAIVER_REJECTED',
                                                  rejection=reason,
                                                  offenders=[o['object'] for o in offenders]),
                                             ensure_ascii=False), flush=True)
                    elif 'INVALID_START_COLLISION' in text:
                        report = start_collision_report(error, label, out)
                        admitted = waiver_admit(start_waiver, report)
                        if admitted:
                            start_waiver.setdefault('names', []).extend(
                                name for name in admitted
                                if name not in start_waiver.get('names', []))
                            ignored_ids.update(admitted)
                            added.extend(admitted)
                            save(out / ('start-collision-waiver-%s.json' % label), dict(
                                label=label, mode=mode,
                                ignored_cuboid_ids=sorted(ignored_ids),
                                admitted=admitted,
                                policy=dict(start_waiver.get('policy') or {}),
                                penetration=report.get('offenders'),
                                note='现场确认起点处的这些体素为误检，已从碰撞世界排除后重新规划同一段'))
                            print(json.dumps(dict(label=label, state='START_COLLISION_WAIVED',
                                                  ignored_cuboid_ids=sorted(ignored_ids)),
                                             ensure_ascii=False), flush=True)
                    if not added:
                        break
                    retry_trial = dict(trial, ignore_cuboid_ids=sorted(ignored_ids))
                    started = time.monotonic()
                    handle, error, busy_waits = plan_request(retry_trial, deadline_s,
                                                             tag, mode, progress)
                    if handle is None:
                        signature.append('%s:waiver%d:%s' % (mode, extra + 1, error))
                if handle is None:
                    history.append(dict(round=attempt, attempt=index, mode=mode,
                                        elapsed_s=round(time.monotonic() - started, 3),
                                        busy_waits=busy_waits, error=error))
                    save(out / ('%s.attempt%d.json' % (tag, index)), history[-1])
                    continue
            step = dict(round=attempt, attempt=index, mode=mode,
                        elapsed_s=round(time.monotonic() - started, 3),
                        busy_waits=busy_waits,
                        plan_id=handle.get('plan_id'), ready=handle.get('execution_package_ready'),
                        error=handle.get('execution_package_error'))
            history.append(step)
            save(out / ('%s.attempt%d.json' % (tag, index)), step)
            if not handle.get('execution_package_ready'):
                signature.append('%s:pkg:%s' % (mode, step.get('error')))
                continue
            record = dict(plan_id=handle['plan_id'], trajectory_hash=handle['trajectory_hash'],
                          scene_snapshot_id=handle.get('scene_snapshot_id'),
                          plan_artifact=handle.get('plan_artifact'), planning_mode=mode,
                          attempts=history)
            try:
                prove_plan(record, tag, out, tolerance_deg=tolerance_deg,
                           final_yaw_rad=final_yaw_rad, descent_m=descent_m,
                           strict_descent=strict_descent, descent_limits=descent_limits)
            except SystemExit as exc:
                step['rejected'] = str(exc)[-300:]
                signature.append('%s:reject:%s' % (mode, step['rejected']))
                save(out / ('%s.attempt%d.json' % (tag, index)), step)
                continue
            save(out / ('%s.plan_handle.json' % tag), handle)
            return record
        # 同一场景下 cuRobo 对同一请求是确定性的：整轮被同一原因拒掉时，
        # 再跑下一轮只会重新计入一次相同结果（实测 3 轮 × 3 模式 ≈ 150 s）。
        if previous_signature is not None and signature == previous_signature:
            save(out / ('%s.rounds-skipped.json' % label), dict(
                round=attempt, reason='IDENTICAL_REJECTION_ACROSS_ROUNDS',
                signature=signature,
                note='同一场景快照 + 同一拒因，后续轮次不可能改变结果，提前结束'))
            print(json.dumps(dict(label=label, state='ROUNDS_SKIPPED_IDENTICAL',
                                  round=attempt, signature=signature[:2]),
                             ensure_ascii=False), flush=True)
            break
        previous_signature = signature
    save(out / ('%s.failed.json' % label), history)
    raise SystemExit('%s: no accepted plan (%d attempts); 首次拒因：%s'
                     % (label, len(history),
                        (history[0].get('rejected') or history[0].get('error') or '')[-400:]))


def clear_residual_servo(out):
    """幂等地关闭控制器残留的 servo 模式。

    原生执行器（`scripts/jaka_right_demo.cpp`）在开跑前会检查
    `is_in_servomove / queue / active_queue / inpos`，任一不满足就抛
    `not idle / pre-existing servo`。上一轮 FAULT（如 2026-11-09 的
    `status code=-3`）可能把 servo 模式留在开启状态，导致下一次预检直接失败。
    这里每次都关一次（已关时是空操作），并写证据。
    """
    from ares_r.adapters.jaka_sdk import JakaSdkArm, _value
    sdk = load(ROOT / 'config/system.json')['jaka']
    arm = JakaSdkArm('right', sdk['arms']['right'], sdk)
    try:
        before = list(_value(arm.robot.get_robot_state(), 'robot state'))
        code = arm.robot.servo_move_enable(False)
        time.sleep(0.2)
        after = list(_value(arm.robot.get_robot_state(), 'robot state'))
        record = dict(action='servo_move_enable(False)', return_code=list(code),
                      robot_state_before=before, robot_state_after=after,
                      in_position=int(_value(arm.robot.is_in_pos(), 'in position')))
        save(Path(out) / 'residual-servo-clear.json', record)
        print(json.dumps(dict(preflight='RESIDUAL_SERVO_CLEAR', **record),
                         ensure_ascii=False), flush=True)
        return record
    finally:
        try:
            arm.close()
        except Exception:                                     # noqa: BLE001
            pass


def soft_limit_report(joints_rad, margin_rad=None):
    """站点软限位诊断：原生执行包打包时必须落在 [lower+soft, upper-soft] 内。"""
    site = load(SITE_FILE)
    soft = (float(site.get('soft_limit_margin_rad') or 0.0)
            if margin_rad is None else float(margin_rad))
    lower = np.asarray(site['lower_rad'], dtype=float) + soft
    upper = np.asarray(site['upper_rad'], dtype=float) - soft
    q = np.asarray(joints_rad if joints_rad else [], dtype=float)
    violations = []
    for index in range(min(6, q.size)):
        if q[index] < lower[index] - 1e-9 or q[index] > upper[index] + 1e-9:
            violations.append(dict(
                joint=index + 1, value_deg=round(math.degrees(float(q[index])), 2),
                allowed_low_deg=round(math.degrees(float(lower[index])), 2),
                allowed_high_deg=round(math.degrees(float(upper[index])), 2),
                excess_deg=round(math.degrees(max(lower[index] - q[index],
                                                 q[index] - upper[index])), 2)))
    return dict(passed=not violations, soft_margin_deg=round(math.degrees(soft), 3),
                violations=violations)


def controller_body_move(params, out, body_vector_m, *, speed_mm_s=None, progress=None,
                         label='descend', ik=None, seed_joints=None):
    """控制器原生直线平移（等价于 JAKA App 里沿某个 BODY 轴 jog）。

    刻意**不经过 cuRobo**：位置来自控制器实时 TCP，姿态原样保持，只把
    `body_vector_m`（BODY 系平移量，米）换算到控制器基座系做一次 `linear_move`
    （MoveL）。下降用 `[0,0,-60mm]`；松爪后后退用 `[-40mm,0,0]`（方向与 demo-3 的
    retreat 段一致）。

    仍然强制以下守卫（不满足即拒绝，零运动）：
      * `--execute` 授权链（本函数的调用点负责）；
      * 控制器 errcode / emergency_stop / protective_stop / drag_mode /
        on_soft_limit / is_on_limit / is_in_collision 全清；
      * 控制器 `tool_id` 必须等于 `parameters.json:required_tool_id`；
      * 站点速度上限：按当前位姿数值微分估算关节速度，超限即拒绝；
      * 运动中逐 200 ms 轮询控制器；出现 errcode/collision/protective_stop 立即
        `motion_abort()` 并报错（不自动清除保护停）；SDK 查询瞬态失败重试并
        重建会话。
    """
    from ares_r.adapters.jaka_sdk import JakaSdkArm, _value, parse_robot_status
    from ares_r.perception.robot_collision import transform_xyz_rpy

    platform = params['platform']
    stage = params['stages']['dmp_place']
    speed = float(speed_mm_s if speed_mm_s is not None
                  else stage.get('descent_speed_mm_s', 10.0))
    vector = np.asarray([float(v) for v in body_vector_m], dtype=float)
    travel_mm = float(np.linalg.norm(vector)) * 1000.0
    if not 1.0 <= travel_mm <= 200.0:
        raise SystemExit('direct move must travel 1..200 mm, got %.2f mm' % travel_mm)
    if not 1.0 <= speed <= 50.0:
        raise SystemExit('direct move speed must be 1..50 mm/s, got %.2f' % speed)
    sdk = load(ROOT / 'config/system.json')['jaka']
    world = load(ROOT / 'config/robot_world.json')
    ceiling = max(float(v) for v in load(SITE_FILE)['max_velocity_rad_s'])

    arm = JakaSdkArm('right', sdk['arms']['right'], sdk)
    record = dict(mode='CONTROLLER_LINEAR_MOVE', api='linear_move', speed_mm_s=speed,
                  requested_body_vector_m=[round(float(v), 5) for v in vector],
                  requested_travel_mm=round(travel_mm, 2), ceiling_rad_s=ceiling)
    try:
        robot = arm.robot

        def reconnect():
            """SDK 会话损坏（`status code=-3` / `returned a result with an exception
            set`）时重建一个独立会话；2026-11-09 实机几次失败都是这个原因。"""
            nonlocal robot
            try:
                robot.logout()
            except Exception:                                     # noqa: BLE001
                pass
            fresh = arm._readonly_rc_factory(arm.ip)
            _value(fresh.login(), 'sdk relogin')
            arm.robot = fresh
            robot = fresh
            return fresh

        status = parse_robot_status(_value(robot.get_robot_status(), 'robot status'))
        blocked = [name for name in ('errcode', 'emergency_stop', 'protective_stop',
                                     'drag_mode', 'on_soft_limit') if status.get(name)]
        if blocked:
            raise SystemExit('direct descent blocked: controller %s not clear: %s'
                             % (sorted(blocked), json.dumps(
                                 {k: status.get(k) for k in blocked})))
        if not status.get('enabled') or not status.get('powered_on'):
            raise SystemExit('direct descent blocked: controller not powered/enabled')
        tool_id = int(_value(robot.get_tool_id(), 'tool id'))
        record['tool_id'] = tool_id
        if tool_id != int(params['required_tool_id']):
            raise SystemExit('direct descent blocked: controller tool_id %d != required %d'
                             % (tool_id, int(params['required_tool_id'])))
        if int(_value(robot.is_on_limit(), 'limit state')):
            raise SystemExit('direct descent blocked: controller reports limit')
        if int(_value(robot.is_in_collision(), 'collision state')):
            raise SystemExit('direct descent blocked: controller reports collision')

        start_pose = [float(v) for v in _value(robot.get_tcp_position(), 'tcp position')]
        start_joints = [float(v) for v in _value(robot.get_joint_position(), 'joint positions')]
        rotation = np.asarray(transform_xyz_rpy(world['arms']['right']['base_xyz_m'],
                                                world['arms']['right']['base_rpy_rad'])
                              )[:3, :3]
        delta_base_mm = rotation.T @ (vector * 1000.0)
        target = list(start_pose)
        for index in range(3):
            target[index] += float(delta_base_mm[index])
        record.update(start_tcp_mm_rad=start_pose, target_tcp_mm_rad=target,
                      base_frame_delta_mm=[round(float(v), 3) for v in delta_base_mm],
                      joints_before_rad=start_joints)

        # 站点速度上限 + 软限位：用运行学数值解目标关节，按预期时长换算关节速度；
        # 若目标关节会越站点软限位（hard 限位再内缩 soft_limit_margin_rad），
        # 就沿同一方向逐步缩短行程，直到可行（记录 clamped）。
        expected_s = travel_mm / speed
        joint_rate = None
        applied_vector = vector.copy()
        if ik is not None and seed_joints:
            try:
                from ares_r.motion.se3 import pose_mm_rad_to_matrix
                body_base = np.asarray(transform_xyz_rpy(
                    world['arms']['right']['base_xyz_m'],
                    world['arms']['right']['base_rpy_rad']), dtype=float)
                start_body = body_base @ np.asarray(pose_mm_rad_to_matrix(start_pose), dtype=float)
                feasible = None
                trimmed = 0.0
                while travel_mm - trimmed >= 5.0:
                    scale = (travel_mm - trimmed) / travel_mm
                    trial = vector * scale
                    goal_body = start_body.copy()
                    goal_body[:3, 3] = start_body[:3, 3] + trial
                    try:
                        solution = ik.solve(goal_body[:3, 3], goal_body[:3, :3],
                                            np.asarray(seed_joints, dtype=float))
                    except Exception:                             # noqa: BLE001
                        trimmed += 2.0
                        continue
                    limit = soft_limit_report(solution.joints_rad)
                    if limit['passed']:
                        feasible = (trial, solution, limit, trimmed)
                        break
                    trimmed += 2.0
                if feasible is None:
                    save(Path(out) / ('%s.direct-move.json' % label), record)
                    raise SystemExit('direct move blocked: 沿该 BODY 方向没有可行行程 '
                                     '（会让关节越站点软限位）')
                applied_vector, solution, limit, trimmed = feasible
                points = [float(v) for v in solution.joints_rad]
                joint_rate = max(abs(float(a) - float(b)) for a, b in
                                 zip(points, seed_joints)) / expected_s
                record.update(applied_body_vector_m=[round(float(v), 5) for v in applied_vector],
                              clamped_mm=round(float(trimmed), 2),
                              predicted_joint_rate_rad_s=round(float(joint_rate), 5),
                              predicted_soft_limit=limit,
                              predicted_goal_joints_rad=[round(float(v), 6) for v in points])
                if trimmed > 0:
                    print(json.dumps(dict(state='DISTANCE_CLAMPED', requested_mm=round(travel_mm, 1),
                                         applied_mm=round(travel_mm - trimmed, 1),
                                         note='目标关节会越站点软限位，已自动缩短行程'),
                                     ensure_ascii=False), flush=True)
                vector = applied_vector
                travel_mm = float(np.linalg.norm(vector)) * 1000.0
                expected_s = travel_mm / speed
            except SystemExit:
                raise
            except Exception as exc:                              # noqa: BLE001
                record['predicted_joint_rate_error'] = str(exc)[-200:]
        # 行程可能已被软限位裁剪，目标位姿必须在裁剪之后重算。
        delta_base_mm = rotation.T @ (vector * 1000.0)
        target = list(start_pose)
        for index in range(3):
            target[index] += float(delta_base_mm[index])
        record.update(target_tcp_mm_rad=target,
                      base_frame_delta_mm=[round(float(v), 3) for v in delta_base_mm])
        if joint_rate is not None and joint_rate > ceiling:
            save(Path(out) / ('%s.direct-move.json' % label), record)
            raise SystemExit('direct descent blocked: predicted joint rate %.3f rad/s '
                             '> site ceiling %.3f rad/s' % (joint_rate, ceiling))

        save(Path(out) / ('%s.direct-move.json' % label), record)
        print(json.dumps(dict(stage='place', state='DIRECT_MOVE_START',
                              mode=record['mode'], speed_mm_s=speed,
                              from_mm_rad=[round(v, 3) for v in start_pose],
                              to_mm_rad=[round(v, 3) for v in target],
                              expected_s=round(expected_s, 2)), ensure_ascii=False),
              flush=True)
        started = time.monotonic()
        launch = robot.linear_move(target, 0, 0, speed)
        if isinstance(launch, (tuple, list)) and launch and int(launch[0]) != 0:
            raise SystemExit('linear_move rejected: %r' % (launch,))

        def poll(method, what, attempts=3):
            """运动中轮询 SDK：控制器在 MoveL 期间会偶发返回 (-3,) 等瞬态错码；
            重试仍失败时重建会话再查一次（会话损坏不会自愈）。"""
            last = None
            for attempt in range(attempts):
                try:
                    return _value(getattr(robot, method)(), what)
                except Exception as exc:                          # noqa: BLE001
                    last = exc
                    if attempt + 1 < attempts:
                        time.sleep(0.05)
            try:
                reconnect()
                return _value(getattr(robot, method)(), what)
            except Exception as exc:                              # noqa: BLE001
                raise last from exc

        deadline = started + max(10.0, expected_s * 4.0 + 5.0)
        start_deadline = started + 5.0
        motion_started = False
        samples, failure = [], None
        misses = 0
        next_beat = started + PROGRESS_HEARTBEAT_S
        try:
            while time.monotonic() < deadline:
                try:
                    state = parse_robot_status(poll('get_robot_status', 'robot status'))
                    pose = [float(v) for v in poll('get_tcp_position', 'tcp position')]
                    collision = int(poll('is_in_collision', 'collision state'))
                    misses = 0
                except Exception as exc:                          # noqa: BLE001
                    # 单次查询失败不当作失败：记一采样、计数，连续失败才中止。
                    misses += 1
                    samples.append(dict(t=round(time.monotonic() - started, 3),
                                        sdk_error=str(exc)[-160:]))
                    if misses >= 5:
                        failure = ('SDK polling failed %d times in a row during the move: %s'
                                   % (misses, str(exc)[-200:]))
                        break
                    time.sleep(0.05)
                    continue
                moved_mm = float(np.linalg.norm(np.asarray(pose[:3]) - np.asarray(start_pose[:3])))
                # 控制器在收到非阻塞 MoveL 后的一小段时间里 `in_position` 仍为真，
                # 必须等到「离开到位状态」或「TCP 真的动了」才算运动已经开始。
                if (not state.get('in_position')) or moved_mm > 0.3:
                    motion_started = True
                samples.append(dict(t=round(time.monotonic() - started, 3),
                                    tcp_mm_rad=[round(v, 3) for v in pose],
                                    moved_mm=round(moved_mm, 2),
                                    errcode=int(state.get('errcode') or 0), collision=collision,
                                    in_position=bool(state.get('in_position'))))
                if state.get('errcode') or state.get('emergency_stop') or collision:
                    failure = ('controller stopped the move: errcode=%s protective_stop=%s '
                               'emergency_stop=%s collision=%s'
                               % (state.get('errcode'), state.get('protective_stop'),
                                  state.get('emergency_stop'), collision))
                    break
                if motion_started and state.get('in_position') and moved_mm > travel_mm * 0.5:
                    break
                if not motion_started and time.monotonic() > start_deadline:
                    failure = ('linear_move never started: controller stayed in_position and '
                               'TCP did not change for 5.0 s')
                    break
                if progress is not None and time.monotonic() >= next_beat:
                    progress.heartbeat(label=label)
                    next_beat = time.monotonic() + PROGRESS_HEARTBEAT_S
                # 0.2 s @ 5 Hz：2026-11-09 实机在 10 Hz 下多次拉到控制器
                # SDK 返回 (-3,) / `returned a result with an exception set`。
                time.sleep(0.2)
            else:
                failure = ('linear_move did not report in_position within %.1f s'
                           % (deadline - started))
        except BaseException:
            # 任何异常（含 SDK 查询失败/用户中断）都不能把运动留在无人监控状态。
            try:
                robot.motion_abort()
            except Exception:                                     # noqa: BLE001
                pass
            record.update(samples=samples[-40:], error='supervision aborted',
                          elapsed_s=round(time.monotonic() - started, 3))
            save(Path(out) / ('%s.direct-move.json' % label), record)
            raise
        if failure:
            try:
                robot.motion_abort()
            except Exception:                                     # noqa: BLE001
                pass
            record.update(samples=samples[-40:], error=failure,
                          elapsed_s=round(time.monotonic() - started, 3))
            save(Path(out) / ('%s.direct-move.json' % label), record)
            raise SystemExit('direct descent failed: ' + failure)

        elapsed = time.monotonic() - started
        time.sleep(0.2)
        end_pose = [float(v) for v in poll('get_tcp_position', 'tcp position')]
        end_joints = [float(v) for v in poll('get_joint_position', 'joint positions')]
        delta_base = np.asarray(end_pose[:3]) - np.asarray(start_pose[:3])
        delta_body = rotation @ delta_base
        requested_mm = vector * 1000.0
        delta_error_mm = float(np.linalg.norm(delta_body - requested_mm))
        lateral_mm = float(np.hypot(delta_body[0], delta_body[1]))
        measured_rate = (max(abs(a - b) for a, b in zip(end_joints, start_joints)) / elapsed
                         if elapsed > 0 else float('inf'))
        record.update(end_tcp_mm_rad=end_pose, joints_after_rad=end_joints,
                      elapsed_s=round(elapsed, 3),
                      actual_body_delta_mm=[round(float(v), 2) for v in delta_body],
                      delta_error_mm=round(delta_error_mm, 2),
                      lateral_mm=round(lateral_mm, 2),
                      measured_joint_rate_rad_s=round(float(measured_rate), 5),
                      samples=samples[-60:])
        save(Path(out) / ('%s.direct-move.json' % label), record)
        print(json.dumps(dict(stage='place', state='DIRECT_MOVE_DONE', label=label,
                              elapsed_s=round(elapsed, 2),
                              requested_body_mm=[round(float(v), 1) for v in requested_mm],
                              actual_body_delta_mm=record['actual_body_delta_mm'],
                              delta_error_mm=record['delta_error_mm'],
                              joint_rate_rad_s=record['measured_joint_rate_rad_s']),
                         ensure_ascii=False), flush=True)
        tolerance = float(platform['descent_tolerance_m']) * 1000.0
        if delta_error_mm > tolerance:
            raise SystemExit('direct move displacement off: body %s (want %s), error %.1f mm'
                             % (record['actual_body_delta_mm'],
                                [round(float(v), 1) for v in requested_mm], delta_error_mm))
        if measured_rate > ceiling:
            print(json.dumps(dict(state='WARNING_JOINT_RATE', measured=round(float(measured_rate), 4),
                                  ceiling=ceiling), ensure_ascii=False), flush=True)
        return record
    finally:
        try:
            arm.close()
        except Exception:                                         # noqa: BLE001
            pass


def execute_plan(record, label, out, timeout_s=600, progress=None):
    body = dict(plan_id=record['plan_id'], trajectory_hash=record['trajectory_hash'],
                authorization=MOTION_API_AUTHORIZATION, onsite_observer_confirmed=True,
                command_id='%s_%s_%d' % (DEMO_ID.upper(), label.upper(),
                                         int(time.time() * 1000) % 10 ** 9))
    save(out / ('%s.execute-request.json' % label), body)
    save(out / ('%s.telemetry-dispatch.json' % label), api('/api/operations/telemetry', {},
                                                            timeout=40))
    # The marker lands BEFORE the dispatch: a crash here is UNCERTAIN, never a silent
    # re-dispatch.
    marker = out / ('%s.dispatched-once.json' % label)
    if marker.exists():
        raise SystemExit('%s: this directory already dispatched; refusing to re-dispatch'
                         % label)
    save(marker, dict(state='UNCERTAIN', at_unix=time.time(), body=body))
    try:
        dispatched = api('/api/operations/execute', body, timeout=120)
    except ApiError as exc:
        # 409 = backend precondition rejected before any motion (e.g. plan handle
        # no longer the current one); 5xx / timeouts stay UNCERTAIN on purpose.
        if exc.code == 409:
            save(marker, dict(state='REJECTED_409', at_unix=time.time(), body=body,
                              error=str(exc)[-1500:]))
        raise
    save(out / ('%s.start.json' % label), dispatched)
    deadline = time.monotonic() + timeout_s
    next_beat = time.monotonic() + PROGRESS_HEARTBEAT_S
    while time.monotonic() < deadline:
        state = api('/api/operations/run-status', timeout=30)
        if progress is not None and time.monotonic() >= next_beat:
            progress.heartbeat(label=label)
            next_beat = time.monotonic() + PROGRESS_HEARTBEAT_S
        if state.get('state') != 'RUNNING':
            save(out / ('%s.result.json' % label), state)
            if state.get('state') != 'SUCCEEDED':
                save(marker, dict(state='DISPATCHED_FAILED', at_unix=time.time(), body=body))
                raise SystemExit('%s failed: %s / %s' % (label, state.get('state'),
                                                         state.get('failure_reason')
                                                         or state.get('study_error')))
            save(marker, dict(state='DISPATCHED', at_unix=time.time(), body=body))
            result = state.get('execution_result') or {}
            print(json.dumps(dict(label=label, state=state['state'],
                                  elapsed_s=result.get('elapsed_s'),
                                  tracking_error_deg=(result.get('tracking_error_deg') or {}
                                                      ).get('max')),
                             ensure_ascii=False), flush=True)
            return state
        time.sleep(0.8)
    raise SystemExit('%s: timeout without terminal state; do NOT re-dispatch' % label)


def transient_zero_motion_failure(out, label):
    """只对「已知的零运动控制器门瞬态」返回 True；其它任何失败一律上抛。

    四条同时成立才允许重试：
      1) 状态 FAULT 且 failure_reason 含 `errcode=4128769`；
      2) 原生执行 0 采样（完全没动）；
      3) 控制器现在 errcode/保护停/急停/drag/软限位全清；
      4) 当前关节与派发前快照相差 ≤ 0.2°。
    """
    out = Path(out)
    state = load(out / ('%s.result.json' % label), {}) or {}
    reason = str(state.get('failure_reason') or '')
    if state.get('state') != 'FAULT' or TRANSIENT_SAFETY_GATE not in reason:
        return False
    if int((state.get('execution_result') or {}).get('sample_count') or 0) != 0:
        return False
    live = api('/api/operations/telemetry', {})
    right = (live.get('arms') or {}).get('right') or {}
    controller = right.get('controller_status') or {}
    if any(controller.get(key) for key in ('errcode', 'emergency_stop', 'protective_stop',
                                           'drag_mode', 'on_soft_limit')):
        return False
    before = ((load(out / ('%s.telemetry-dispatch.json' % label), {}) or {}
               ).get('arms') or {}).get('right') or {}
    start, now = before.get('joints_rad'), right.get('joints_rad')
    if not start or not now:
        return False
    return max(abs(a - b) for a, b in zip(start, now)) * 180.0 / math.pi <= UNMOVED_TOLERANCE_DEG


def execute_leg(plan_callable, record, label, stage, out, progress):
    """派发一段；仅当命中已知零运动瞬态时，重新规划 + 重新派发一次。"""
    progress.begin(stage, 'MOVE_%s' % label.upper(), 'execute')
    try:
        execute_plan(record, label, out, progress=progress)
        return record
    except SystemExit:
        if not transient_zero_motion_failure(out, label):
            raise
        retry = Path(out) / ('retry-%s-1' % label)
        retry.mkdir(parents=True, exist_ok=True)
        save(retry / 'retry-reason.json', dict(
            first_attempt=str(out),
            failure=(load(Path(out) / ('%s.result.json' % label), {}) or {}).get('failure_reason'),
            policy='KNOWN_ZERO_MOTION_CONTROLLER_GATE; one fresh plan and one dispatch',
            sample_count=0, controller_clear=True, joints_unmoved_within_deg=UNMOVED_TOLERANCE_DEG))
        print(json.dumps(dict(label=label, state='TRANSIENT_ZERO_MOTION_RETRY_ONCE'),
                         ensure_ascii=False), flush=True)
        fresh = plan_callable(retry)
        progress.begin(stage, 'MOVE_%s_RETRY' % label.upper(), 'execute')
        execute_plan(fresh, label, retry, progress=progress)
        return fresh


# -------------------------------------------------------------------- stage 1
def mm(values):
    return [round(float(v) * 1000.0, 1) for v in values]


def place_geometry(base_point, offset, descent, direct_place=False):
    """解析这一段的几何：返回 `(leg_target, place, descent)`。

    常规（`plan_direct_to_place=false`，demo-5）：
        preplace = detection + offset；place = preplace − descent
        两段：先到预放置点，再用控制器 MoveL 下降 descent。

    直放（`plan_direct_to_place=true`，demo-6 2026-11-09 现场要求）：
        取消预放置点，**只有一条腿**，目标就是放置点 = detection + offset，
        `descent` 归零（不再有控制器 MoveL 下降段，规划到位后直接松爪）。
        此时 offset 直接作用在放置点上，不再有「预放置点抬高多少」的含义。
    """
    offset = [float(v) for v in offset]
    base = [float(v) for v in base_point]
    if direct_place:
        place = [b + o for b, o in zip(base, offset)]
        return list(place), place, 0.0
    leg = [b + o for b, o in zip(base, offset)]
    place = [leg[0], leg[1], leg[2] - float(descent)]
    return leg, place, float(descent)


def preplace_report(out, detection, offset, preplace, place, descent, current_tcp,
                    direct_place=False):
    """落地「预放置点 = 检测返回点 + BODY 偏移」这一条，方便现场改偏移。"""
    body = [float(v) for v in detection['detection_body_m_rad'][:3]]
    record = dict(
        demo_id=DEMO_ID,
        detection_source='5700 %s（epic_command=%s）' % (detection.get('epic_command'),
                                                        detection.get('captured_at_unix')),
        detection_body_mm=mm(body),
        detection_body_rpy_deg=[round(float(v), 3)
                                for v in (detection.get('detection_body_rpy_deg') or [])],
        preplace_offset_body_mm=mm(offset),
        preplace_offset_source='parameters.json:stages.dmp_place.preplace_offset_body_m'
                              '（可用 --preplace-offset X Y Z 覆盖）',
        plan_direct_to_place=bool(direct_place),
        leg_target_body_mm=mm(preplace),
        preplace_body_mm=None if direct_place else mm(preplace),
        descent_mm=round(float(descent) * 1000.0, 1),
        place_body_mm=mm(place),
        tcp_before_body_mm=mm(current_tcp),
        tcp_to_preplace_mm=mm(np.asarray(preplace, dtype=float) - np.asarray(current_tcp)),
        tcp_to_leg_target_mm=mm(np.asarray(preplace, dtype=float) - np.asarray(current_tcp)),
        formula=('place = detection_body + offset_body（直放：没有预放置点、没有下降段）'
                 if direct_place else
                 'preplace = detection_body + offset_body; place = preplace - [0, 0, descent]'),
        note='偏移是 BODY 坐标（x 前 / y 左 / z 上），相对检测返回点，不是相对当前 TCP。')
    save(Path(out) / 'preplace-offset.json', record)
    return record


def place_plan_payload(position, label, scene_policy, rotation, platform, demo_id,
                       hard_level_manifold=None, yaw_rad=None):
    """构造放置腿的 `/api/motion/plan` 请求体。

    默认 `TERMINAL_EXPLICIT`：只约束终点姿态，中途由 cuRobo 自由优化，规划完才由
    `validate_level_path` 的 5° 硬门限事后否决（demo-5/6 的既有行为）。

    `stages.dmp_place.hard_level_manifold` 打开时改为 `EXPLICIT + hard_level_manifold`：
    显式姿态沿整条路径都参与优化，worker 还会沿水平流形生成连续 IK 种子，避免
    「规划 40 s → 中途倾斜 7.6° → 整条扔掉」的重复浪费（2026-11-11 实测）。
    """
    body = dict(arm='right', position_m=[float(v) for v in position],
                speed_profile=platform['motion_speed_profile'], scene_policy=scene_policy,
                environment_avoidance=platform['environment_avoidance'],
                source=demo_id.upper(), request_label=label)
    body.update(orientation='TERMINAL_EXPLICIT',
                explicit_rotation=np.asarray(rotation, dtype=float).tolist())
    if hard_level_manifold:
        manifold = (dict(hard_level_manifold)
                    if isinstance(hard_level_manifold, dict) else {})
        if yaw_rad is not None:
            manifold.setdefault('goal_yaw_rad', float(yaw_rad))
        body.update(orientation='EXPLICIT', hard_level_manifold=manifold)
    return body


def detect_place_target(params, out):
    from ares_r.adapters.epic import EpicClient
    from ares_r.motion.grasp import rotation_matrix
    from ares_r.perception.robot_collision import transform_xyz_rpy        # noqa: F401
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
                yaw_override=None, stop_after='release', level_tolerance_deg=None,
                progress=None):
    stage = params['stages']['dmp_place']
    platform = params['platform']
    out.mkdir(parents=True, exist_ok=False)
    deadline = float(load(ROOT / 'config/system.json')['curobo']['timeout_s'])
    offset = [float(v) for v in (offset_override or stage['preplace_offset_body_m'])]
    descent = float(descent_override if descent_override is not None else stage['descent_m'])
    # 直放模式（`plan_direct_to_place`）：取消预放置点，只有一条腿直接到放置点，
    # 不再有控制器 MoveL 下降段（offset 直接作用在放置点上）。
    direct_place = bool(stage.get('plan_direct_to_place'))
    if direct_place and descent_override:
        print(json.dumps(dict(stage='place', state='DESCENT_OVERRIDE_IGNORED',
                              plan_direct_to_place=True, descent_override_m=descent_override,
                              note='直放模式没有预放置点与下降段，--descent-m 本次不生效'),
                         ensure_ascii=False), flush=True)
    tolerance = float(level_tolerance_deg if level_tolerance_deg is not None
                      else platform['level_tolerance_deg'])

    progress = progress or Progress()
    progress.begin('DETECT', 'DETECT_5700', 'prep')
    grip_snapshot(out, 'before-place')
    detection = detect_place_target(params, out)
    base_point = [float(v) for v in detection['detection_body_m_rad'][:3]]
    preplace, place, descent = place_geometry(base_point, offset, descent, direct_place)

    state = telemetry()
    controller_guard(state)
    tool_guard(state, params['required_tool_id'])
    tilt = start_tilt_guard(state, tolerance, out)
    waiver_policy = stage.get('goal_collision_waiver') or {}
    waiver = dict(enabled=bool(waiver_policy.get('enabled')), names=[],
                  max_penetration_mm=float(waiver_policy.get('max_penetration_mm', 10.0)),
                  allowed_prefixes=tuple(waiver_policy.get('allowed_prefixes') or ()),
                  policy=dict(waiver_policy))
    start_policy = stage.get('start_collision_waiver') or {}
    # 现场确认误检的体素家族：从规划错误的净空表里按前缀整族排除（见
    # false_positive_voxel_ids）。名字仍取自当次真实场景，不在白名单/不存在的名字
    # 都由 worker 侧 fail-closed 拒绝。
    fp_policy = stage.get('false_positive_voxels') or {}
    fp_prefixes = (tuple(fp_policy.get('allowed_prefixes') or ())
                   if fp_policy.get('enabled') else ())
    start_waiver = dict(enabled=bool(start_policy.get('enabled')), names=[],
                        max_penetration_mm=float(start_policy.get('max_penetration_mm', 5.0)),
                        allowed_prefixes=tuple(start_policy.get('allowed_prefixes') or ()),
                        policy=dict(start_policy))
    reference = dict(arms=state['arms'])
    report = preplace_report(out, detection, offset, preplace, place, descent,
                             tcp_of(state)[:3, 3], direct_place)
    print(json.dumps(dict(stage='place',
                          state='PLACE_TARGET' if direct_place else 'PREPLACE_TARGET',
                          plan_direct_to_place=bool(direct_place),
                          detection_body_mm=report['detection_body_mm'],
                          preplace_offset_body_mm=report['preplace_offset_body_mm'],
                          leg_target_body_mm=report['leg_target_body_mm'],
                          preplace_body_mm=report['preplace_body_mm'],
                          descent_mm=report['descent_mm'],
                          place_body_mm=report['place_body_mm'],
                          tcp_before_body_mm=report['tcp_before_body_mm'],
                          tcp_to_leg_target_mm=report['tcp_to_leg_target_mm']),
                     ensure_ascii=False), flush=True)
    yaw_requested = yaw_override if yaw_override is not None else stage.get('yaw_target_deg')
    rotation, yaw, branch = level_orientation(
        state, None if yaw_requested is None else math.radians(float(yaw_requested)))
    manifold_spec = stage.get('hard_level_manifold')
    save(out / 'place-contract.json', dict(
        detection_body_m_rad=base_point, offset_body_m=offset,
        plan_direct_to_place=bool(direct_place), leg_target_body_m=preplace,
        preplace_body_m=None if direct_place else preplace,
        place_body_m=place, descent_m=descent, yaw_target_rad=yaw, roll_branch=branch,
        tool_id=state['arms']['right'].get('tool_id'),
        release_raw=stage['release_raw'], level_tolerance_deg=tolerance,
        start_tilt_deg=tilt['max_tilt_deg'],
        hard_level_manifold=dict(manifold_spec) if isinstance(manifold_spec, dict)
        else (bool(manifold_spec)),
        goal_collision_waiver=dict(enabled=waiver['enabled'],
                                   max_penetration_mm=waiver['max_penetration_mm'],
                                   allowed_prefixes=list(waiver['allowed_prefixes'])),
        planning_modes=platform['planning_modes'], rounds=platform['planning_rounds'],
        authorization=MOTION_API_AUTHORIZATION, execute=bool(execute)))

    def payload(position, label, scene_policy):
        return place_plan_payload(position, label, scene_policy, rotation, platform,
                                  DEMO_ID, manifold_spec, yaw)

    common = dict(tolerance_deg=tolerance, final_yaw_rad=yaw,
                  rounds=int(platform['planning_rounds']), progress=progress,
                  waiver=waiver, start_waiver=start_waiver, fp_prefixes=fp_prefixes)

    # 直放模式只有一条腿（目标 = 放置点）；常规模式是「预放置点 + 下降」。
    leg_label = 'place' if direct_place else 'preplace'
    leg_title = 'DMP_PLACE' if direct_place else 'DMP_PREPLACE'
    leg_stage = 'PLACE' if direct_place else 'PREPLACE'
    leg_phase = 'PLAN_PLACE' if direct_place else 'PLAN_PREPLACE'

    def plan_place_leg(directory=None):
        target = Path(directory) if directory else out
        progress.begin(leg_stage, leg_phase, 'plan')
        record = plan_leg(payload(preplace, leg_title, platform['scene_policy_place']),
                          leg_label, target, deadline, **common)
        record['authorization'] = MOTION_API_AUTHORIZATION
        request_path = ROOT / record['plan_artifact'] / 'planner_request.json'
        save(target / 'planned-tool-binding.json', dict(
            tool_id=state['arms']['right'].get('tool_id'),
            required_tool_id=int(params['required_tool_id']),
            controller_tool_pose_mm_rad=(load(request_path, {}) or {}
                                         ).get('controller_tool_pose_mm_rad'),
            source=str(request_path)))
        return record

    def plan_descend(directory=None):
        target = Path(directory) if directory else out
        progress.begin('DESCEND', 'PLAN_DESCEND', 'plan')
        record = plan_leg(payload(place, 'DMP_DESCENT', platform['scene_policy_place']),
                          'descend', target, deadline, descent_m=descent,
                          descent_limits=dict(
                              enabled=bool(platform.get('descent_axis_gate_enabled', True)),
                              lateral_mm=platform.get('descent_lateral_tolerance_mm', 20.0),
                              min_below_goal_mm=platform.get('descent_min_z_above_goal_mm',
                                                             -2.0)),
                          **common)
        record['authorization'] = MOTION_API_AUTHORIZATION
        return record

    current = tcp_of(state)[:3, 3]
    at_leg = float(np.linalg.norm(current - np.asarray(preplace)))
    skip_tol = float(stage.get('skip_preplace_within_tolerance_m') or 0.0)
    skip_preplace = bool(skip_tol > 0.0 and at_leg <= skip_tol)

    pre = None if skip_preplace else plan_place_leg(out)
    descent_mode = str(stage.get('descent_mode') or 'CUROBO_PLAN').upper()
    if not execute:
        if direct_place:
            save(out / 'plans.json', dict(
                place=None if pre is None else {k: v for k, v in pre.items()
                                                if k != 'attempts'},
                descend=dict(mode='SKIPPED_DIRECT_PLACE', descent_m=0.0,
                             note='plan_direct_to_place=true：没有预放置点，也没有下降段')))
            print(json.dumps(dict(stage='place', state='PLANNED_ONLY',
                                  plan_direct_to_place=True,
                                  place=None if pre is None else pre['plan_id'],
                                  descend='SKIPPED_DIRECT_PLACE',
                                  leg_target_body_mm=mm(preplace),
                                  place_body_mm=mm(place),
                                  already_at_place_mm=round(at_leg * 1000.0, 2),
                                  place_leg_skipped=skip_preplace),
                             ensure_ascii=False))
            return dict(state='PLANNED_ONLY', place_body_m=place)
        if descent_mode == 'CONTROLLER_LINEAR_MOVE':
            save(out / 'plans.json', dict(
                preplace=None if pre is None else {k: v for k, v in pre.items()
                                                  if k != 'attempts'},
                descend=dict(mode='CONTROLLER_LINEAR_MOVE_NOT_PLANNED',
                             descent_m=descent,
                             speed_mm_s=float(stage.get('descent_speed_mm_s', 10.0)))))
            print(json.dumps(dict(stage='place', state='PLANNED_ONLY',
                                  preplace=None if pre is None else pre['plan_id'],
                                  descend='CONTROLLER_LINEAR_MOVE(not planned)',
                                  preplace_body_mm=mm(preplace), place_body_mm=mm(place),
                                  descent_mm=round(descent * 1000.0, 1),
                                  already_at_preplace_mm=round(at_leg * 1000.0, 2),
                                  preplace_leg_skipped=skip_preplace),
                             ensure_ascii=False))
            return dict(state='PLANNED_ONLY', preplace_body_m=preplace, place_body_m=place)
        descending = plan_descend(out)
        save(out / 'plans.json', dict(
            preplace=None if pre is None else {k: v for k, v in pre.items()
                                               if k != 'attempts'},
            descend={k: v for k, v in descending.items() if k != 'attempts'},
            skipped='ALREADY_AT_PREPLACE' if skip_preplace else None))
        print(json.dumps(dict(stage='place', state='PLANNED_ONLY',
                              preplace=None if pre is None else pre['plan_id'],
                              descend=descending['plan_id'],
                              preplace_body_mm=mm(preplace), place_body_mm=mm(place),
                              descent_mm=round(descent * 1000.0, 1),
                              already_at_preplace_mm=round(at_leg * 1000.0, 2),
                              preplace_leg_skipped=skip_preplace),
                         ensure_ascii=False))
        return dict(state='PLANNED_ONLY', preplace_body_m=preplace, place_body_m=place)

    # 实机：预放置段先派发，下降段必须**到位后重新扫描再规划**。后端只允许派发
    # 「当前」plan handle，提前把下降段规划好会把预放置的 handle 顶掉
    # （2026-11-06 实测 409 `plan handle mismatch`）。
    if skip_preplace:
        save(out / ('%s-skipped.json' % leg_label), dict(
            state='SKIPPED_ALREADY_AT_TARGET', tcp_body_m=current.tolist(),
            target_body_m=preplace, error_mm=round(at_leg * 1000.0, 2),
            tolerance_m=skip_tol, plan_direct_to_place=bool(direct_place),
            note='当前 TCP 已在目标点公差内 → 跳过该段规划/派发'))
        print(json.dumps(dict(stage='place', state='SKIPPED_ALREADY_AT_TARGET',
                              error_mm=round(at_leg * 1000.0, 2),
                              target_mm=mm(preplace)),
                         ensure_ascii=False), flush=True)
        arrived, error = current, at_leg
        save(out / ('%s-arrival.json' % leg_label),
             dict(target=preplace, tcp=arrived.tolist(), error_m=error, skipped=True))
        save(out / 'plans.json', dict({leg_label: None}, skipped='ALREADY_AT_TARGET'))
    else:
        save(out / 'plans.json', dict({leg_label: {k: v for k, v in pre.items()
                                                   if k != 'attempts'}}))
        pre = execute_leg(plan_place_leg, pre, leg_label, leg_stage, out, progress)
        arrived = tcp_of(telemetry())[:3, 3]
        error = float(np.linalg.norm(arrived - np.asarray(preplace)))
        save(out / ('%s-arrival.json' % leg_label),
             dict(target=preplace, tcp=arrived.tolist(), error_m=error,
                  plan_direct_to_place=bool(direct_place)))
        if error > platform['arrival_tolerance_m']:
            raise SystemExit('%s arrival error %.1f mm' % (leg_label, error * 1000))
    if direct_place:
        # 直放模式：唯一的腿就是放置腿，到了就已经在放置点上——没有下降段。
        if stop_after in ('preplace', 'descend'):
            save(out / 'stop-after-place.json', dict(
                state='AT_PLACE', tcp_body_m=arrived.tolist(), target_body_m=place,
                error_m=error, error_mm=round(error * 1000, 2),
                plan_direct_to_place=True,
                tool_id=telemetry()['arms']['right'].get('tool_id'),
                note='只派发了唯一的放置腿（直放：无预放置点、无下降段）；夹爪未释放'))
            print(json.dumps(dict(stage='place', state='AT_PLACE',
                                  tcp_mm=mm(arrived), target_mm=mm(place),
                                  error_mm=round(error * 1000, 2)),
                             ensure_ascii=False), flush=True)
            return dict(state='AT_PLACE', tcp_body_m=arrived.tolist(),
                        place_body_m=place, error_mm=round(error * 1000, 2))
    if stop_after == 'preplace':
        save(out / 'stop-after-preplace.json', dict(
            state='AT_PREPLACE', tcp_body_m=arrived.tolist(), target_body_m=preplace,
            error_m=error, error_mm=round(error * 1000, 2),
            tool_id=telemetry()['arms']['right'].get('tool_id'),
            note='只派发了预放置段；下降段尚未规划/派发，夹爪未动'))
        print(json.dumps(dict(stage='place', state='AT_PREPLACE',
                              tcp_mm=mm(arrived), target_mm=mm(preplace),
                              error_mm=round(error * 1000, 2)),
                         ensure_ascii=False), flush=True)
        return dict(state='AT_PREPLACE', tcp_body_m=arrived.tolist(),
                    preplace_body_m=preplace, error_mm=round(error * 1000, 2))

    if direct_place:
        # 直放模式：唯一的腿就是放置腿，到了就已经在放置点上——没有下降段。
        save(out / 'descent-skipped.json', dict(
            state='DIRECT_PLACE_NO_DESCENT', plan_direct_to_place=True,
            place_body_m=place, arrived_body_m=arrived.tolist(),
            error_mm=round(error * 1000, 2), descent_m=0.0,
            note='plan_direct_to_place=true：取消预放置点，唯一一条腿的目标就是放置点；'
                 '不再有控制器 MoveL 下降段，到位后直接松爪'))
        plans = load(out / 'plans.json', {}) or {}
        plans['descend'] = dict(mode='SKIPPED_DIRECT_PLACE', descent_m=0.0,
                                note='直放模式：没有预放置点，也没有下降段')
        save(out / 'plans.json', plans)
        print(json.dumps(dict(stage='place', state='DIRECT_PLACE_AT_PLACE',
                              tcp_mm=mm(arrived), place_mm=mm(place),
                              error_mm=round(error * 1000, 2),
                              descent='SKIPPED_DIRECT_PLACE'),
                         ensure_ascii=False), flush=True)
        before, delta = arrived, np.zeros(3, dtype=float)
    elif descent_mode == 'CONTROLLER_LINEAR_MOVE':
        # 现场要求：到位后直接像 JAKA App 里一样 jog 下去，不经过 cuRobo。
        progress.begin('DESCEND', 'DIRECT_MOVE_DESCEND', 'execute')
        ik_handle, seed = None, None
        try:
            if pre and pre.get('plan_artifact'):
                from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
                request = load(ROOT / pre['plan_artifact'] / 'planner_request.json', {}) or {}
                if request:
                    ik_handle = RuntimeGoalIK(request['robot_yaml_urdf'], request['T_body_model'],
                                              request['T_link6_tcp'])
                    seed = (telemetry().get('arms') or {}).get('right', {}).get('joints_rad')
        except Exception:                                        # noqa: BLE001
            ik_handle, seed = None, None
        direct = controller_body_move(params, out, (0.0, 0.0, -float(descent)),
                                      progress=progress, label='descend',
                                      ik=ik_handle, seed_joints=seed)
        save(out / 'plans.json', dict(
            preplace=None if pre is None else {k: v for k, v in pre.items()
                                               if k != 'attempts'},
            descend=dict(mode='CONTROLLER_LINEAR_MOVE', direct_move=direct),
            order='preplace dispatched; descent executed as a controller-native MoveL '
                  '(no cuRobo planning, no scene voxel gate)'))
        before = tcp_of(telemetry())[:3, 3]
        delta = before - arrived
        save(out / 'descent-check.json', dict(before_m=arrived.tolist(), after_m=before.tolist(),
                                              delta_m=delta.tolist(), target_m=place,
                                              mode='CONTROLLER_LINEAR_MOVE',
                                              direct_move=direct))
        if (abs(delta[0]) > platform['descent_tolerance_m']
                or abs(delta[1]) > platform['descent_tolerance_m']
                or abs(delta[2] + descent) > platform['descent_tolerance_m']):
            raise SystemExit('descent is not a %.0f mm BODY -Z move: %s'
                             % (descent * 1000, np.round(delta, 4).tolist()))
    else:
        descending = plan_descend(out)
        save(out / 'plans.json', dict(
            preplace=None if pre is None else {k: v for k, v in pre.items()
                                               if k != 'attempts'},
            descend={k: v for k, v in descending.items() if k != 'attempts'},
            order='preplace dispatched first; descend re-scanned and planned at the preplace pose'))
        descending = execute_leg(plan_descend, descending, 'descend', 'DESCEND', out, progress)
        before = tcp_of(telemetry())[:3, 3]
        delta = before - arrived
        save(out / 'descent-check.json', dict(before_m=arrived.tolist(), after_m=before.tolist(),
                                              delta_m=delta.tolist(), target_m=place))
        if (abs(delta[0]) > platform['descent_tolerance_m']
                or abs(delta[1]) > platform['descent_tolerance_m']
                or abs(delta[2] + descent) > platform['descent_tolerance_m']):
            raise SystemExit('descent is not a %.0f mm BODY -Z move: %s'
                             % (descent * 1000, np.round(delta, 4).tolist()))
    if stop_after == 'descend':
        save(out / 'stop-after-descend.json', dict(
            state='AT_DESCENT', tcp_body_m=before.tolist(), target_body_m=place,
            error_mm=round(float(np.linalg.norm(before - np.asarray(place))) * 1000, 2),
            note='只派发了预放置+下降两段；夹爪未释放'))
        print(json.dumps(dict(stage='place', state='AT_DESCENT',
                              tcp_mm=mm(before)), ensure_ascii=False), flush=True)
        return dict(state='AT_DESCENT', tcp_body_m=before.tolist(),
                    descent_delta_m=delta.tolist())

    progress.begin('RELEASE', 'RELEASE_GRIPPER', 'prep')
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

    # 与 demo-3 一致：松爪后先从槽里沿 BODY x− 退出（demo-3 实测 55 mm），
    # 再从「已脱离接触」的位姿规划回 center。否则从槽内斜着抽出会卡住结构，
    # 2026-11-09 实测控制器报 983092 碰撞并锁存保护停。
    retreat_cfg = stage.get('post_release_retreat') or {}
    retreat = None
    if retreat_cfg.get('enabled') and float(retreat_cfg.get('distance_m') or 0.0) > 0.0:
        axis = [float(v) for v in retreat_cfg.get('axis_body') or [-1.0, 0.0, 0.0]]
        distance = float(retreat_cfg['distance_m'])
        vector = [axis[0] * distance, axis[1] * distance, axis[2] * distance]
        progress.begin('RETREAT', 'DIRECT_MOVE_RETREAT', 'execute')
        retreat = controller_body_move(
            params, out, vector,
            speed_mm_s=float(retreat_cfg.get('speed_mm_s') or 10.0),
            progress=progress, label='retreat')
        after_retreat = tcp_of(telemetry())[:3, 3]
        save(out / 'retreat-check.json', dict(before_m=before.tolist(),
                                              after_m=after_retreat.tolist(),
                                              delta_m=(after_retreat - before).tolist(),
                                              requested_body_vector_m=vector,
                                              direct_move=retreat))
        print(json.dumps(dict(stage='place', state='RETREATED',
                              delta_mm=[round(float(v) * 1000, 1)
                                        for v in (after_retreat - before)],
                              note='松爪后沿 BODY x− 退出 %.0f mm（与 demo-3 相同）'
                                   % (distance * 1000)), ensure_ascii=False), flush=True)

    print(json.dumps(dict(stage='place', state='PLACED_AND_RELEASED',
                          tcp=[round(v, 5) for v in before]), ensure_ascii=False))
    return dict(state='PLACED_AND_RELEASED', tcp_body_m=before.tolist(),
                release_readback_raw=raw,
                retreat=retreat)


# -------------------------------------------------------------------- stage 2
def stage_center(params, out, execute, progress=None):
    from ares_r.manipulation.task_contract import center_goal
    stage = params['stages']['return_center']
    platform = params['platform']
    out.mkdir(parents=True, exist_ok=False)
    deadline = float(load(ROOT / 'config/system.json')['curobo']['timeout_s'])
    goal = center_goal(ROOT)
    state = telemetry()
    controller_guard(state)
    tool_guard(state, params['required_tool_id'])
    progress = progress or Progress()
    # 站点软限位快速失败：原生执行包要求每个采样落在 [lower+soft, upper-soft]，
    # 起点已越界时任何轨迹都会被打包拒绝（2026-11-09 实测 3 次尝试白等 170 s）。
    start_limit = soft_limit_report(((state.get('arms') or {}).get('right') or {}
                                     ).get('joints_rad'))
    save(out / 'start-soft-limit.json', start_limit)
    if not start_limit['passed']:
        raise SystemExit('START_POSE_OUTSIDE_SOFT_LIMIT: %s —— 关节已在站点软限位外'
                         '（hard 限位再内缩 %s°），归 center 的任何轨迹都会被原生打包'
                         '拒绝。先手动把该关节挪回 [%s, %s] 区间再跑。'
                         % (json.dumps(start_limit['violations'], ensure_ascii=False),
                            start_limit['soft_margin_deg'],
                            start_limit['violations'][0]['allowed_low_deg'],
                            start_limit['violations'][0]['allowed_high_deg']))

    def plan_center(directory=None):
        target = Path(directory) if directory else out
        progress.begin('CENTER', 'PLAN_CENTER', 'plan')
        payload = dict(arm='right', position_m=[float(v) for v in goal['position_m']],
                       orientation='TERMINAL_EXPLICIT',
                       explicit_rotation=goal['explicit_rotation'],
                       speed_profile=platform['motion_speed_profile'],
                       scene_policy=platform['scene_policy_center'],
                       environment_avoidance=platform['environment_avoidance'],
                       source=DEMO_ID.upper(), request_label='RETURN_CENTER')
        rec = plan_leg(payload, 'center', target, deadline, tolerance_deg=90.0, rounds=1,
                       progress=progress)
        rec['authorization'] = MOTION_API_AUTHORIZATION
        save(target / 'center-goal.json', goal)
        return rec

    record = plan_center(out)
    if not execute:
        print(json.dumps(dict(stage='center', state='PLANNED_ONLY',
                              plan_id=record['plan_id']), ensure_ascii=False))
        return dict(state='PLANNED_ONLY')
    record = execute_leg(plan_center, record, 'center', 'CENTER', out, progress)
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
    global DEMO_ID, EVIDENCE_ROOT, LAST_RUN
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--prepare', action='store_true', help='只做检测与规划（默认）')
    group.add_argument('--execute', action='store_true', help='规划后当次派发')
    group.add_argument('--stop', action='store_true', help='请求停止当前物理任务')
    parser.add_argument('--output', type=Path, default=None, help='本次运行的证据根目录')
    parser.add_argument('--stage', choices=('all', 'place', 'place_center', 'center'),
                        default='all',
                        help='all/place_center = 放置（含下降60mm）+回center；本 Demo 不动底盘')
    parser.add_argument('--preplace-offset', type=float, nargs=3, default=None,
                        help='覆盖预放置点偏移（BODY 相对检测点，米）')
    parser.add_argument('--descent-m', type=float, default=None)
    parser.add_argument('--descent-mode', choices=('CONTROLLER_LINEAR_MOVE', 'CUROBO_PLAN'),
                        default=None,
                        help='下降方式：CONTROLLER_LINEAR_MOVE=控制器原生 MoveL（等同 JAKA App '
                             '里 jog 下去，不经过 cuRobo）；CUROBO_PLAN=规划式下降')
    parser.add_argument('--yaw-deg', type=float, default=None,
                        help='覆盖放置目标偏航（BODY 度）')
    parser.add_argument('--stop-after', choices=('preplace', 'descend', 'release'),
                        default='release',
                        help='放置段执行到哪一步就停（preplace=只到预放置点，便于现场确认）；'
                             '直放模式（plan_direct_to_place）没有预放置点/下降段，'
                             '非 release 值均停在唯一的放置腿到位后（AT_PLACE）')
    parser.add_argument('--level-tolerance', type=float, default=None,
                        help='覆盖水平门限（度，默认取 platform.level_tolerance_deg=5.0）；'
                             '仅在确认可接受倾斜时显式放宽')
    parser.add_argument('--demo-id', default=None,
                        help='切换 Demo 身份（默认 %s）；决定 parameters.json 默认路径与'
                             '证据目录 worklog/evidence/demo-runs/<demo-id>/'
                             '（demo-6 = right_arm_liaopan_dmp_place_v1）' % DEMO_ID)
    parser.add_argument('--parameters', type=Path, default=None,
                        help='参数文件；默认 demos/<--demo-id>/parameters.json')
    parser.add_argument('--authorization', default=None,
                        help="本 Demo 的操作授权短语（parameters.json:authorization_phrase）")
    parser.add_argument('--onsite-observer-confirmed', action='store_true')
    args = parser.parse_args()

    if args.stop:
        emit(stop=api('/api/operations/stop', {}, timeout=30))
        return 0

    # Demo 身份可以在命令行切换（demo-5 / demo-6 共用本脚本）。
    # 先按候选身份解析参数、校验 `parameters.demo_id`，通过后才真正切换模块身份，
    # 这样「身份与参数文件不匹配」被拒时不会留下半切换的全局状态。
    demo_id = str(args.demo_id or DEMO_ID)
    parameters = Path(args.parameters) if args.parameters else (
        ROOT / 'demos' / demo_id / 'parameters.json')

    params = load(parameters)
    if params.get('demo_id') != demo_id:
        raise SystemExit('parameters demo_id mismatch: %r (expected %r for %s)'
                         % (params.get('demo_id'), demo_id, parameters))
    if demo_id != DEMO_ID:
        DEMO_ID = demo_id
        EVIDENCE_ROOT = ROOT / 'worklog/evidence/demo-runs' / DEMO_ID
        LAST_RUN = EVIDENCE_ROOT / 'last-run.json'
    phrase = str(params.get('authorization_phrase') or '')
    execute = bool(args.execute)
    if execute:
        if not args.onsite_observer_confirmed:
            raise SystemExit('实机执行需要 --onsite-observer-confirmed（现场确认）')
        if args.authorization != phrase:
            raise SystemExit('授权短语必须是 %r' % phrase)

    out = Path(args.output) if args.output else (EVIDENCE_ROOT / ('run_%d' % time.time_ns()))
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    marker = out / 'demo-run.json'
    overrides = dict(preplace_offset=args.preplace_offset, descent_m=args.descent_m,
                     yaw_deg=args.yaw_deg, level_tolerance_deg=args.level_tolerance,
                     descent_mode=args.descent_mode)
    if args.descent_mode:
        params['stages']['dmp_place']['descent_mode'] = args.descent_mode
    if args.level_tolerance is not None and not 0.0 < float(args.level_tolerance) <= 12.0:
        raise SystemExit('--level-tolerance 必须在 (0, 12] 度之间')
    if execute:
        if marker.exists():
            raise SystemExit('该输出目录已派发过，拒绝重复执行：%s' % marker)
        status = api('/api/operations/run-status', timeout=30)
        if status.get('state') == 'RUNNING':
            raise SystemExit('another physical task running: %s' % status)
        save(marker, dict(armed_at_unix=time.time(), demo_id=DEMO_ID, stage=args.stage,
                          parameters=str(parameters), overrides=overrides))
    else:
        save(out / 'dry-run.json', dict(at_unix=time.time(), demo_id=DEMO_ID,
                                        stage=args.stage, overrides=overrides))

    # 开工自检：站点速度上限（必须是 0.2 rad/s）+ 控制器 TCP（必须是 tool_id 3）
    progress = Progress()
    progress.begin('PREFLIGHT', 'PREFLIGHT', 'prep')
    ceiling = site_ceiling(params['required_site_max_velocity_rad_s'])
    save(out / 'site-ceiling.json', ceiling)
    print(json.dumps(dict(preflight='SITE_CEILING', ok=True,
                          effective_ceiling_rad_s=ceiling['effective_ceiling_rad_s'],
                          required_rad_s=ceiling['required_rad_s']),
                     ensure_ascii=False), flush=True)
    state = telemetry()
    save(out / 'telemetry-before.json', state)
    if state.get('errors') or not (state.get('arms') or {}).get('right'):
        raise SystemExit('telemetry has no trusted right-arm state: %s' % state.get('errors'))
    controller_guard(state)
    binding = tool_guard(state, params['required_tool_id'])
    save(out / 'tool-binding.json', binding)
    print(json.dumps(dict(preflight='CONTROLLER_TOOL', ok=True, tool_id=binding['tool_id'],
                          required_tool_id=binding['required_tool_id']),
                     ensure_ascii=False), flush=True)
    # 上一轮 FAULT 可能把 servo 模式留着，原生执行器会以
    # `not idle / pre-existing servo` 直接拒绝（2026-11-09 实测）。幂等关一次。
    if execute:
        clear_residual_servo(out)

    results = {}
    if args.stage in ('all', 'place', 'place_center'):
        results['place'] = stage_place(params, out / '01-dmp-place', execute,
                                       args.preplace_offset, args.descent_m, args.yaw_deg,
                                       args.stop_after, args.level_tolerance, progress)
    if args.stage in ('all', 'center', 'place_center'):
        results['center'] = stage_center(params, out / '02-return-center', execute, progress)
    save(out / 'summary.json', results)
    progress.finish()

    states = {k: v.get('state') for k, v in results.items()}
    key = tuple(k for k in ('place', 'center') if k in results)
    place_expected = {'preplace': 'AT_PREPLACE', 'descend': 'AT_DESCENT',
                      'release': 'PLACED_AND_RELEASED'}[args.stop_after]
    if bool((params.get('stages') or {}).get('dmp_place', {}).get('plan_direct_to_place')) \
            and args.stop_after in ('preplace', 'descend'):
        # 直放模式没有预放置点/下降段：任何「分段停」都停在唯一的放置腿到位处。
        place_expected = 'AT_PLACE'
    expected = dict(place=place_expected, center='AT_CENTER')
    label = {('place', 'center'): 'PLACE_CENTER_COMPLETE',
             ('place',): place_expected,
             ('center',): 'AT_CENTER'}
    if not execute:
        outcome = 'PLANNED_ONLY'
    elif key in label and all(states.get(k) == expected[k] for k in key):
        outcome = label[key] if (args.stop_after == 'release' or len(key) == 1) else 'INCOMPLETE'
    else:
        outcome = 'INCOMPLETE'
    result = dict(demo_id=DEMO_ID, output=str(out), stage=args.stage, execute=execute,
                  parameters=str(parameters), overrides=overrides,
                  stop_after=args.stop_after, timings=progress.timings(),
                  base='STATIONARY_AT_DMP_STATION', states=states,
                  result=outcome, physical_motion=execute, at_unix=time.time())
    save(out / 'result.json', result)
    save(LAST_RUN, dict(result, run_dir=str(out)))
    emit(**result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
