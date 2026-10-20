"""Summarize fresh no-motion rehearsal; never imports device adapters."""
import os,json,hashlib,time,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.native_execution_package import package_native_preview

R=Path('/home/yikun/ARES-R-RC1-20261019')
O=Path(os.environ['ARES_R_REHEARSAL_DIR'])
if R/'worklog/evidence' not in O.parents:raise ValueError('isolated evidence required')
def load(p):return json.loads(p.read_text())
obs=load(O/'epoch2/manipulation_observation.json')
req=load(O/'pregrasp_plan/planner_request.json')
gpu=load(O/'pregrasp_plan/gpu_planning_audit.json')
plan=load(O/'pregrasp_plan/planning-warm.json')
stages=load(O/'current_stage_diagnostics.json')
params=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
base=load(R/'config/robot_world.json')['arms']['right']
d=obs['robot_state_after']['right']['diagnostics']
def T(x,r):
 t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',r).as_matrix();t[:3,3]=x;return t
actual=T(base['base_xyz_m'],base['base_rpy_rad'])@T(np.asarray(d['tcp_position_mm_rad'][:3])/1000,d['tcp_position_mm_rad'][3:])
pregrasp_native={}
try:
 text,pregrasp_native=package_native_preview(plan['trajectory_points_rad'],plan['smoothness']['sample_period_s'],
  load(R/'config/jaka_mini2_motion.site.json'),tool_id=d['tool_data']['tool_id'],
  controller_tool_pose_mm_rad=req['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
  speed_ceiling_rad_s=params['lift_velocity_rad_s'],accel_ceiling_rad_s2=params['lift_acceleration_rad_s2'],
  tracking_stop_threshold_deg=params['tracking_stop_deg'],max_excursion_rad=math.radians(220))
 (O/'pregrasp.native.preview.txt').write_text(text)
except Exception as e:pregrasp_native={'error':str(e),'execution_allowed':False}
summary=[]
for row in stages:
 proof=row.get('collision_proof',{});native=row.get('native_audit',{})
 summary.append({'symmetry':row['symmetry'],'segment':row['segment'],
  'passed':row['full_collision_validation'],'start':row['start'],'end':row['end'],
  'validation_wall_s':row['collision_validation_wall_s'],'retiming_wall_s':row['native_build_wall_s'],
  'duration_s':native.get('duration_s'),'max_joint_speed_rad_s':native.get('max_joint_speed_rad_s'),
  'max_joint_accel_rad_s2':native.get('max_joint_accel_rad_s2'),
  'max_level_error_deg':proof.get('orientation',{}).get('max_level_error_deg'),
  'non_target_gripper_clearance_m':proof.get('non_target_tool_world_validation',{}).get('min_clearance_m'),
  'error':row.get('collision_error')})
report={'schema_version':1,'kind':'FRESH_SCENE_PICK_15S_NO_MOTION',
 'physical_motion':False,'production_services_changed':False,'deployment':str(R),
 'deadline':{'fast_profile_s':load(R/'config/planner_latency_profiles.json')['fast']['result_deadline_s'],
  'demo_fast_s':params['planning_deadline_s'],'cancellation_retained':True,
  'cold_initialization_diagnostic_budget_s':45,'quality_fallback_changed':False},
 'binding':{k:obs[k] for k in ('observation_id','scene_snapshot_id','scene_digest','pointcloud_sha256','calibration_revision','tool_revision','maximum_joint_delta_rad')},
 'observation_wall_s':obs['completed_at_unix']-obs['captured_at_unix'],
 'capture_phase_timing':load(O/'capture_phase_timing.json'),
 'scene_timing_s':load(O/'epoch2/live_scene/fresh_scene_summary.json')['timing_s'],
 'contact_lift_ik_precheck_s':load(O/'pregrasp_plan/contact_lift_precheck.json')['elapsed_s'],
 'current_tcp_body':{'xyz_m':actual[:3,3].tolist(),'rpy_deg':Rotation.from_matrix(actual[:3,:3]).as_euler('xyz',degrees=True).tolist()},
 'fresh_target':obs['target'],
 'gpu_attempts':[{k:x.get(k) for k in ('label','wall_s','budget_s','observed_result','timing_s')}|{'ok':x['response'].get('ok'),'error':x['response'].get('error')} for x in gpu],
 'pregrasp_native_preview':pregrasp_native,'selected_pregrasp_branch':plan['selected_goal_candidate_metadata'],
 'pregrasp_dense_proof':plan['independent_dense_validation'],
 'stages':summary,'hold230_ik_only':load(O/'hold230_ik_only.json'),
 'gripper_read_only':load(O/'gripper-read.json'),
 'limits':['Contact/free-space geometry assumes 40 percent opening. Actual readback is separately recorded; no gripper command sent.',
  'Remaining 130 mm has continuous IK only: attached-payload cuRobo/dense/native acceptance is not established.',
  'No physical close, delayed-readback grasp verification or payload feedback can be simulated as confirmed success.',
  'Native preview is not execution authorization; production services and original golden demo unchanged.'],
 'orientation_convention':'BODY +X forward,+Y left,+Z up; RPY degrees XYZ Euler. Physical gripper forward is TCP +Z, not Euler zero.'}
(O/'REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
(O/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(O))+'\n' for p in sorted(O.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
print(json.dumps({'report':str(O/'REPORT.json'),'current':report['current_tcp_body'],'pregrasp_native_duration_s':pregrasp_native.get('duration_s'),'error':pregrasp_native.get('error'),'stages':[{k:x[k] for k in ('symmetry','segment','passed','duration_s')} for x in summary]}))
