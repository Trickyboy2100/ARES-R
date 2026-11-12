from pathlib import Path
import json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-pick-retest-1113'
def load(p):return json.loads(p.read_text())
obs=load(O/'epoch2/manipulation_observation.json');scene=load(O/'epoch2/live_scene/fresh_scene_summary.json');stage=load(O/'current_stage_diagnostics.json');pre=load(O/'pregrasp_plan/contact_lift_precheck.json');request=load(O/'pregrasp_plan/planner_request.json');world=load(R/'config/robot_world.json');base=world['arms']['right'];diag=obs['robot_state_after']['right']['diagnostics']
def transform(xyz,rpy):
 T=np.eye(4);T[:3,:3]=Rotation.from_euler('xyz',rpy).as_matrix();T[:3,3]=xyz;return T
T=transform(base['base_xyz_m'],base['base_rpy_rad'])@transform(np.asarray(diag['tcp_position_mm_rad'][:3])/1000,diag['tcp_position_mm_rad'][3:])
current={'xyz_m':T[:3,3].tolist(),'rpy_deg':Rotation.from_matrix(T[:3,:3]).as_euler('xyz',degrees=True).tolist(),'T_body_tcp':T.tolist(),'joints_rad':diag['joint_position_rad'],'tool':diag['tool_data']}
plans=[]
for name,folder in [('NORMAL_40_PERCENT','pregrasp_plan'),('FLIPPED_40_PERCENT','flipped_plan'),('CURRENT_FULL_OPEN_ENVELOPE','actual_opening/pregrasp_plan')]:
 for x in load(O/folder/'gpu_planning_audit.json'):
  error=x['response'].get('error','');overlap=[]
  if 'INVALID_GOAL_COLLISION: ' in error:
   try:overlap=[{k:v for k,v in y.items() if v<0} for y in json.loads(error.split('INVALID_GOAL_COLLISION: ',1)[1])]
   except Exception:pass
  plans.append({'mode':name,'wall_s':x['wall_s'],'budget_s':x['budget_s'],'success':x['response'].get('ok',False),'failure':'INVALID_GOAL_COLLISION' if overlap else error,'negative_model_distances_m':overlap,'successful_trajectory_duration_s':None})
normal=[x for x in stage if x['symmetry']=='NORMAL']
report={'schema_version':1,'kind':'FRESH_CURRENT_SCENE_PICK_RETEST_NO_MOTION','root':str(O),'physical_motion':False,'production_services_changed':False,'speed_parameters_changed':False,'overall':'NOT_READY_NON_TARGET_COLLISION',
 'observation':{k:obs[k] for k in ('observation_id','scene_snapshot_id','scene_digest','pointcloud_sha256','detection_id','calibration_revision','tool_revision','maximum_joint_delta_rad')},
 'observation_wall_s':obs['completed_at_unix']-obs['captured_at_unix'],'capture_phase_timing':load(O/'capture_phase_timing.json'),'scene_timing_s':scene['timing_s'],'initial_IK_s':pre['elapsed_s'],
 'planner_attempts':plans,'planner_time_interpretation':'cold process/model/world initialization plus invalid-goal collision rejection, not successful solve time or FAST timeout; warm successful latency not established',
 'gripper_read_only':load(O/'gripper-read.json'),'gripper_model_contract':'actual raw992 near fully open: current-to-pregrasp tested separately with full-opening envelope; later contact assumes commanded raw400 but command NOT executed',
 'current_tcp_body':current,'stage_tcp_body':{'normal_pregrasp':normal[0]['start'],'normal_grasp':normal[0]['end'],'normal_lift100':normal[1]['end']},
 'stage_tests':stage,'hold230_ik_only':load(O/'hold230_ik_only.json'),
 'grasp_close_and_verification':{'physical_test':False,'closure_duration_s':None,'software_delayed_readback_schedule_s':[.25,.75,1.5],'held_payload_confirmed':False},
 'scope_rule':'STAGE_TARGET_CONTACT_V1 bound to this fresh observation. Target-only contact allowed; all non-target collisions retained.',
 'remaining_lift130_status':'IK_ONLY; full payload SceneSnapshot/cuRobo/native execution not accepted because previous stages fail',
 'physical_duration_estimates':'contact and lift durations are kinematic-only at configured caps, NOT executable packages. No motion duration can be claimed for a rejected pregrasp plan.',
 'slow_contact':{'current_contact_cap_rad_s':.05,'free_motion_cap_rad_s':.20,'retiming_policy':'VERIFIED_SHORT_V1','production_switched_to_RC1':False,'historical_comparison_kind':'PREVIOUSLY_REPLAYED_OCT16_REAL_PATH_NOT_THIS_FRESH_EPOCH','historical_old_contact_s':115.04,'historical_same_cap_retimed_contact_s':16.72,'cause':'old global dilation reacts to worst dense-IK knot derivative; stage-specific contact cap is separately lower than free motion'},
 'orientation_convention':'BODY XYZ in metres. RPY degrees: Rz(yaw)Ry(pitch)Rx(roll). Physical gripper forward is TCP +Z; Euler zeros are not horizontal-forward gripper.'}
(O/'REPORT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
(O/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(O))+'\n' for p in sorted(O.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
print(json.dumps({'current':current,'normal_tcp_targets':report['stage_tcp_body'],'report':str(O/'REPORT.json')},ensure_ascii=False))
