"""Build exact golden pregrasp request from today's captured epoch, no planning/execution."""
import hashlib,json,os,subprocess,time,sys
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261021-center-grasp-planner-study'
p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text())
diagnostic='--pregrasp-only' in sys.argv
name='frozen-pregrasp-only' if diagnostic else 'frozen-pregrasp'
args=[str(R/'.venv/bin/python'),'scripts/prepare_authorized_first_pick.py','--epoch',str(O/'pick-epoch'),
 '--template-plan',p['template_plan'],'--output',str(O/name),
 '--contact-observed-narrowphase',
 '--task-tcp-offset-m-rad',json.dumps(p.get('task_tcp_offset_m_rad',[0]*6)),
 '--demo-tcp-orientation-compensation',json.dumps(p.get('demo_tcp_orientation_compensation',{}))]
if not diagnostic:args.append('--early-contact-lift-precheck')
at=time.monotonic()
with (O/('prepare-pregrasp-only.log' if diagnostic else 'prepare.log')).open('x') as log:
 result=subprocess.run(args,cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src')),stdout=log,stderr=subprocess.STDOUT)
record=dict(wall_s=time.monotonic()-at,returncode=result.returncode,argv=args,physical_motion=False)
(O/('prepare-pregrasp-only-timing.json' if diagnostic else 'prepare-timing.json')).write_text(json.dumps(record,indent=2)+'\n')
if result.returncode:raise SystemExit(result.returncode)
source=O/name/'planner_request.json';request=json.loads(source.read_text())
request.update(planning_only=True,execution_allowed=False,warmup_policy='NONE',benchmark_runs=1)
# Same policy as formal Live.prepare, isolated request only. Do not change world.
policy=json.loads((R/'config/scene_aware_motion.json').read_text())['planner']
request['planner_clearance_policy']=dict(policy,revision=policy['profile_revision'])
request['planning_parameters']['optimizer_collision_activation_distance']=policy['optimizer_collision_activation_distance_m']
request['benchmark_scope']='PREGRASP_ONLY_NOT_CONTACT_OR_LIFT_CERTIFICATION' if diagnostic else 'GOLDEN_PRECHECK_BOUND_PREGRASP'
target=O/('frozen-pregrasp-only-request.json' if diagnostic else 'frozen-request.json');target.write_text(json.dumps(request,indent=2)+'\n')
ob=json.loads((O/'pick-epoch/manipulation_observation.json').read_text());prep=json.loads((O/name/'preparation.json').read_text())
summary=dict(request=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),preparation_wall_s=record['wall_s'],
 scene_snapshot_id=request['scene_snapshot_id'],world_obstacles=len(request['compiled_scene']['cuboids']),
 target=prep,observation_wall_s=ob['completed_at_unix']-ob['captured_at_unix'],physical_motion=False)
(O/('frozen-pregrasp-only-summary.json' if diagnostic else 'frozen-summary.json')).write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
