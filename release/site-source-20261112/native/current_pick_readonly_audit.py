"""No hardware calls: current pose projection and frozen native retiming audit."""
import json,time,math,traceback
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.native_execution_package import package_native_preview
from ares_r.motion.short_motion import validate_short_motion
ROOT=Path('/home/yikun/ARES-R-RC1-20261019');OUT=ROOT/'worklog/evidence/2026-10-19-current-pick-rehearsal'
def load(p):return json.loads(p.read_text())
world=load(ROOT/'config/robot_world.json')
audit=load(OUT/'epoch/robot_state_before/right.json');d=audit['diagnostics']
base=world['arms']['right'];T=np.eye(4);T[:3,:3]=Rotation.from_euler('xyz',base['base_rpy_rad']).as_matrix();T[:3,3]=base['base_xyz_m']
tcp=d['tcp_position_mm_rad'];U=np.eye(4);U[:3,:3]=Rotation.from_euler('xyz',tcp[3:]).as_matrix();U[:3,3]=np.asarray(tcp[:3])/1000
B=T@U
pose={'frame':'BODY','xyz_m':B[:3,3].tolist(),'rpy_rad':Rotation.from_matrix(B[:3,:3]).as_euler('xyz').tolist(),'rpy_deg':Rotation.from_matrix(B[:3,:3]).as_euler('xyz',degrees=True).tolist(),'T_body_tcp':B.tolist(),'controller_tool':d.get('tool_data'),'physical_motion':False}
(OUT/'current_tcp_body.json').write_text(json.dumps(pose,indent=2)+'\n')
old=Path('/home/yikun/ARES-R/worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792142393480633163/pick_attempt_2_QUALITY')
package=load(old/'package/first_pick_execution_package.json');request=load(old/'pregrasp_plan/planner_request.json');site=load(ROOT/'config/jaka_mini2_motion.site.json');parameters=load(ROOT/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
records=[]
for segment in ('contact','lift'):
    points=package['trajectories'][segment];old_audit=load(old/('native/'+segment+'.audit.json'))
    def validator(rows):
        direction=request.get('goal_candidate_metadata',[{}])[0].get('approach_direction_body',[1,0,0]) if segment=='contact' else [0,0,1]
        return validate_short_motion(rows,request,segment=segment,observation_id=package['observation_id'],direction=direction,central_exclusion=False,contact_target_ids=[package['target_primitive_id']])
    record={'segment':segment,'kind':'OCT16_FROZEN_REAL_PATH_NOT_CURRENT_TARGET','old_duration_s':old_audit['duration_s'],'old_max_joint_speed_rad_s':old_audit['max_joint_speed_rad_s'],'points':len(points)}
    start=time.monotonic()
    try:
        _,new=package_native_preview(points,.008,site,tool_id=1,controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),speed_ceiling_rad_s=parameters['contact_velocity_rad_s'] if segment=='contact' else parameters['lift_velocity_rad_s'],accel_ceiling_rad_s2=parameters['contact_acceleration_rad_s2'] if segment=='contact' else parameters['lift_acceleration_rad_s2'],tracking_stop_threshold_deg=parameters['tracking_stop_deg'],max_excursion_rad=math.radians(220),retiming_policy='VERIFIED_SHORT_V1',geometry_validator=validator)
        record.update(success=True,new_audit=new)
    except Exception as e:record.update(success=False,error=str(e),traceback=traceback.format_exc())
    record['compute_wall_s']=time.monotonic()-start;records.append(record)
    (OUT/'historical_native_retiming.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ('new_audit','traceback')},ensure_ascii=False),flush=True)
print(json.dumps(pose,ensure_ascii=False))
