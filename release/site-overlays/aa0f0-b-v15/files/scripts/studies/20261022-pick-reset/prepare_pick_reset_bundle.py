"""Stationary pick/reset preparation with overlapping camera and planner init.

No motion/gripper dispatch exists in this file. Golden launchers unchanged.

The base demo (demo-2-branch) keeps using the shared roundtrip parameters; a copy
may declare its own `demos/<demo_id>/parameters.json` (demo-7 does) and change the
5700 抓取配置 ID via `pick_command` and the continuous lift height via `total_lift_m`.
"""
import concurrent.futures,json,os,subprocess,time,threading,sys,argparse
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-overlap-r1'
DEMO='right_arm_pick_lift_replace_reset_v1'
parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path,default=O);parser.add_argument('--source-epoch',type=Path)
parser.add_argument('--demo-id',default=DEMO,help='参数身份；默认 %s（沿用 demos/right_arm_grasp_place_roundtrip_v1/parameters.json）'%DEMO)
parser.add_argument('--parameters',type=Path,default=None,help='显式参数文件；默认 demos/<demo-id>/parameters.json')
parser.add_argument('--lift-m',type=float,default=None,help='覆盖抬升高度（默认取参数文件 total_lift_m）')
args=parser.parse_args();O=args.output_root;E=args.source_epoch or O/'epoch'
PY=str(R/'.venv/bin/python');CAM='/home/yikun/ARES-R/vendor/venv311/bin/python3.11'
os.environ.update(ARES_R_BACKEND_URL='http://127.0.0.1:8776',ARES_R_ROUNDTRIP_API_URL='http://127.0.0.1:8775',ARES_R_PLANNER_SOCKET=str(R/'worklog/runtime/rc1-webui/planner.sock'))
def load(path):return json.loads(Path(path).read_text())
def save(path,v):Path(path).write_text(json.dumps(v,indent=2)+'\n')

def parameters_path(demo_id,explicit=None):
 """Demo-local parameters when the copy declares them, else the shared snapshot."""
 if explicit:return Path(explicit)
 own=R/'demos'/str(demo_id)/'parameters.json'
 return own if own.exists() else R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json'

PARAMETERS=parameters_path(args.demo_id,args.parameters)
PARAMS=load(PARAMETERS)
if PARAMS.get('demo_id') not in (None,args.demo_id):
 raise SystemExit('parameters demo_id mismatch: %r (expected %r for %s)'%(PARAMS.get('demo_id'),args.demo_id,PARAMETERS))
LIFT_SOURCE='parameters.total_lift_m'
LIFT_M=float(PARAMS.get('total_lift_m') or .23)
if args.lift_m is not None:
 if PARAMS.get('total_lift_m') is not None and abs(float(args.lift_m)-LIFT_M)>1e-9:
  raise SystemExit('--lift-m %s contradicts parameters.total_lift_m %s'%(args.lift_m,LIFT_M))
 LIFT_M,LIFT_SOURCE=float(args.lift_m),'CLI_LIFT_M'
if not .01<=LIFT_M<=.30:raise SystemExit('lift height out of the commissioned 0.01-0.30 m band: %s'%LIFT_M)

def pick_command_env():
 """A copy may declare its own 5700 抓取配置 ID through `pick_command`.

 The capture stage is a subprocess, so the override travels as the same switch
 the adapter already supports (ARES_R_EPIC_PICK_COMMAND / ..._PROFILE). Nothing
 is written to config/system.json, and when the declared command equals the
 commissioned profile command the environment is left untouched.
 """
 command=str(PARAMS.get('pick_command') or '').strip()
 name=str(PARAMS.get('pick_profile') or 'right_pick')
 if not command:return {}
 profiles=((load(R/'config/system.json').get('epic') or {}).get('task_profiles') or {})
 if str((profiles.get(name) or {}).get('command'))==command:return {}
 fields=[v.strip() for v in command.split(',')]
 if len(fields)<4 or fields[0]!='320':raise SystemExit('pick_command is not a 320 command: '+command)
 return dict(ARES_R_EPIC_PICK_PROFILE=name,ARES_R_EPIC_PICK_COMMAND=command)

PICK_ENV=pick_command_env()
rows=[];lock=threading.Lock();started=time.monotonic()
def stage(name,call):
 at=time.monotonic();row=dict(stage=name,start_s=at-started)
 try:value=call();row['state']='PASS';return value
 except BaseException as e:row.update(state='FAIL',error=str(e));raise
 finally:
  row['wall_s']=time.monotonic()-at
  with lock:rows.append(row);save(O/'timings.json',dict(physical_motion=False,elapsed_s=time.monotonic()-started,stages=rows))
