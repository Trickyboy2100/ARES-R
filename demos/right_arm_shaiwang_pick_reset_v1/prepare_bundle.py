#!/usr/bin/env python3
"""Task-local preparation derived from the branch's proven pipeline.

Uses ID6, read-only inherited offsets and scoped task policy. Kinematics,
planning, geometry validation and packaging reuse existing shared services.
No physical motion dispatch exists here.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CAPTURE = HERE / 'capture_epoch.py'

parser = argparse.ArgumentParser()
parser.add_argument('--output-root', type=Path, required=True)
parser.add_argument('--source-epoch', type=Path)
args = parser.parse_args()
O = args.output_root
E = args.source_epoch or O / 'epoch'
PY = str(R / '.venv/bin/python')
CAM = '/home/yikun/ARES-R/vendor/venv311/bin/python3.11'
os.environ.update(ARES_R_BACKEND_URL='http://127.0.0.1:8776',
                  ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',
                  ARES_R_PLANNER_SOCKET=str(R / 'worklog/runtime/rc1-webui/planner.sock'))


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


rows = []
lock = threading.Lock()
started = time.monotonic()


def stage(name, call):
    at = time.monotonic()
    row = dict(stage=name, start_s=at - started)
    try:
        value = call()
        row['state'] = 'PASS'
        return value
    except BaseException as exc:
        row.update(state='FAIL', error=str(exc))
        raise
    finally:
        row['wall_s'] = time.monotonic() - at
        with lock:
            rows.append(row)
            save(O / 'timings.json', dict(physical_motion=False, elapsed_s=time.monotonic() - started,
                                          stages=rows))


def command(cmd, log):
    with (O / log).open('x') as out:
        result = subprocess.run(list(map(str, cmd)), cwd=R,
                                env=dict(os.environ, PYTHONPATH=str(R / 'src')),
                                stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('command failed: ' + str(O / log))


def init():
    from ares_r.motion.planner_service_client import plan
    req = load(R / 'worklog/evidence/20261022-pick-reset-timing/forward60/benchmark-request.json')
    req['initialize_only'] = True
    req['cuboid_capacity_floor'] = 768
    save(O / 'initialize.request.json', req)
    plan(PY, R, O / 'initialize.request.json', O / 'initialize.result.json', O / 'initialize.log', 120,
         autostart=False)
    proof = load(O / 'initialize.result.json')
    if proof['observed_result'] != 'INITIALIZED_NOT_PLANNED' or proof['solve_calls'] != 0:
        raise RuntimeError('initialization unexpectedly solved')


PARAMS = json.loads((HERE / 'params.json').read_text())
# 操作员授权的水平门阈值：通过环境变量传给本进程与全部子进程（tcp_orientation 读取）。
os.environ['ARES_R_LEVEL_TOLERANCE_DEG'] = str(PARAMS.get('level_gate_tolerance_deg', 3.0))
os.environ['ARES_R_ACTIVE_MANIPULATION_TASK'] = PARAMS['demo_id']


def effective_demo_inputs():
    """返回（补偿, 任务 TCP 偏移）。params.json 里的 *_override 为 null 时沿用
    demos/right_arm_grasp_place_roundtrip_v1/parameters.json（已验收值）。"""
    p = load(R / 'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
    comp = dict(p.get('demo_tcp_orientation_compensation') or {})
    override = PARAMS.get('demo_tcp_orientation_compensation_override')
    if override:
        comp.update(override)
    offset = PARAMS.get('task_tcp_offset_m_rad_override')
    if offset is None:
        offset = p.get('task_tcp_offset_m_rad', [0] * 6)
    return comp, offset


def prepare():
    p = load(R / 'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
    comp, offset = effective_demo_inputs()
    command([PY, 'scripts/prepare_authorized_first_pick.py', '--epoch', E,
             '--template-plan', p['template_plan'], '--output', O / 'pregrasp',
             '--early-contact-lift-precheck', '--contact-observed-narrowphase',
             '--contact-measured-protrusions',
             '--task-tcp-offset-m-rad', json.dumps(offset),
             '--demo-tcp-orientation-compensation',
             json.dumps(comp)], 'prepare.log')
    r = load(O / 'pregrasp/planner_request.json')
    ref = load(O / 'initialize.request.json')
    r.update(planning_only=True, execution_allowed=False, warmup_policy='NONE', benchmark_runs=1,
             independent_distance_backend='NATIVE_CPU_V1', cuboid_capacity_floor=768)
    r['solver_policy'] = ref['solver_policy']
    r['planning_parameters'].update({k: ref['planning_parameters'][k]
                                     for k in ('num_ik_seeds', 'num_trajopt_seeds', 'use_cuda_graph')})
    r['planner_clearance_policy'] = ref['planner_clearance_policy']
    r['planning_parameters']['optimizer_collision_activation_distance'] = \
        ref['planning_parameters']['optimizer_collision_activation_distance']
    save(O / 'pregrasp/planner_request.json', r)


def solve():
    from ares_r.motion.planner_service_client import plan
    plan(PY, R, O / 'pregrasp/planner_request.json', O / 'pregrasp/planning.json',
         O / 'pregrasp/planning.log', 120, autostart=False)
    if load(O / 'pregrasp/planning.json')['observed_result'] != 'SUCCESS':
        raise RuntimeError('pregrasp planning not successful')


def lift():
    from ares_r.manipulation.continuous_demo_lift import build_path, validate_path
    from ares_r.motion.independent_path_validation import validate_dense_world
    r = load(O / 'pregrasp/planner_request.json')
    package = load(O / 'package/first_pick_execution_package.json')
    points = build_path(package, r, .23)
    save(O / 'lift230-path.json', points)
    from ares_r.manipulation.pick_reset_pipeline import bind_geometry_proof
    proof = bind_geometry_proof(validate_path(points, r, package, contact_escape=None), points, r, package)
    save(O / 'lift230-validation.json', proof)
    paths = dict(pregrasp=package['trajectories']['pregrasp'],
                 contact=package['trajectories']['contact'],
                 lift230=points, lower230=list(reversed(points)),
                 retreat=list(reversed(package['trajectories']['contact'])),
                 center=list(reversed(package['trajectories']['pregrasp'])))
    save(O / 'pick-reset-paths.json', paths)
    empty = validate_dense_world(paths['center'], r, subdivisions=4)
    save(O / 'reset-center-validation.json', empty)
    if not empty['collision_free']:
        raise RuntimeError('reset center collision')
    save(O / 'preparation-ready.json', dict(physical_motion=False, planning_only=True,
                                            execution_allowed=False, geometry_prepared=True,
                                            native_packaging_complete=False,
                                            scene_snapshot_id=r['scene_snapshot_id'],
                                            epic_command=json.loads((HERE / 'params.json').read_text())['epic_command']))


def verify_compensation():
    """-10° TCP_LOCAL_Z 末端偏置是现场已验证的关键修正；prepare_authorized_first_pick.py
    的该参数默认是 '{}'，不显式传就会静默丢失（2026-10-28 旧实现即因此空合）。
    若 params.json 给了 override，则按 override 后的有效值校。"""
    r = load(O / 'pregrasp/planner_request.json')
    comp = r.get('demo_tcp_orientation_compensation') or {}
    expected, _ = effective_demo_inputs()
    want_angle = float(expected.get('angle_deg', -10.0))
    if comp.get('enabled') is not True or comp.get('axis') != 'TCP_LOCAL_Z' \
            or abs(float(comp.get('angle_deg', 0.0)) - want_angle) > 1e-9:
        raise RuntimeError('TCP 末端偏置缺失/不符（期望 %.1f° TCP_LOCAL_Z）：%s'
                           % (want_angle, json.dumps(comp, ensure_ascii=False)))
    save(O / 'compensation-proof.json', dict(planned=comp, expected=expected))


def main():
    os.chdir(R)
    O.mkdir(parents=True, exist_ok=False)
    try:
        stage('GRIPPER_RUNTIME_PREFLIGHT',
              lambda: command([PY, 'scripts/gripper_direct_once.py', 'status'], 'gripper-runtime.json'))
        if load(O / 'gripper-runtime.json')['fault_code']:
            raise RuntimeError('gripper hardware fault; do not scan or plan')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            camera = pool.submit(
                stage, 'OBSERVATION_GRASP_CONFIG6' if args.source_epoch is None else 'REUSE_FROZEN_EPOCH',
                lambda: command([CAM, str(CAPTURE), '--profile', 'right_pick', '--observed-obb',
                                 '--output', E], 'capture.log')
                if args.source_epoch is None else load(E / 'manipulation_observation.json'))
            planner = pool.submit(stage, 'PLANNER_INITIALIZE_NO_SOLVE', init)
            camera.result()
            stage('CONTACT_GEOMETRY_IK', prepare)
            stage('TCP_ORIENTATION_COMPENSATION_MINUS10', verify_compensation)
            planner.result()
        stage('CUROBO_PREGRASP', solve)
        stage('BUILD_PICK_PACKAGE',
              lambda: command([PY, 'scripts/build_first_pick_execution_package.py', '--plan', O / 'pregrasp',
                               '--epoch', E, '--payload-policy',
                               'DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2', '--output', O / 'package'],
                              'package.log'))
        stage('LIFT230_AND_REVERSE_GEOMETRY', lift)
    except BaseException as exc:
        save(O / 'failure.json', dict(error=str(exc), physical_motion=False,
                                      elapsed_s=time.monotonic() - started))
        raise
    finally:
        print(json.dumps(dict(output=str(O), elapsed_s=time.monotonic() - started, stages=rows)), flush=True)


if __name__ == '__main__':
    main()
