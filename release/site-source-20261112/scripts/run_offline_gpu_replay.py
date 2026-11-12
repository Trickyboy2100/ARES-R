#!/usr/bin/env python3
"""Pinned real CUDA planning on historical scenes; never physical commissioning.

Run ONLY via offline_sandbox.sh --gpu. All outputs stay in ignored runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.persistent_planner_service import PlannerSupervisor


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--warm-runs',type=int,default=10)
    parser.add_argument('--synthetic-smoke',action='store_true')
    args=parser.parse_args()
    if os.environ.get('ARES_R_OFFLINE_REPLAY')!='1':raise RuntimeError('offline_sandbox.sh required')
    args.output.mkdir(parents=True,exist_ok=False)
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA required, no mock fallback')
    if torch.cuda.device_count()!=1 or '3080' not in torch.cuda.get_device_name(0):
        raise RuntimeError('this acceptance is restricted to one RTX3080')
    root=ROOT/'worklog/runtime/preview-model'
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['commissioned'] is not False:raise RuntimeError('preview provenance required')
    fast=json.loads((ROOT/'config/planner_latency_profiles.json').read_text())['fast']
    supervisor=PlannerSupervisor();records=[];failed=False
    try:
        for mode in (('CLEAR',) if args.synthetic_smoke else ('CLEAR','AVOID','BLOCK')):
            source=ROOT/('worklog/evidence/2026-09-21-p3-production-demo/%s_final/scene/planner_request.json'%mode.lower())
            request=json.loads(source.read_text())
            request.update(robot_yaml=str(root/'robot.yml'),robot_yaml_urdf=str(root/'robot.urdf'),
                benchmark_runs=1,warmup_policy='NONE',
                solver_policy={'mode':'FAST_SINGLE_PASS_V1','initial_iters':fast['initial_iters'],
                    'max_goal_candidates':1,'distance_backend':'NATIVE_CPU_V1'},
                replay_provenance={'kind':'PROXY_REPLAY','source_date':'2026-09-21',
                    'source_request_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                    'model_commissioned':False,'oct16_reproduced':False})
            request['planning_parameters'].update({key:fast[key] for key in ('num_ik_seeds','num_trajopt_seeds','use_cuda_graph')})
            if args.synthetic_smoke:
                # Separate smoke fixture: never relabel modified history as CLEAR replay.
                request['compiled_scene']['cuboids']={'synthetic_far_box':{
                    'dims':[.1,.1,.1],'pose':[10,10,10,1,0,0,0]}}
                request['compiled_scene']['scene_snapshot_id']='SYNTHETIC_GPU_SMOKE'
                request['compiled_scene']['digest']=hashlib.sha256(json.dumps(request['compiled_scene'],sort_keys=True).encode()).hexdigest()
                request['scene_snapshot_id']=request['compiled_scene']['scene_snapshot_id']
                request['scene_digest']=request['compiled_scene']['digest']
                request['goal_rad']=list(request['start_rad']);request['goal_rad'][5]+=.05
                request['motion_constraints']={'central_exclusion':False}
                request['replay_provenance']['kind']='SYNTHETIC_GPU_SMOKE'
            count=args.warm_runs+1 if mode=='CLEAR' else 1
            for i in range(count):
                label='%s_%02d'%(mode,i);path=args.output/(label+'.request.json')
                path.write_text(json.dumps(request,indent=2)+'\n')
                start=time.monotonic()
                # Cold initialization/compilation is explicitly separated from FAST deadline.
                budget=240 if i==0 else 4
                job={'job_id':uuid.uuid4().hex,'request':str(path),
                    'output':str(args.output/(label+'.planning.json')),
                    'log':str(args.output/(label+'.log')),'deadline_monotonic':start+budget}
                response=supervisor.plan(job)
                record={'label':label,'budget_s':budget,'wall_s':time.monotonic()-start,
                        'response':response,'supervisor':supervisor.status()}
                if response['ok']:
                    result=json.loads(Path(job['output']).read_text())
                    record.update(observed=result['observed_result'],expectation_met=result['expectation_met'],
                        effective_solver_config=result['effective_solver_config'],
                        gpu_memory_bytes=result['gpu_memory_bytes'],timing_s=result['timing_s'],
                        independent_dense_validation=result['independent_dense_validation'])
                if not record.get('expectation_met',False):failed=True
                records.append(record)
                (args.output/'summary.json').write_text(json.dumps({
                    'kind':'SYNTHETIC_GPU_SMOKE' if args.synthetic_smoke else 'PROXY_REPLAY','oct16_reproduced':False,'physical_execution':False,
                    'gpu':torch.cuda.get_device_name(0),'total_bytes':torch.cuda.get_device_properties(0).total_memory,
                    'torch':torch.__version__,'cuda':torch.version.cuda,'records':records},indent=2)+'\n')
                print(json.dumps({'label':label,'response':response,'wall_s':record['wall_s']}),flush=True)
                if not response['ok']:break
    finally:supervisor.reap()
    if failed:raise SystemExit(2)


if __name__=='__main__':main()
