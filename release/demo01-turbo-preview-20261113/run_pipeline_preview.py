#!/usr/bin/env python3
"""Replay saved scans while preparing one GPU runtime in parallel. No hardware I/O."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time

from run_preview import HERE, save
from preparation_runtime import PreparationRuntime, Stage, run_owned_process


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mode', choices=('serial', 'parallel'), required=True)
    a = p.parse_args()
    root, out = a.repository.resolve(), a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.chdir(root)
    sys.path.insert(0, str(root / 'src'))
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name] = '2'
    parameters = json.loads((HERE / 'parameters.json').read_text())
    config = json.loads((root / 'config/system.json').read_text())
    scenes = root / 'worklog/evidence/scene-aware-motion'
    requests = {}
    for stage, plan_id in parameters['source_plans'].items():
        request = json.loads((scenes / plan_id / 'planner_request.json').read_text())
        request.update(planning_only=True, execution_allowed=False,
            physical_state='FROZEN_PIPELINE_REPLAY', benchmark_runs=1, warmup_policy='NONE',
            latency_contract=None, independent_distance_backend='NATIVE_CPU_V1')
        request['planning_parameters'].update(num_ik_seeds=4, num_trajopt_seeds=2, use_cuda_graph=True)
        request['solver_policy'] = dict(mode='FAST_SINGLE_PASS_V1',initial_iters=50,
                                        max_goal_candidates=1,distance_backend='NATIVE_CPU_V1')
        requests[stage] = request
    # Resolve frozen scene folders before the measured serial/parallel section.
    source_folders = {}
    for file in scenes.glob('scene_*/scene/compiled_scene.json'):
        value = json.loads(file.read_text())
        for stage, request in requests.items():
            if value['scene_snapshot_id'] == request['scene_snapshot_id']:
                source_folders[stage] = file.parent.parent
    if set(source_folders) != set(requests):
        raise ValueError('FROZEN_SOURCE_SCENE_MISSING')
    started = time.perf_counter()
    def gpu_solve(request, folder):
        folder.mkdir()
        path, result = folder / 'request.json', folder / 'planning.json'
        save(path, request)
        from ares_r.motion.production_scene_worker import main as solve
        sys.argv = ['pipeline-worker', str(path), str(result)]
        solve(progress=lambda event: runtime.check_cancelled())
        value = json.loads(result.read_text())
        if value.get('observed_result') != 'SUCCESS':
            raise RuntimeError('FROZEN_GPU_PLAN_FAILED')
        return value
    def warm():
        import torch
        torch.cuda.set_per_process_memory_fraction(parameters['memory_fraction'])
        # Startup-only graph/optimizer preparation, no execution candidate released.
        result = gpu_solve(copy.deepcopy(requests['center']), out / 'warmup')
        return dict(runtime_reused=result['timing_s']['persistent_runtime_reused'])
    def prepare():
        from ares_r.operations import planning_world
        prepared = {}
        for stage, source in source_folders.items():
            destination = out / (stage + '-reconstructed')
            command = [config['epic_pointcloud']['body_cloud_viewer_python'],
                str(root / 'scripts/p32_scan_scene.py'), '--mode', 'LIVE',
                '--output', str(destination), '--open3d-python',
                config['epic_pointcloud']['body_cloud_viewer_python'],
                '--active', 'right', '--reuse-capture', str(source)]
            with (out / (stage + '-scene.log')).open('w') as stream:
                run_owned_process(command,cwd=root,env=dict(os.environ,PYTHONPATH=str(root/'src')),
                    stream=stream,cancelled=runtime.check_cancelled,timeout_s=120)
            # This is a saved-scan replay. No camera or controller is contacted.
            report = json.loads((destination/'scene/scene_report.json').read_text())
            compiled = json.loads((destination/'scene/compiled_scene.json').read_text())
            compiled = planning_world(compiled, 'ON')
            request = copy.deepcopy(requests[stage])
            request.update(compiled_scene=compiled, scene_snapshot_id=compiled['scene_snapshot_id'],
                           scene_digest=compiled['digest'])
            if report['geometry_revision'] != request['geometry_revision']:
                raise ValueError('FROZEN_GEOMETRY_CHANGED')
            prepared[stage] = request
        return prepared
    runtime = PreparationRuntime()
    revisions = dict(parameters=parameters['revision'],
        center_scene=requests['center']['scene_snapshot_id'],
        restore_scene=requests['restore']['scene_snapshot_id'])
    def package(stage, dependencies, cancelled):
        cancelled()
        value = dependencies['PLAN_'+stage].value
        request = dependencies['CPU_SCENE_REBUILD'].value[stage]
        from ares_r.motion.native_execution_package import package_native_preview
        original = scenes/parameters['source_plans'][stage]
        audit = json.loads((original/'native_package/native_audit.json').read_text())
        _, native = package_native_preview(value['trajectory_points_rad'],
            value['smoothness']['sample_period_s'],json.loads((root/'config/jaka_mini2_motion.site.json').read_text()),
            tool_id=audit['controller_tool_id'],
            controller_tool_pose_mm_rad=request['controller_tool_pose_mm_rad'],
            captured_at_unix=time.time(),speed_ceiling_rad_s=.2,accel_ceiling_rad_s2=.2,
            tracking_stop_threshold_deg=1.5,max_excursion_rad=3.839724354387525,
            retiming_policy='ARC_LENGTH_EXACT_V1')
        save(out/(stage+'-native-audit.json'),native)
        return dict(stage=stage,timing_s=value['timing_s'],planned_motion_s=native['duration_s'])
    stages = [
        Stage('GPU_STARTUP','gpu',('GPU',),(),lambda d,c:warm()),
        Stage('CPU_SCENE_REBUILD','cpu',('SCENE_REBUILD',),
              ('GPU_STARTUP',) if a.mode=='serial' else (),lambda d,c:prepare(),'OBSERVATION_BOUND'),
        Stage('PLAN_center','gpu',('GPU',),('GPU_STARTUP','CPU_SCENE_REBUILD'),
              lambda d,c:gpu_solve(d['CPU_SCENE_REBUILD'].value['center'],out/'center-plan'),'OBSERVATION_BOUND'),
        Stage('PACKAGE_center','cpu',('NATIVE_PACKAGING',),('PLAN_center','CPU_SCENE_REBUILD'),
              lambda d,c:package('center',d,c),'OBSERVATION_BOUND'),
        Stage('PLAN_restore','gpu',('GPU',),
              ('PLAN_center','CPU_SCENE_REBUILD','PACKAGE_center') if a.mode=='serial'
              else ('PLAN_center','CPU_SCENE_REBUILD'),
              lambda d,c:gpu_solve(d['CPU_SCENE_REBUILD'].value['restore'],out/'restore-plan'),'OBSERVATION_BOUND'),
        Stage('PACKAGE_restore','cpu',('NATIVE_PACKAGING',),('PLAN_restore','CPU_SCENE_REBUILD'),
              lambda d,c:package('restore',d,c),'OBSERVATION_BOUND'),
    ]
    try:
        artifacts = runtime.run(stages,revisions)
    except BaseException as error:
        save(out/'result.json',dict(success=False,error=str(error),events=runtime.events,
                                   physical_motion=False,execution_allowed=False))
        raise
    ready_s = max(e['end_s'] for e in runtime.events if e['stage'] in ('GPU_STARTUP','CPU_SCENE_REBUILD'))
    rows = [artifacts['PACKAGE_'+stage].bind(revisions) for stage in ('center','restore')]
    events = sorted(runtime.events,key=lambda event:event['queued_s'])
    result=dict(success=True,demo_id='demo01_turbo_pipeline_preview_v1',mode=a.mode,
        preparation_ready_s=ready_s,total_s=time.perf_counter()-started,
        events=events,rows=rows,
        physical_motion=False,live_scene_validated=False,execution_allowed=False,
        scan_source='SAVED_PIXEL_PRO_FRAMES_WITH_FROZEN_ROBOT_STATE')
    save(out/'result.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
