from pathlib import Path
import json,math,hashlib
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-current-pick-rehearsal'
def load(p):return json.loads(p.read_text())
obs=load(O/'epoch2/manipulation_observation.json');prep=load(O/'pregrasp_plan/preparation.json');stage=load(O/'current_stage_diagnostics.json');scene=load(O/'epoch2/live_scene/fresh_scene_summary.json');pre=load(O/'pregrasp_plan/contact_lift_precheck.json')
gpu=[]
for name,path in [('NORMAL',O/'gpu_planning_audit.json'),('FLIPPED_180',O/'flipped_plan/gpu_planning_audit.json')]:
 for row in load(path):
  error=row['response'].get('error','');detail=[]
  if 'INVALID_GOAL_COLLISION: ' in error:
   try:detail=[{k:v for k,v in x.items() if v<0} for x in json.loads(error.split('INVALID_GOAL_COLLISION: ',1)[1])]
   except Exception:pass
  gpu.append({'symmetry':name,'label':row['label'],'wall_s':row['wall_s'],'budget_s':row['budget_s'],'success':row['response'].get('ok',False),'failure':'INVALID_GOAL_COLLISION' if detail else error,'overlaps':detail,'worker_reaped':row['response'].get('worker_reaped')})
normal=[x for x in stage if x['symmetry']=='NORMAL']
result={'schema_version':1,'purpose':'CURRENT_SITE_PICK_REHEARSAL_NO_MOTION','overall':'NOT_READY_COLLISION_MODEL_REJECTED','physical_motion':False,'parameters_modified':False,
 'observation':{k:obs[k] for k in ('observation_id','scene_snapshot_id','scene_digest','pointcloud_sha256','detection_id','calibration_revision','tool_revision','maximum_joint_delta_rad')},
 'stages':[
  {'stage':'ID1 detection','success':True,'timing_probe':load(O/'detection_timing.json'),'initial_failure':'5700 connection refused; resolved after operator started service'},
  {'stage':'PixelPro CAMERA to BODY','success':True,'isolated_wall_s':load(O/'pixelpro-only.json')['wall_s'],'epoch_capture_body_s':scene['timing_s']['capture_body']},
  {'stage':'fresh SceneSnapshot','success':True,'scene_pipeline':scene,'whole_observation_wall_s':15.44},
  {'stage':'contact55mm and lift100mm IK','success':pre['passed'],'wall_s':pre['elapsed_s'],'prepare_cli_wall_s':1.12,'accepted_symmetries':[x['grasp_symmetry_id'] for x in pre['accepted']]},
  {'stage':'current to pregrasp cuRobo','success':False,'attempts':gpu,'successful_plan_time_s':None,'native_execution_duration_s':None,'normal_joint_velocity_only_lower_bound_s':max(prep['goal_excursion_from_start_deg'])*math.pi/180/.2},
  {'stage':'pregrasp to grasp contact55mm','kinematics_passed':True,'collision_passed':False,'timing_only_native_duration_s':{x['symmetry']:x['native_audit']['duration_s'] for x in stage if x['segment']=='contact'},'execution_allowed':False},
  {'stage':'gripper close and grasp verification','success':None,'physical_test':'NOT_PERFORMED','reason':'No gripper actuation in this rehearsal','readback_schedule_s':[.25,.75,1.5],'actual_close_duration_s':None},
  {'stage':'initial lift100mm','kinematics_passed':True,'collision_passed':False,'timing_only_native_duration_s':{x['symmetry']:x['native_audit']['duration_s'] for x in stage if x['segment']=='lift'},'payload_collision_fully_validated':False,'execution_allowed':False},
  {'stage':'remaining130mm to total230mm','success':None,'status':'NOT_VALIDATED_AFTER_EARLIER_COLLISION_FAILURE','intended_hold230_body_xyz_m':[obs['target']['pose_m_rad'][0],obs['target']['pose_m_rad'][1],obs['target']['pose_m_rad'][2]+.23]}],
 'tcp_body':{'convention':'BODY XYZ metres; Euler roll/pitch/yaw degrees, Rz(yaw)Ry(pitch)Rx(roll); TCP +Z is gripper forward axis, Euler zero is not level-forward gripper','current_controller_derived':load(O/'current_tcp_body.json'),'current_model_fk':load(O/'start_tcp_body_model.json'),'normal_pregrasp':normal[0]['start'],'normal_grasp':normal[0]['end'],'normal_lift100':normal[1]['end'],'flipped':[{k:x[k] for k in ('segment','start','end')} for x in stage if x['symmetry']=='FLIPPED_180']},
 'collision_attribution':load(O/'collision-attribution.json'),
 'slow_contact_findings':{'historical_real_path':load(O/'historical_native_retiming.json'),'cause':'legacy whole-path global dilation amplifies worst dense-IK knot derivative discontinuity; contact cap0.05rad/s vs free-motion0.20rad/s; not slow robot feedback or cuRobo solve in the contact stage','retimer':'bounded cubic candidates plus same geometric validation; exact polyline fallback; caps unchanged','not_claimed':'No current collision-valid contact, no physical retiming commissioning, no grasp validation or total230mm planning acceptance'},
 'artifacts':{'root':str(O),'review_image':str(O/'current_pick_review.png'),'rc1_production_switched':False}}
(O/'REPORT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
files=[p for p in O.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
(O/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(O))+'\n' for p in sorted(files)))
print(O/'REPORT.json')
