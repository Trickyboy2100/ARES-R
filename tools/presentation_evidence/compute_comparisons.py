#!/usr/bin/env python3
"""Matched frozen-request diagnostics, CPU equivalence and optional actual GPU A/B."""
import argparse,copy,json,time,sys,hashlib,uuid,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from replay_rasc import load,save,sha,digest
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.manipulation.observed_contact_geometry import _bounded_cloud

def main():
 p=argparse.ArgumentParser();p.add_argument('--records',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);p.add_argument('--private',type=Path,required=True);p.add_argument('--robot-yaml',type=Path,required=True);p.add_argument('--urdf',type=Path,required=True);p.add_argument('--gpu',action='store_true');p.add_argument('--gpu-only',action='store_true');p.add_argument('--reuse-completed',action='store_true');a=p.parse_args();d=a.private;d.mkdir(exist_ok=True,parents=True)
 source=a.records/'transit10.10/transit_plan/planner_request.json';request=load(source);original_plan=load(source.with_name('planning.json'));request['robot_yaml']=str(a.robot_yaml.resolve());request['robot_yaml_urdf']=str(a.urdf.resolve());request['collision_model']['asset_root']=str(a.urdf.parent.resolve())
 # Only relocation of pinned model inputs; verify URDF against the requested source asset.
 original_urdf_hash=request['collision_model']['asset_sha256'].get(a.urdf.name);assert original_urdf_hash==sha(a.urdf),(original_urdf_hash,sha(a.urdf))
 request['planning_only']=True;request['execution_allowed']=False
 attachment=request.get('attached_object_collision')
 if attachment:
  assert attachment['object_id'] not in request['compiled_scene']['cuboids']
  request['compiled_scene']['attached_object_id']=attachment['object_id'];request['compiled_scene']['attached_object_revision']=attachment['revision']
 # Original saved trajectory is used for same-input CPU backend comparison.
 if not a.gpu_only:
  q=original_plan['trajectory_points_rad'];cpu=[];reference=None
  for backend in ['NUMPY_REFERENCE','NATIVE_CPU_V1','NUMPY_REFERENCE','NATIVE_CPU_V1','NUMPY_REFERENCE','NATIVE_CPU_V1']:
   r=dict(request,independent_distance_backend=backend);at=time.perf_counter();v=validate_dense_world(q,r,subdivisions=2);elapsed=time.perf_counter()-at
   if reference is None:reference=v
   keys=['dense_samples','validation_knots','input_trajectory_samples','ignored_object_ids','collision_free','limiting_object_id','limiting_robot_component_id']
   assert all(reference[k]==v[k] for k in keys);assert abs(reference['min_clearance_m']-v['min_clearance_m'])<1e-12
   cpu.append(dict(backend=backend,elapsed_s=elapsed,min_gap_m=v['min_clearance_m'],dense_samples=v['dense_samples'],limiting_object=v['limiting_object_id'],limiting_component=v['limiting_robot_component_id'],collision_free=v['collision_free']));print('CPU',cpu[-1],flush=True)
  save(a.assets/'runlogs/cpu_backend_comparison.json',dict(source_kind='FROZEN_REPLAY',source_request_sha256=sha(source),source_trajectory_sha256=sha(source.with_name('planning.json')),urdf_sha256=sha(a.urdf),exact_equivalence=True,tolerance_m=1e-12,runs=cpu,interpretation_limit='Oct10 saved trajectory; not Oct21 431-sample benchmark. CPU world validation, not GPU speedup or independent self-collision check.'))
  # The actual indexed query retains the original inclusive predicate and ordering.
  from scipy.spatial import cKDTree
  body=np.load(d/'rasc_arrays.npz')['body'];primitives=load(d/'decomposition.json')['primitives'];query=[];expected=None
  for indexed in [False,True,False,True,False,True]:
   at=time.perf_counter();tree=cKDTree(body) if indexed else None;results=[_bounded_cloud(body,*b['observed_bounds_m'],tree) for b in primitives];elapsed=time.perf_counter()-at
   hashes=[hashlib.sha256(x.tobytes()).hexdigest() for x in results]
   if expected is None:expected=hashes
   assert hashes==expected;query.append(dict(indexed=indexed,elapsed_s=elapsed,query_count=len(primitives),returned_point_count=sum(map(len,results)),all_arrays_equal=True))
   print('QUERY',query[-1],flush=True)
  save(a.assets/'runlogs/contact_query_comparison.json',dict(source_kind='FROZEN_REPLAY',source_cloud_sha256=sha(a.records/'real_aligned_sources/body_cloud_artifacts/20261010_114819_091f37ab/body_cloud.npz'),query_box_hash=digest(primitives),runs=query,output_hash=digest(expected),interpretation_limit='Query kernel plus index build across the same primitive bounds; not entire contact geometry artifact/pregrasp preparation.'))
 # Full same-source geometry A/B. Identical q0/qgoal/tool/payload/limits and solve budget.
 rows=[]
 from ares_r.motion.persistent_planner_service import PlannerSupervisor
 service=PlannerSupervisor()
 try:
  for name in ['old','new']:
   r=copy.deepcopy(request);scene=load(d/(name+'_compiled.json'))
   if attachment:
    # Do not erase any newly assigned point primitive: a duplicate diagnosis is a negative result.
    scene['attached_object_id']=attachment['object_id'];scene['attached_object_revision']=attachment['revision']
   scene.pop('digest',None);scene['digest']=hashlib.sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   r.update(compiled_scene=scene,scene_snapshot_id=scene['scene_snapshot_id'],scene_digest=scene['digest'],independent_distance_backend='NATIVE_CPU_V1',benchmark_runs=1,warmup_policy='NONE',solver_policy=dict(mode='FAST_SINGLE_PASS_V1',initial_iters=50,max_goal_candidates=1,distance_backend='NATIVE_CPU_V1'))
   r['planning_parameters'].update(num_trajopt_seeds=2,num_ik_seeds=4,use_cuda_graph=True);r['goal_candidates_rad']=[r['goal_rad']];r['goal_candidate_metadata']=(r.get('goal_candidate_metadata') or [])[:1]
   pre={}
   for endpoint in ['start','goal']:
    v=validate_dense_world([r[endpoint+'_rad'],r[endpoint+'_rad']],r,subdivisions=2);pre[endpoint]={k:v[k] for k in ['collision_free','min_clearance_m','limiting_object_id','limiting_robot_component_id']}
   save(d/(name+'_request.json'),r);row=dict(representation=name,endpoints=pre,source_request_sha256=sha(source),request_sha256=sha(d/(name+'_request.json')),same_q0_qgoal=True,safety_constraints_digest=digest({k:r.get(k) for k in ['start_rad','goal_rad','T_link6_tcp','collision_model','execution_tool_envelope','attached_object_collision','motion_constraints','planning_parameters','solver_policy']}),gpu_attempted=a.gpu)
   if a.gpu:
    cached_plan=load(d/(name+'_planning.json')) if a.reuse_completed and (d/(name+'_planning.json')).exists() else None
    if cached_plan:
     assert cached_plan['scene_digest']==r['scene_digest'] and cached_plan['start_rad']==r['start_rad'] and cached_plan['runtime_motion_goal']==r.get('runtime_motion_goal') and np.allclose(cached_plan['goal_rad'],r['goal_rad'],atol=1e-4,rtol=0)
     assert cached_plan['effective_solver_config']['worker_sha256']==sha(ROOT/'src/ares_r/motion/production_scene_worker.py')
     plan=cached_plan;reply={'ok':True};row['request_elapsed_s']=plan['planner_job']['supervisor_elapsed_s'];row['reused_completed_receipt']=True
    else:
     at=time.monotonic();reply=service.plan(dict(job_id=uuid.uuid4().hex,request=str((d/(name+'_request.json')).resolve()),output=str((d/(name+'_planning.json')).resolve()),log=str((d/(name+'_gpu.log')).resolve()),deadline_monotonic=at+180));row['request_elapsed_s']=time.monotonic()-at;plan=load(d/(name+'_planning.json')) if (d/(name+'_planning.json')).exists() else {}
    row['supervisor_ok']=reply.get('ok');row['supervisor_error']=reply.get('error');row['result']=plan.get('observed_result');row['timing_s']=plan.get('timing_s');row['independent_validation']=plan.get('independent_dense_validation');row['effective_config']=plan.get('effective_solver_config');row['gpu_peak']=plan.get('gpu_memory_bytes');print('GPU',name,row,flush=True)
   rows.append(row);save(a.assets/'runlogs/compare_planning.json',dict(source_kind='FROZEN_REPLAY',experiment_id='OCT10_UNIFORM7_SAME_SOURCE_AB',source_scene='SCENE_133c1fca71484bd2abea0cb3e0b6af8d',source_request_sha256=sha(source),urdf_sha256=sha(a.urdf),runtime_reconstruction='Pinned ARES YAML relocated; worker overwrites collision spheres using saved request; six arm cspace entries unchanged, nonplanning finger locked at zero, link6 tool frame. Exact site runtime YAML absent; not site recommissioning.',padding_m=.007,iterations=50,trajopt_seeds=2,ik_seeds=4,rows=rows,interpretation_limit='Negative results retained. Same captured payload/tool retained. No obstacle removal/limit relaxation for success.'))
 finally:service.reap()
if __name__=='__main__':main()
