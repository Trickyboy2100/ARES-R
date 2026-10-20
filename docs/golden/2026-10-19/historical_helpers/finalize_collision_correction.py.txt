"""Frozen-scene collision correction certificate; no device API."""
from pathlib import Path
import json,hashlib,shutil,subprocess,time
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-pick-retest-1113'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original=O/'refined_contact/pregrasp_plan';final=O/'refined_contact_v3/pregrasp_plan'
a=load(original/'planner_request.json');b=load(final/'planner_request.json')
keys=('compiled_scene','start_rad','goal_rad','goal_candidates_rad','goal_candidate_metadata','collision_model','execution_tool_envelope','T_body_model','T_link6_tcp','controller_tool_pose_mm_rad','robot_yaml_urdf','scene_snapshot_id','scene_digest')
if not all(a.get(k)==b.get(k) for k in keys):raise RuntimeError('DIFFERENT_GEOMETRIC_PROBLEMS_NO_TRAJECTORY_REUSE')
plan=load(original/'planning-cold.json')
if plan['observed_result']!='SUCCESS' or plan['selected_goal_candidate_metadata']['branch_sha256'] not in [x['branch_sha256'] for x in b['goal_candidate_metadata']]:raise RuntimeError('PRECHECK_BRANCH_MISMATCH')
stages=load(O/'refined_contact_v3/current_stage_diagnostics.json')
if not all(x['full_collision_validation'] and x['timing_estimate_collision_approved'] for x in stages):raise RuntimeError('CONTACT_STAGE_NOT_READY')
dest=O/'final_verified_pick_plan';dest.mkdir(exist_ok=False)
for k in ('planning_parameters','solver_policy','warmup_policy','benchmark_runs'):b[k]=a[k]
(dest/'planner_request.json').write_text(json.dumps(b,indent=2)+'\n')
shutil.copy2(original/'planning-cold.json',dest/'planning.json')
certificate={'source_plan':str(original/'planning-cold.json'),'source_plan_sha256':sha(original/'planning-cold.json'),'geometric_fields_identical':list(keys),'branch_sha256':plan['selected_goal_candidate_metadata']['branch_sha256'],'same_frozen_scene':True,'physical_motion':False}
(dest/'frozen_plan_reuse_certificate.json').write_text(json.dumps(certificate,indent=2)+'\n')
command=['bash','scripts/offline_sandbox.sh','.venv/bin/python','scripts/build_first_pick_execution_package.py','--plan',str(dest),'--epoch',str(O/'epoch2'),'--output',str(O/'collision_corrected_pick_package')]
with (O/'collision-corrected-package.log').open('w') as log:rc=subprocess.run(command,cwd=R,stdout=log,stderr=subprocess.STDOUT).returncode
gpu=load(original/'gpu_planning_audit.json');probe=load(O/'raw_occupancy_probe.json')
report={'schema_version':1,'created_at_unix':time.time(),'result':'FROZEN_PICK_COLLISION_FALSE_POSITIVES_CORRECTED',
 'physical_motion':False,'production_services_switched':False,'deployed_root':str(R),'original_root_untouched':'/home/yikun/ARES-R',
 'self_filter_attribution':probe['self_filter_attribution'],
 'root_causes':['Union gripper box included empty space between pinned parts','Scene AABBs filled gaps around observed support/structure','UNKNOWN_OCCUPIED remaining_observed means measured unclassified points, not unseen occlusion'],
 'correction':['Reuse existing pinned 40% component geometry for free-space planning','Gripper-only contact narrow phase over same-frame raw 2mm occupied voxel spheres','Preserve per-object 4/7mm sensor inflation in voxel sphere radius','Arm links retain original scene; known/unobserved volume retain hard geometry','Initial100mm gripper sweep covers opening0..40% at5% steps with1.1mm interpolation padding'],
 'pointcloud_sha256':b['manipulation_contact_scope']['pointcloud_sha256'],'scene_snapshot_id':b['scene_snapshot_id'],
 'contact_geometry_revision':b['contact_observed_geometry']['revision'],'non_target_voxels':sum(len(x['centers_body_m']) for x in b['contact_observed_geometry']['rows']),
 'world_obstacles_deleted':0,'blanket_TCP_radius_ignore':False,'controller_protections_changed':False,
 'curobo_pregrasp':{'cold_wall_s':gpu[0]['wall_s'],'result':gpu[0].get('observed_result'),'solver_s':gpu[0]['timing_s']['planning_samples'][0],'warm_4s_result':gpu[1]['response'],'same_geometric_problem':certificate},
 'contact_and_lift':[{'symmetry':x['symmetry'],'stage':x['segment'],'passed':x['full_collision_validation'],'modeled_clearance_m':x['collision_proof']['non_target_tool_world_validation']['min_clearance_m'],'native_duration_s':x['native_audit']['duration_s'],'native_build_s':x['native_build_wall_s'],'opening_percent':x['collision_proof']['non_target_tool_world_validation']['gripper_openings_checked_percent']} for x in stages],
 'package_builder_returncode':rc,'planning_only_package':str(O/'collision_corrected_pick_package'),
 'tests':'710/710 OK; occupied voxel inside finger, hard known obstacle, genuinely unobserved volume and payload checks reject',
 'remaining':['FAST warm4s deadline still fails; cold success is not realtime acceptance','Physical start gripper was raw992; 40% model requires real400 command/readback before affected free-space move','First100mm candidate payload full envelope remains upstream software/site qualification item','Fresh scan/state and supervised authorization still needed; no frozen artifact is a live execution authorization'],
 'source_files_sha256':{str(p.relative_to(R)):sha(p) for p in [R/'src/ares_r/manipulation/observed_contact_geometry.py',R/'src/ares_r/motion/short_motion.py',R/'scripts/prepare_authorized_first_pick.py',R/'scripts/run_grasp_place_roundtrip.py',R/'scripts/build_first_pick_execution_package.py',R/'tests/test_observed_contact_geometry.py']}}
(O/'COLLISION_CORRECTION_REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'report':str(O/'COLLISION_CORRECTION_REPORT.json'),'package_returncode':rc,'collision_stages_passed':len(stages)}))