def command(args,log,env_extra=None):
 with (O/log).open('x') as out:
  result=subprocess.run(list(map(str,args)),cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'src'),**(env_extra or {})),stdout=out,stderr=subprocess.STDOUT)
 if result.returncode:raise RuntimeError('command failed: '+str(O/log))
def init():
 from ares_r.motion.planner_service_client import plan
 profile_path=os.environ.get('ARES_R_AA0F0_B_PROFILE')
 profile=load(profile_path) if profile_path else {}
 source_run=profile.get('planner_initialization_source_run_id') if profile.get('capability_version')=='1.5' else None
 source=(R/'worklog/evidence/demo-runs/right_arm_tray_fetch_hold_v1'/source_run/'pregrasp/planner_request.json') if source_run else R/'worklog/evidence/20261022-pick-reset-timing/forward60/benchmark-request.json'
 if not source.is_file():raise RuntimeError('V15_PLANNER_INITIALIZATION_SOURCE_MISSING: '+str(source))
 req=load(source);req['initialize_only']=True;req['cuboid_capacity_floor']=768
 if source_run:
  req.update(planning_only=True,execution_allowed=False,warmup_policy='NONE',benchmark_runs=1)
 save(O/'initialize.request.json',req)
 plan(PY,R,O/'initialize.request.json',O/'initialize.result.json',O/'initialize.log',120,autostart=False)
 proof=load(O/'initialize.result.json')
 if proof['observed_result']!='INITIALIZED_NOT_PLANNED' or proof['solve_calls']!=0:raise RuntimeError('initialization unexpectedly solved')
def prepare():
 p=PARAMS
 command([PY,'scripts/prepare_authorized_first_pick.py','--epoch',E,'--template-plan',p['template_plan'],'--output',O/'pregrasp','--early-contact-lift-precheck','--contact-observed-narrowphase','--contact-measured-protrusions','--task-tcp-offset-m-rad',json.dumps(p.get('task_tcp_offset_m_rad',[0]*6)),'--demo-tcp-orientation-compensation',json.dumps(p.get('demo_tcp_orientation_compensation',{})),'--contact-extra-allowed-object-ids',json.dumps(p.get('contact_extra_allowed_object_ids') or []),'--contact-extra-allowed-protrusion-waivers',json.dumps(p.get('contact_extra_allowed_protrusion_waivers') or [])],'prepare.log')
 r=load(O/'pregrasp/planner_request.json');ref=load(O/'initialize.request.json')
 r.update(planning_only=True,execution_allowed=False,warmup_policy='NONE',benchmark_runs=1,independent_distance_backend='NATIVE_CPU_V1',cuboid_capacity_floor=768)
 r['solver_policy']=ref['solver_policy'];r['planning_parameters'].update({k:ref['planning_parameters'][k] for k in ('num_ik_seeds','num_trajopt_seeds','use_cuda_graph')});r['planner_clearance_policy']=ref['planner_clearance_policy'];r['planning_parameters']['optimizer_collision_activation_distance']=ref['planning_parameters']['optimizer_collision_activation_distance']
 save(O/'pregrasp/planner_request.json',r)
def solve():
 from ares_r.motion.planner_service_client import plan
 if os.environ.get('ARES_R_AA0F0_B_V15_PARALLEL_STATE')=='1':
  from ares_r.motion.persistent_planner_service import runtime_key
  initial=load(O/'initialize.request.json');formal=load(O/'pregrasp/planner_request.json')
  matched=runtime_key(initial)==runtime_key(formal)
  save(O/'v15-runtime-binding.json',dict(runtime_key_match=matched,
   initialization_source_run_id=load(os.environ['ARES_R_AA0F0_B_PROFILE'])['planner_initialization_source_run_id'],
   fresh_scene_snapshot_id=formal['scene_snapshot_id'],initialization_only=True))
  if not matched:raise RuntimeError('V15_RUNTIME_KEY_MISMATCH: no motion; retain V1.4 as fallback')
 plan(PY,R,O/'pregrasp/planner_request.json',O/'pregrasp/planning.json',O/'pregrasp/planning.log',120,autostart=False)
 result=load(O/'pregrasp/planning.json')
 if os.environ.get('ARES_R_AA0F0_B_V15_PARALLEL_STATE')=='1':
  save(O/'v15-planner-performance.json',dict(
   runtime_binding=load(O/'v15-runtime-binding.json'),
   planner_job=result.get('planner_job'),
   observed_result=result.get('observed_result'),
   scene_snapshot_id=load(O/'pregrasp/planner_request.json')['scene_snapshot_id']))
 if result['observed_result']!='SUCCESS':raise RuntimeError('pregrasp planning not successful')
