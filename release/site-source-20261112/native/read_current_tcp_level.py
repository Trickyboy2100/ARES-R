"""Read current controller TCP only and evaluate full-SE3 BODY axes."""
import json,subprocess,math,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
R=Path('/home/yikun/ARES-R-RC1-20261019')
raw=subprocess.check_output([str(R/'native/jaka_right_rc1'),'snapshot'],cwd=R,text=True)
row=next(json.loads(x) for x in raw.splitlines() if x.startswith('{') and json.loads(x).get('event')=='snapshot')
base=json.loads((R/'config/robot_world.json').read_text())['arms']['right']
def T(x,r):
    t=np.eye(4);t[:3,:3]=Rotation.from_euler('xyz',r).as_matrix();t[:3,3]=x;return t
tcp=row['tcp_mm_rad'];body=T(base['base_xyz_m'],base['base_rpy_rad'])@T(np.asarray(tcp[:3])/1000,tcp[3:])
rotation=body[:3,:3]
forward_tilt=math.degrees(math.asin(min(1,abs(float(rotation[2,2])))))
finger_tilt=math.degrees(math.asin(min(1,abs(float(rotation[2,0])))))
out={'recorded_at_unix':time.time(),'sdk_snapshot':row,'T_body_tcp':body.tolist(),
 'xyz_body_m':body[:3,3].tolist(),'rpy_body_deg':Rotation.from_matrix(rotation).as_euler('xyz',degrees=True).tolist(),
 'tcp_forward_axis_body':rotation[:,2].tolist(),'finger_closing_axis_body':rotation[:,0].tolist(),
 'forward_axis_tilt_deg':forward_tilt,'finger_axis_tilt_deg':finger_tilt,
 'physical_forward_yaw_deg':math.degrees(math.atan2(rotation[1,2],rotation[0,2])),
 'level_within_3deg':max(forward_tilt,finger_tilt)<=3,
 'reference':'BODY configured Z; not an independent gravity measurement',
 'physical_motion':False}
p=R/'worklog/evidence/demo-runs/right_arm_grasp_place_roundtrip_v1/web_1792382763337808664/observer/current-tcp-level.json'
p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
