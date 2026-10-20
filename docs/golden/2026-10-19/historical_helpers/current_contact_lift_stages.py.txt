"""Offline stage diagnostics. Kinematic timing is not collision approval."""
from pathlib import Path
import json,time,math,traceback,os
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.motion.short_motion import validate_short_motion
from ares_r.motion.tcp_orientation import validate_level_path
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-current-pick-rehearsal'
O=Path(os.environ.get('ARES_R_REHEARSAL_DIR',str(O)))
if R/'worklog/evidence' not in O.parents:raise ValueError('isolated evidence directory required')
def load(p):return json.loads(p.read_text())
req=load(O/'pregrasp_plan/planner_request.json');obs=load(O/'epoch2/manipulation_observation.json');site=load(R/'config/jaka_mini2_motion.site.json');params=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
ik=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp'])
precheck=load(O/'pregrasp_plan/contact_lift_precheck.json');records=[]
def pose(q):
 T=ik.fk(q);return {'xyz_m':T[:3,3].tolist(),'rpy_deg':Rotation.from_matrix(T[:3,:3]).as_euler('xyz',degrees=True).tolist(),'T_body_tcp':T.tolist()}
for branch in precheck['accepted']:
 for segment in ('contact','lift'):
  q=branch['prechecked_paths'][segment];direction=branch['approach_direction_body'] if segment=='contact' else [0,0,1]
  record={'symmetry':branch['grasp_symmetry_id'],'segment':segment,'start':pose(q[0]),'end':pose(q[-1]),'physical_execution':False,'full_collision_validation':False}
  start=time.monotonic()
  def full(rows):return validate_short_motion(rows,req,segment=segment,observation_id=obs['observation_id'],direction=direction,contact_target_ids=req['motion_constraints']['ignore_cuboid_ids'])
  try:record['collision_proof']=full(q);record['full_collision_validation']=True
  except Exception as e:record['collision_error']=str(e)
  record['collision_validation_wall_s']=time.monotonic()-start
  anchor=ik.fk(q[0])[:3,3];end=ik.fk(q[-1])[:3,3];axis=end-anchor;length=np.linalg.norm(axis);axis/=length
  def kinematic(rows):
   level=validate_level_path(ik.fk,rows,subdivisions=4,tolerance_deg=3.)
   xyz=np.asarray([ik.fk(p)[:3,3] for p in rows]);along=(xyz-anchor)@axis
   off=np.linalg.norm(xyz-anchor-along[:,None]*axis,axis=1)
   passed=level['passed'] and max(off)<=.0015 and min(along)>=-.0015 and max(along)<=length+.0015
   return {'passed':bool(passed),'orientation':level,'max_off_axis_m':float(max(off)),'collision_checked':False,'timing_diagnostic_only':True}
  args=dict(tool_id=1,controller_tool_pose_mm_rad=req['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),speed_ceiling_rad_s=params['contact_velocity_rad_s'] if segment=='contact' else params['lift_velocity_rad_s'],accel_ceiling_rad_s2=params['contact_acceleration_rad_s2'] if segment=='contact' else params['lift_acceleration_rad_s2'],tracking_stop_threshold_deg=params['tracking_stop_deg'],max_excursion_rad=math.radians(220))
  start=time.monotonic()
  try:
   _,audit=package_native_preview(q,.008,site,retiming_policy='VERIFIED_SHORT_V1',geometry_validator=full if record['full_collision_validation'] else kinematic,**args)
   record['native_audit']=audit;record['timing_estimate_collision_approved']=record['full_collision_validation']
  except Exception as e:record['native_error']=str(e)
  record['native_build_wall_s']=time.monotonic()-start
  records.append(record);(O/'current_stage_diagnostics.json').write_text(json.dumps(records,indent=2)+'\n')
  print(json.dumps({'symmetry':record['symmetry'],'segment':segment,'collision':record['full_collision_validation'],'error':record.get('collision_error'),'duration_s':record.get('native_audit',{}).get('duration_s'),'compute_s':record['native_build_wall_s']}),flush=True)
(O/'start_tcp_body_model.json').write_text(json.dumps(pose(req['start_rad']),indent=2)+'\n')
