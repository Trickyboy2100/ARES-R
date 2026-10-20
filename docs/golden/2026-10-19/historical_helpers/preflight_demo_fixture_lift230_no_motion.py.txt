"""Validate one fresh frozen230mm lift and native text; no actuation."""
import json,time
from pathlib import Path
import numpy as np
from ares_r.manipulation.continuous_demo_lift import validate_path
from ares_r.motion.native_execution_package import package_native_preview,verify_installed_sender
import subprocess
R=Path('/home/yikun/ARES-R-RC1-20261019')
S=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792398755608150576'
O=S/'association10mm-preflight';O.mkdir(exist_ok=False)
def load(p):return json.loads(p.read_text())
def write(n,v):(O/n).write_text(json.dumps(v,indent=2)+'\n')
f=next(S.glob('pick_*'))
p=load(R/'native/reviewed_roundtrip_v12.json');request=load(f/'pregrasp_plan/planner_request.json')
package=load(f/'package/first_pick_execution_package.json');points=load(f/'continuous_lift230.json')['points_rad']
at=time.monotonic()
def validate(rows):return validate_path(rows,request,package,contact_escape=p['lift_lower_fixture_contact_escape'])
try:
    sender=Path(p['contact_sender']);verify_installed_sender(sender)
    text,audit=package_native_preview(points,.008,load(R/'config/jaka_mini2_motion.site.json'),tool_id=1,
        controller_tool_pose_mm_rad=request['controller_tool_pose_mm_rad'],captured_at_unix=time.time(),
        speed_ceiling_rad_s=p['lift_velocity_rad_s'],accel_ceiling_rad_s2=p['lift_acceleration_rad_s2'],
        tracking_stop_threshold_deg=p['tracking_stop_deg'],max_excursion_rad=np.deg2rad(220),
        retiming_policy='VERIFIED_SHORT_V1',geometry_validator=validate)
    proof=audit['source_geometry_validation'];write('geometry-preflight.json',proof)
    native=O/'lift230.native.txt';native.write_text(text);write('native-audit.json',audit)
    v=subprocess.run([str(sender),'validate-supervised-path',str(native)],cwd=R,capture_output=True,text=True,timeout=20)
    (O/'native-validate.log').write_text(v.stdout+v.stderr)
    if v.returncode:raise RuntimeError('native validate-only failed')
    report={'LIFT230_DEMO_PRECHECK_PASS':True,'physical_motion':False,'full_cycle_ready':False,
        'single_native_stream':True,'wall_s':time.monotonic()-at,'native_duration_s':audit['duration_s'],
        'geometry_proof':proof,'policy_revision':p['lift_lower_fixture_contact_escape']['revision'],
        'source_scene_snapshot_id':request['scene_snapshot_id'],'source_pointcloud_sha256':package['pointcloud_sha256']}
    write('REPORT.json',report);print(json.dumps(report),flush=True)
except BaseException as e:
    write('FAULT.json',{'error':str(e),'physical_motion':False,'wall_s':time.monotonic()-at});raise
