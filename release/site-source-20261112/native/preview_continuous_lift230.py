"""Frozen real-scene continuous230mm planning/native validation; no hardware."""
import json,time,subprocess
from pathlib import Path
import numpy as np
from ares_r.manipulation.continuous_demo_lift import build_path,validate_path
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
R=Path('/home/yikun/ARES-R-RC1-20261019');S=R/'worklog/evidence/20261019-grasp-from-center-frozen-repack-fixed'
O=R/'worklog/evidence/20261019-continuous-lift230-no-motion'
def load(p):return json.loads(p.read_text())
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
def main():
    O.mkdir(parents=True,exist_ok=False);at=time.monotonic()
    p=load(R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json')
    package=load(S/'package/first_pick_execution_package.json');request=load(S/'pregrasp_plan/planner_request.json')
    points=build_path(package,request);write('points.json',points)
    validation=validate_path(points,request,package);write('geometry-validation.json',validation)
    text,audit=package_native_preview(points,.008,load(R/'config/jaka_mini2_motion.site.json'),
        tool_id=1,controller_tool_pose_mm_rad=package['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
        speed_ceiling_rad_s=p['lift_velocity_rad_s'],accel_ceiling_rad_s2=p['lift_acceleration_rad_s2'],
        tracking_stop_threshold_deg=p['tracking_stop_deg'],max_excursion_rad=np.deg2rad(220),
        retiming_policy='VERIFIED_SHORT_V1',geometry_validator=lambda q:validate_path(q,request,package))
    native=O/'lift230.native.txt';native.write_text(text);write('native-audit.json',audit)
    sender=Path(p['contact_sender']);verify_installed_sender(sender)
    with (O/'sender-validate.log').open('x') as stream:subprocess.run([str(sender),'validate-supervised-path',str(native)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=20)
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    report={'planning_only':True,'physical_execution':False,'single_native_stream':True,'servo_enable_count_when_executed':1,
        'no_stop_at100mm':True,'geometry_validation_passed':True,'native_validation_passed':True,
        'source_scene_snapshot_id':request['scene_snapshot_id'],'source_package_sha256':package['package_sha256'],
        'start_xyz_body_m':ik.fk(points[0])[:3,3].tolist(),'end_xyz_body_m':ik.fk(points[-1])[:3,3].tolist(),
        'duration_s':audit['duration_s'],'max_joint_speed_rad_s':audit['max_joint_speed_rad_s'],
        'max_joint_accel_rad_s2':audit['max_joint_accel_rad_s2'],'native_file_sha256':audit['native_file_sha256'],
        'wall_s':time.monotonic()-at,'new_full_lift_physical_commissioned':False}
    write('REPORT.json',report);print(json.dumps(report),flush=True)
try:main()
except BaseException as e:
    if O.exists():write('FAULT.json',{'error':str(e),'physical_execution':False})
    raise
