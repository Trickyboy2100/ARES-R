#!/usr/bin/env python3
"""Bounded, isolated planning-only comparison. Never imports robot adapters.

Uses one private planner/socket per profile and the unchanged frozen scene.
No production parameters are written and no execution package is produced.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time


def call(path, payload, timeout):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout); client.connect(str(path))
        client.sendall((json.dumps(payload)+'\n').encode())
        chunks = []
        while True:
            block = client.recv(65536)
            if not block: break
            chunks.append(block)
    return json.loads(b''.join(chunks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python', default='/home/yikun/ares-r-curobo-venv/bin/python')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--suite', choices=('seeds','cuda','fast','fast2','balanced'), default='seeds')
    parser.add_argument('--block-goal',action='store_true',help='Derived synthetic BLOCK, never production scene')
    args = parser.parse_args()
    if not 1 <= args.runs <= 5: raise ValueError('bounded to 1..5 repeats/profile')
    frozen = args.request.read_bytes(); source = json.loads(frozen)
    if source.get('execution_allowed') is not False or source.get('planning_only') is not True:
        raise ValueError('execution-blocked frozen request required')
    if args.block_goal:
        import numpy as np
        target=source['runtime_motion_goal']['position_m']
        center=(np.linalg.inv(np.asarray(source['T_body_model']))@np.r_[target,1])[:3].tolist()
        world=source['compiled_scene']
        world['cuboids']['benchmark_goal_enclosure']={'pose':center+[1,0,0,0],'dims':[.3,.3,.3]}
        world['scene_snapshot_id']='DERIVED_BENCHMARK_BLOCK_'+hashlib.sha256(frozen).hexdigest()[:16]
        world['digest']=hashlib.sha256(json.dumps(world,sort_keys=True).encode()).hexdigest()
        source.update(mode='BLOCK',scene_snapshot_id=world['scene_snapshot_id'],scene_digest=world['digest'])
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    report = {'execution_allowed': False, 'scope': 'FROZEN_OFFLINE_BENCHMARK_ONLY',
              'request_sha256': hashlib.sha256(frozen).hexdigest(),
              'scene_snapshot_id': source['scene_snapshot_id'], 'profiles': {}}
    profiles = ([('baseline', {}), ('seeds4_4', {'num_trajopt_seeds':4,'num_ik_seeds':4}),
                 ('seeds4_2', {'num_trajopt_seeds':4,'num_ik_seeds':2})]
                if args.suite=='seeds' else
                [('cuda8_8', {'use_cuda_graph':True}),
                 ('cuda4_4', {'num_trajopt_seeds':4,'num_ik_seeds':4,'use_cuda_graph':True})])
    if args.suite in ('fast','fast2','balanced'):
        profiles=[('fast25_4',{'num_trajopt_seeds':4,'num_ik_seeds':4,'use_cuda_graph':True}),
                  ('fast50_4',{'num_trajopt_seeds':4,'num_ik_seeds':4,'use_cuda_graph':True}),
                  ('fast25_2',{'num_trajopt_seeds':2,'num_ik_seeds':4,'use_cuda_graph':True})]
        if args.suite=='fast2':profiles=profiles[-1:]
        if args.suite=='balanced':profiles=[('fast50_2',{'num_trajopt_seeds':2,'num_ik_seeds':4,'use_cuda_graph':True})]
    for name, override in profiles:
        directory = args.output / name; directory.mkdir()
        sock = Path('/tmp/ares_bench_%d.sock' % os.getpid())
        if sock.exists(): raise RuntimeError('private socket already exists')
        rows = []
        with (directory/'service.log').open('x') as log:
            worker = subprocess.Popen([args.python,'-m','ares_r.motion.persistent_planner_service',
                '--socket',str(sock)], cwd=root, env=dict(os.environ,PYTHONPATH=str(root/'src')),
                stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic()+40
                while not sock.exists():
                    if worker.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('private planner startup failed')
                    time.sleep(.1)
                for index in range(args.runs):
                    request = copy.deepcopy(source)
                    request['planning_parameters'].update(override)
                    if args.suite in ('fast','fast2','balanced'):
                        request['solver_policy']={'mode':'FAST_SINGLE_PASS_V1',
                            'initial_iters':50 if name.startswith('fast50') else 25,
                            'max_goal_candidates':1,'distance_backend':'NATIVE_CPU_V1'}
                    request.update(benchmark_runs=1, warmup_policy='NONE',
                                   planning_only=True, execution_allowed=False)
                    rp = directory/('%d.request.json'%index); op = directory/('%d.result.json'%index)
                    rp.write_text(json.dumps(request,indent=2))
                    at = time.monotonic()
                    response = call(sock,{'command':'plan','request':str(rp.resolve()),
                        'output':str(op.resolve()),'log':str((directory/('%d.log'%index)).resolve())},180)
                    artifact = json.loads(op.read_text()) if op.exists() else {}
                    row = {'repeat':index,'cold_runtime':index==0,'wall_s':time.monotonic()-at,
                        'worker_response':response,'observed_result':artifact.get('observed_result'),
                        'expectation_met':artifact.get('expectation_met'),
                        'timing_s':artifact.get('timing_s'), 'clearance_m':artifact.get('clearance_m'),
                        'orientation_validation':artifact.get('orientation_validation'),
                        'independent_dense_validation':artifact.get('independent_dense_validation'),
                        'smoothness':artifact.get('smoothness'),
                        'trajectory_sha256':hashlib.sha256(json.dumps(
                            artifact.get('trajectory_points_rad'),sort_keys=True).encode()).hexdigest()}
                    rows.append(row)
                    print(json.dumps({'profile':name,'repeat':index,'wall_s':row['wall_s'],
                                      'observed_result':row['observed_result']}),flush=True)
                warm = [r['wall_s'] for r in rows[1:]]
                report['profiles'][name] = {'parameters_override':override,'runs':rows,
                    'warm_wall_median_s':statistics.median(warm) if warm else None,
                    'all_success':all(r['observed_result']=='SUCCESS' for r in rows)}
                report['profiles'][name]['all_expectations_met']=all(r['expectation_met'] is True for r in rows)
            finally:
                if worker.poll() is None:
                    worker.terminate()
                    try: worker.wait(timeout=10)
                    except subprocess.TimeoutExpired: worker.kill();worker.wait()
                if sock.exists(): sock.unlink()
            (args.output/'report.json').write_text(json.dumps(report,indent=2))


if __name__ == '__main__': main()
