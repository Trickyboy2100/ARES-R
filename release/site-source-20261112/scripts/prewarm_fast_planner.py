#!/usr/bin/env python3
"""Compile/warm the persistent planner from frozen requests; NEVER execute.

Frozen scenes are initialization inputs only, not a current RobotState/scene
or an execution candidate. No robot adapter or execution packager is imported.
"""
import argparse
import json
from pathlib import Path
import time
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.planner_service_client import plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,action='append',required=True)
    p.add_argument('--python',default='/home/yikun/ares-r-curobo-venv/bin/python')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not 1<=len(a.request)<=4:raise ValueError('1..4 initialization inputs only')
    a.output.mkdir(parents=True,exist_ok=False)
    config=json.loads((ROOT/'config/planner_latency_profiles.json').read_text());fast=config['fast']
    rows=[]
    for index,source in enumerate(a.request):
        request=json.loads(source.read_text())
        if request.get('execution_allowed') is not False or request.get('planning_only') is not True:
            raise ValueError('frozen planning-only request required')
        mode=(request.get('runtime_motion_goal') or {}).get('orientation','FREE')
        request['planning_parameters'].update({k:fast[k] for k in ('num_trajopt_seeds','num_ik_seeds','use_cuda_graph')})
        request.update(solver_policy={'mode':'FAST_SINGLE_PASS_V1',
            'initial_iters':fast['initial_iters_by_orientation'].get(mode,fast['initial_iters']),
            'max_goal_candidates':fast['max_goal_candidates'],'distance_backend':fast['distance_backend']},
            latency_contract=None,warmup_policy='NONE',benchmark_runs=1,warmup_only=True)
        rp=a.output/('%d.request.json'%index);op=a.output/('%d.result.json'%index)
        rp.write_text(json.dumps(request,indent=2))
        at=time.monotonic()
        try:
            plan(a.python,ROOT,rp,op,a.output/('%d.log'%index),120)
            rows.append({'orientation':mode,'warmup_s':time.monotonic()-at,'worker_ok':True})
        except RuntimeError as e:
            # Failed convergence can still warm a runtime; never count as a valid plan.
            rows.append({'orientation':mode,'warmup_s':time.monotonic()-at,'worker_ok':False,'error':str(e)})
        print(json.dumps(rows[-1]),flush=True)
    (a.output/'manifest.json').write_text(json.dumps({'warmup_only':True,
        'execution_allowed':False,'no_execution_candidate':True,'profiles':rows},indent=2))


if __name__=='__main__':main()
