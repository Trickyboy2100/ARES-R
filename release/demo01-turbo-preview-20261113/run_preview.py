#!/usr/bin/env python3
"""Frozen two-stage GPU planning and Native packaging preview."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def worker(specification):
    spec = json.loads(Path(specification).read_text())
    root, output = Path(spec['repository']), Path(spec['output'])
    sys.path.insert(0, str(root / 'src'))
    import torch
    torch.cuda.set_per_process_memory_fraction(spec['parameters']['memory_fraction'])
    from ares_r.motion.production_scene_worker import main as plan
    from ares_r.motion.native_execution_package import package_native_preview
    parameters = spec['parameters']
    site = json.loads((root / 'config/jaka_mini2_motion.site.json').read_text())
    rows = []
    started = time.perf_counter()
    try:
        # Both frozen stages run in one process, exercising runtime reuse.
        for repeat in range(spec['repeats']):
            for stage in ('center', 'restore'):
                source = root / 'worklog/evidence/scene-aware-motion' / parameters['source_plans'][stage]
                raw = (source / 'planner_request.json').read_bytes()
                request = json.loads(raw)
                audit = json.loads((source / 'native_package/native_audit.json').read_text())
                request.update(planning_only=True, execution_allowed=False,
                    physical_state='FROZEN_DEMO01_TURBO_PREVIEW', benchmark_runs=1,
                    warmup_policy='NONE', latency_contract=None,
                    independent_distance_backend=parameters['independent_distance_backend'])
                request['planning_parameters'].update(num_ik_seeds=parameters['num_ik_seeds'],
                    num_trajopt_seeds=parameters['num_trajopt_seeds'],
                    use_cuda_graph=parameters['use_cuda_graph'])
                request['solver_policy'] = dict(mode='FAST_SINGLE_PASS_V1',
                    initial_iters=parameters['initial_iters'], max_goal_candidates=1,
                    distance_backend='NATIVE_CPU_V1')
                folder = output / ('%02d-%s' % (repeat, stage))
                folder.mkdir()
                request_path, result_path = folder / 'request.json', folder / 'planning.json'
                save(request_path, request)
                save(folder / 'source.json', dict(source_request=str(source / 'planner_request.json'),
                    sha256=hashlib.sha256(raw).hexdigest(), scene_snapshot_id=request['scene_snapshot_id'],
                    source_tool_id=audit['controller_tool_id']))
                sys.argv = ['frozen-planner', str(request_path), str(result_path)]
                at = time.perf_counter()
                plan()
                planning_s = time.perf_counter() - at
                result = json.loads(result_path.read_text())
                if result.get('observed_result') != 'SUCCESS':
                    raise RuntimeError('FROZEN_PLANNING_FAILED:' + stage)
                at = time.perf_counter()
                text, native = package_native_preview(result['trajectory_points_rad'],
                    result['smoothness']['sample_period_s'], site,
                    tool_id=audit['controller_tool_id'],
                    controller_tool_pose_mm_rad=request['controller_tool_pose_mm_rad'],
                    captured_at_unix=time.time(),
                    speed_ceiling_rad_s=parameters['max_velocity_rad_s'],
                    accel_ceiling_rad_s2=parameters['max_acceleration_rad_s2'],
                    tracking_stop_threshold_deg=parameters['tracking_stop_deg'],
                    max_excursion_rad=math.radians(parameters['max_excursion_deg']),
                    retiming_policy=parameters['retiming_policy'])
                packaging_s = time.perf_counter() - at
                # Native bytes are hashed for comparison, never written as a dispatch file.
                save(folder / 'native-audit.json', native)
                row = dict(stage=stage, repeat=repeat, planning_s=planning_s,
                    packaging_s=packaging_s, planned_motion_s=native['duration_s'],
                    runtime_reused=result['timing_s']['persistent_runtime_reused'],
                    solve_s=result['timing_s']['planning_samples'],
                    independent_validation_s=result['timing_s']['independent_dense_validation'],
                    native_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    geometry_error_rad=native['max_joint_geometry_error_rad'],
                    scene_snapshot_id=request['scene_snapshot_id'], physical_motion=False)
                rows.append(row)
                save(output / 'progress.json', dict(state='RUNNING', rows=rows))
                print(json.dumps(row), flush=True)
        save(output / 'result.json', dict(success=True, state='FROZEN_PLANNING_PREVIEW_PASS',
            demo_id=parameters['demo_id'], physical_motion=False, execution_allowed=False,
            live_scene_validated=False, elapsed_s=time.perf_counter()-started, rows=rows))
    except BaseException as error:
        save(output / 'result.json', dict(success=False, state='PREVIEW_FAILED',
            error=str(error), physical_motion=False, execution_allowed=False, rows=rows))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--timeout-s', type=float, default=180)
    parser.add_argument('--worker-spec', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_spec:
        worker(args.worker_spec)
        return
    if args.repository is None or args.output is None:
        parser.error('--repository and --output are required')
    if not 1 <= args.repeats <= 10 or not 1 <= args.timeout_s <= 600:
        parser.error('repeats must be 1..10; timeout must be 1..600 seconds')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    parameters = json.loads((HERE / 'parameters.json').read_text())
    assert parameters['planning_only'] is True and parameters['execution_allowed'] is False
    spec = output / 'specification.json'
    save(spec, dict(repository=str(args.repository.resolve()), output=str(output),
                    repeats=args.repeats, parameters=parameters))
    with (output / 'worker.log').open('w') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                  '--worker-spec', str(spec)], stdout=log, stderr=subprocess.STDOUT)
        try:
            code = child.wait(timeout=args.timeout_s)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            save(output / 'result.json', dict(success=False, state='PREVIEW_CANCELLED',
                physical_motion=False, execution_allowed=False))
            raise
    print((output / 'result.json').read_text() if (output / 'result.json').exists()
          else json.dumps(dict(success=False, state='WORKER_EXITED', returncode=code)))
    if code:
        raise SystemExit(code)


if __name__ == '__main__':
    main()
