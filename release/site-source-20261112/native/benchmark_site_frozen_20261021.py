"""Explicit parameter experiments on frozen grasp request; no actuation imports."""
import argparse,copy,hashlib,json,os,statistics,time,uuid
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
PROFILES=[
 ('single25_1x4_graph',25,1,4,True),
 ('single25_1x4_nograph',25,1,4,False),
 ('single25_2x4_graph',25,2,4,True),
 ('single50_2x4_graph',50,2,4,True),
 ('single100_2x4_graph',100,2,4,True),
 ('single50_4x4_graph',50,4,4,True),
 ('single50_4x8_graph',50,4,8,True),
 ('single50_8x8_graph',50,8,8,True),
 ('single50_2x4_nograph',50,2,4,False),
 ('single25_2x4_nograph',25,2,4,False),
 ('native_refine_2x4_graph',None,2,4,True),
 ('native_refine_8x8_graph',None,8,8,True)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def percentile(a,p):return sorted(a)[max(0,__import__('math').ceil(len(a)*p)-1)] if a else None
def main():
 p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--profiles',nargs='+');p.add_argument('--warm-runs',type=int,default=2);p.add_argument('--independent-native',action='store_true');p.add_argument('--seed-step',type=int,default=0);a=p.parse_args()
 if not 1<=a.warm_runs<=20:raise ValueError('warm runs 1..20')
 source=json.loads(a.request.read_text())
 if source.get('planning_only') is not True or source.get('execution_allowed') is not False:raise RuntimeError('planning-only request required')
 from ares_r.motion.persistent_planner_service import PlannerSupervisor
 a.output.mkdir(parents=True,exist_ok=False)
 report=dict(request=str(a.request),request_sha256=sha(a.request),scene_snapshot_id=source['scene_snapshot_id'],scene_digest=source['scene_digest'],physical_motion=False,production_configuration_modified=False,former_FAST_QUALITY_deadlines_applied=False,hang_watchdog_s=3500,profiles={})
 for name,iters,seeds,ik,graph in PROFILES:
  if a.profiles and name not in a.profiles:continue
  service=PlannerSupervisor();directory=a.output/name;directory.mkdir();rows=[]
  try:
   for index in range(a.warm_runs+1):
    request=copy.deepcopy(source);request.update(warmup_policy='NONE',benchmark_runs=1)
    if a.independent_native:request['independent_distance_backend']='NATIVE_CPU_V1'
    # Equal goal branch for the optimizer matrix; symmetry is a separate study.
    request['goal_candidates_rad']=source.get('goal_candidates_rad',[source['goal_rad']])[:1]
    if source.get('goal_candidate_metadata'):request['goal_candidate_metadata']=source['goal_candidate_metadata'][:1]
    request['planning_parameters'].update(num_trajopt_seeds=seeds,num_ik_seeds=ik,use_cuda_graph=graph)
    request['planning_parameters']['random_seed']=source['planning_parameters']['random_seed']+index*a.seed_step
    if iters is None:request.pop('solver_policy',None)
    else:request['solver_policy']=dict(mode='FAST_SINGLE_PASS_V1',initial_iters=iters,max_goal_candidates=1,distance_backend='NATIVE_CPU_V1')
    rp=directory/(str(index)+'.request.json');op=directory/(str(index)+'.planning.json');save(rp,request)
    oldpid=service.process.pid if service.process is not None else None
    at=time.monotonic();response=service.plan(dict(job_id=uuid.uuid4().hex,request=str(rp),output=str(op),log=str(directory/(str(index)+'.log')),deadline_monotonic=at+3500))
    elapsed=time.monotonic()-at;artifact=json.loads(op.read_text()) if op.exists() else {}
    pid=service.process.pid if service.process is not None else None
    row=dict(repeat=index,cold_worker=(oldpid is None or pid!=oldpid),worker_pid=pid,wall_s=elapsed,response=response,observed_result=artifact.get('observed_result'),timing_s=artifact.get('timing_s'),effective_solver_config=artifact.get('effective_solver_config'),independent_dense_validation=artifact.get('independent_dense_validation'),orientation_validation=artifact.get('orientation_validation'),sphere_count=artifact.get('active_collision_sphere_count'),obstacle_count=len(artifact.get('world_cuboid_ids',[])),trajectory_hash=hashlib.sha256(json.dumps(artifact.get('trajectory_points_rad')).encode()).hexdigest())
    rows.append(row);report['profiles'][name]=dict(runs=rows,parameter_overrides=dict(iters=iters,num_trajopt_seeds=seeds,num_ik_seeds=ik,use_cuda_graph=graph))
    save(a.output/'report.json',report);print(json.dumps(dict(profile=name,repeat=index,cold=row['cold_worker'],wall_s=elapsed,result=row['observed_result'],timing_s=row['timing_s'],error=response.get('error'))),flush=True)
    if not response.get('ok'):break
  finally:service.reap()
  warm=[r['wall_s'] for r in rows if not r['cold_worker']]
  report['profiles'][name].update(successes=sum(r['observed_result']=='SUCCESS' for r in rows),samples=len(rows),warm_p50_s=statistics.median(warm) if warm else None,warm_p95_s=percentile(warm,.95))
  save(a.output/'report.json',report)
 print('BENCHMARK_COMPLETE',flush=True)
if __name__=='__main__':main()
