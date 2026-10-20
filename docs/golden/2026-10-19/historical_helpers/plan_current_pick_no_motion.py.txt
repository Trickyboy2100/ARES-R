"""Real GPU plan only: no device imports, network or sender invocation."""
import json,time,uuid,copy,sys,os
from pathlib import Path
from ares_r.motion.persistent_planner_service import PlannerSupervisor
ROOT=Path('/home/yikun/ARES-R-RC1-20261019');OUT=ROOT/'worklog/evidence/2026-10-19-current-pick-rehearsal'
OUT=Path(os.environ.get('ARES_R_REHEARSAL_DIR',str(OUT)))
if ROOT/'worklog/evidence' not in OUT.parents:raise ValueError('isolated evidence directory required')
def main():
    request=json.loads((OUT/'pregrasp_plan/planner_request.json').read_text())
    fast=json.loads((ROOT/'config/planner_latency_profiles.json').read_text())['fast']
    request.update(warmup_policy='NONE',benchmark_runs=1)
    request['planning_parameters'].update({k:fast[k] for k in ('num_ik_seeds','num_trajopt_seeds','use_cuda_graph')})
    request['solver_policy']={'mode':'FAST_SINGLE_PASS_V1','initial_iters':fast['initial_iters'],'max_goal_candidates':fast['max_goal_candidates'],'distance_backend':fast['distance_backend']}
    plan_dir=OUT/'pregrasp_plan'
    if '--flipped' in sys.argv:
        plan_dir=OUT/'flipped_plan';plan_dir.mkdir(exist_ok=False)
        request['goal_rad']=request['goal_candidates_rad'][1]
        request['goal_candidates_rad']=[request['goal_rad']]
        request['goal_candidate_metadata']=[request['goal_candidate_metadata'][1]]
    path=plan_dir/'planner_request.json';path.write_text(json.dumps(request,indent=2)+'\n')
    supervisor=PlannerSupervisor();records=[]
    try:
        for label,budget in [('cold',45),('warm',float(fast['result_deadline_s']))]:
            start=time.monotonic();output=plan_dir/('planning-'+label+'.json')
            job={'job_id':uuid.uuid4().hex,'request':str(path),'output':str(output),'log':str(plan_dir/('planner-'+label+'.log')),'deadline_monotonic':start+budget}
            response=supervisor.plan(job);record={'label':label,'wall_s':time.monotonic()-start,'budget_s':budget,'response':response,'physical_execution':False}
            if output.exists():
                result=json.loads(output.read_text());record.update(observed_result=result.get('observed_result'),timing_s=result.get('timing_s'),independent_dense_validation=result.get('independent_dense_validation'))
                if result.get('observed_result')=='SUCCESS' and not (plan_dir/'planning.json').exists():(plan_dir/'planning.json').write_text(output.read_text())
            records.append(record);(plan_dir/'gpu_planning_audit.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(record),flush=True)
            if not response.get('ok'):break
    finally:supervisor.reap()
if __name__=='__main__':main()