def lift():
 from ares_r.manipulation.continuous_demo_lift import build_path,validate_path
 from ares_r.motion.independent_path_validation import validate_dense_world
 r=load(O/'pregrasp/planner_request.json');package=load(O/'package/first_pick_execution_package.json');p=PARAMS
 save(O/'lift-height.json',dict(demo_id=args.demo_id,parameters=str(PARAMETERS),lift_height_m=LIFT_M,
  lift_height_source=LIFT_SOURCE,initial_contact_lift_m=p.get('initial_contact_lift_m'),
  additional_free_lift_m=p.get('additional_free_lift_m'),
  native_segment_names=dict(up='lift230',down='lower230'),
  note='the native segment names stay lift230/lower230 for manifest/sender compatibility; the height itself is total_lift_m'))
 points=build_path(package,r,LIFT_M);save(O/'lift230-path.json',points)
 # First prove full non-target clearance; no old fixture exception is needed
 # or applicable if the loaded path already passes the hard-world checks.
 from ares_r.manipulation.pick_reset_pipeline import bind_geometry_proof
 proof=bind_geometry_proof(validate_path(points,r,package,contact_escape=None),points,r,package);save(O/'lift230-validation.json',proof)
 paths=dict(pregrasp=package['trajectories']['pregrasp'],contact=package['trajectories']['contact'],lift230=points,lower230=list(reversed(points)),retreat=list(reversed(package['trajectories']['contact'])),center=list(reversed(package['trajectories']['pregrasp'])))
 save(O/'pick-reset-paths.json',paths)
 empty=validate_dense_world(paths['center'],r,subdivisions=4);save(O/'reset-center-validation.json',empty)
 if not empty['collision_free']:raise RuntimeError('reset center collision')
 save(O/'preparation-ready.json',dict(physical_motion=False,planning_only=True,execution_allowed=False,geometry_prepared=True,native_packaging_complete=False,scene_snapshot_id=r['scene_snapshot_id'],
  demo_id=args.demo_id,parameters=str(PARAMETERS),lift_height_m=LIFT_M,pick_command=PARAMS.get('pick_command'),
  pick_config_id=PARAMS.get('pick_config_id')))
 save(O/'pick-configuration.json',dict(demo_id=args.demo_id,parameters=str(PARAMETERS),
  pick_profile=PARAMS.get('pick_profile'),pick_command=PARAMS.get('pick_command'),
  pick_config_id=PARAMS.get('pick_config_id'),capture_env=PICK_ENV,
  source='parameters.json:pick_command (in-process profile override, config/system.json untouched)'))
def main():
 os.chdir(R);O.mkdir(parents=True,exist_ok=False)
 try:
  stage('GRIPPER_RUNTIME_PREFLIGHT',lambda:command([PY,'scripts/gripper_direct_once.py','status'],'gripper-runtime.json'))
  if load(O/'gripper-runtime.json')['fault_code']:raise RuntimeError('gripper hardware fault; do not scan or plan')
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   camera=pool.submit(stage,'OBSERVATION' if args.source_epoch is None else 'REUSE_FROZEN_DIAGNOSTIC_NOT_EXECUTION',lambda:command([CAM,'scripts/capture_manipulation_observation.py','--profile',PARAMS.get('pick_profile') or 'right_pick','--observed-obb','--output',E],'capture.log',PICK_ENV) if args.source_epoch is None else load(E/'manipulation_observation.json'))
   planner=pool.submit(stage,'PLANNER_INITIALIZE_NO_SOLVE',init)
   camera.result();stage('CONTACT_GEOMETRY_IK',prepare);planner.result()
  stage('CUROBO_PREGRASP',solve)
  stage('BUILD_PICK_PACKAGE',lambda:command([PY,'scripts/build_first_pick_execution_package.py','--plan',O/'pregrasp','--epoch',E,'--payload-policy','DEMO_EXPOSED160_WIDTH100_REAR20_RETAINED_V2','--output',O/'package'],'package.log'))
  stage('LIFT230_AND_REVERSE_GEOMETRY',lift)
 except BaseException as e:
  save(O/'failure.json',dict(error=str(e),physical_motion=False,elapsed_s=time.monotonic()-started));raise
 finally:print(json.dumps(dict(output=str(O),elapsed_s=time.monotonic()-started,stages=rows)),flush=True)
if __name__=='__main__':main()
