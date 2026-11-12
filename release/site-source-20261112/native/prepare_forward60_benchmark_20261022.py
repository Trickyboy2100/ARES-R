"""Freeze a motion-free benchmark request and independent endpoint checks."""
import json,time,hashlib
from pathlib import Path
from ares_r.motion.independent_path_validation import validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-timing/forward60'
r=json.loads((O/'preparation-retry/planner_request.json').read_text());r.update(planning_only=True,execution_allowed=False,warmup_policy='NONE',benchmark_runs=1,independent_distance_backend='NATIVE_CPU_V1')
r['planning_parameters'].update(num_ik_seeds=4,num_trajopt_seeds=1,use_cuda_graph=True)
r['solver_policy']=dict(mode='FAST_SINGLE_PASS_V1',initial_iters=25,max_goal_candidates=1,distance_backend='NATIVE_CPU_V1')
policy=json.loads((R/'config/scene_aware_motion.json').read_text())['planner'];r['planner_clearance_policy']=dict(policy,revision=policy['profile_revision']);r['planning_parameters']['optimizer_collision_activation_distance']=policy['optimizer_collision_activation_distance_m']
rows=[];at=time.monotonic()
for name,q in [('start',r['start_rad'])]+[('goal_'+str(i),q) for i,q in enumerate(r['goal_candidates_rad'])]:
 proof=validate_dense_world([q,q],r,subdivisions=2);rows.append(dict(name=name,validation=proof));print(json.dumps(dict(name=name,valid=proof['collision_free'],gap=proof['min_clearance_m'],object=proof['limiting_object_id'])),flush=True)
(O/'benchmark-request.json').write_text(json.dumps(r,indent=2)+'\n');(O/'endpoint-checks.json').write_text(json.dumps(dict(physical_motion=False,elapsed_s=time.monotonic()-at,rows=rows),indent=2)+'\n')
