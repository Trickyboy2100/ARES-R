import json,os,sys,time,subprocess,copy
from pathlib import Path
ROOT=Path('/home/yikun/ARES-R-RC1-20261019');OUT=Path(__file__).resolve().parent
PROFILES=('FAST50','FAST100','QUALITY_NO_WARMUP')
CASES={'center':'PLAN_72a6186055e24cb6a9c8f1f6f7c5583e','restore':'PLAN_a9a7f76a9fb54be797d707d5f829cf84'}
if len(sys.argv)>1:
    import torch
    torch.cuda.set_per_process_memory_fraction(.45)
    from ares_r.motion.production_scene_worker import main
    profile,case=sys.argv[1:3];source=json.loads((ROOT/'worklog/evidence/scene-aware-motion'/CASES[case]/'planner_request.json').read_text())
    source.update(planning_only=True,execution_allowed=False,physical_state='FROZEN_OFFLINE_BENCHMARK',benchmark_runs=1,warmup_policy='NONE',latency_contract=None)
    if profile.startswith('FAST'):
        source['planning_parameters'].update(num_ik_seeds=4,num_trajopt_seeds=2,use_cuda_graph=True)
        source['solver_policy']=dict(mode='FAST_SINGLE_PASS_V1',initial_iters=int(profile[4:].split('_')[0]),max_goal_candidates=1,distance_backend='NATIVE_CPU_V1')
    else:
        source['planning_parameters'].update(num_ik_seeds=8,num_trajopt_seeds=8,use_cuda_graph=False);source['solver_policy']=None
    if profile.endswith('_NATIVE'):source['independent_distance_backend']='NATIVE_CPU_V1'
    request=OUT/(profile+'-'+case+'-request.json');request.write_text(json.dumps(source))
    for repeat in range(3):
        output=OUT/(profile+'-'+case+'-'+str(repeat)+'.json');sys.argv=['frozen-worker',str(request),str(output)];started=time.monotonic()
        try:main()
        except BaseException as error:
            if not output.exists():output.write_text(json.dumps(dict(error=str(error),exception_type=type(error).__name__)))
        value=json.loads(output.read_text());row=dict(profile=profile,case=case,repeat=repeat,wall_s=time.monotonic()-started,result=value.get('observed_result'),failure_reason=value.get('failure_reason',value.get('error')),timing=value.get('timing_s'),output=str(output))
        with (OUT/'results.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print('BENCH_RESULT',json.dumps(row),flush=True)
else:
    for case in CASES:
        for profile in PROFILES:
            with (OUT/(profile+'-'+case+'.log')).open('w') as log:
                try:
                    result=subprocess.run([sys.executable,str(__file__),profile,case],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=log,stderr=subprocess.STDOUT,timeout=180)
                    print('GROUP',profile,case,result.returncode,flush=True)
                except subprocess.TimeoutExpired:print('GROUP_TIMEOUT',profile,case,flush=True)
