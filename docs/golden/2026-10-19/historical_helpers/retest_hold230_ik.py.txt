"""Hypothetical post-grasp IK only; no payload/collision or motion approval."""
import os,json,time,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019');O=Path(os.environ['ARES_R_REHEARSAL_DIR'])
req=json.load(open(O/'pregrasp_plan/planner_request.json'));pre=json.load(open(O/'pregrasp_plan/contact_lift_precheck.json'));ik=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp']);site=json.load(open(R/'config/jaka_mini2_motion.site.json'));rows=[]
ik.lower=np.maximum(ik.lower,np.asarray(site['lower_rad'])+site['soft_limit_margin_rad']);ik.upper=np.minimum(ik.upper,np.asarray(site['upper_rad'])-site['soft_limit_margin_rad'])
for branch in pre['accepted']:
 q=np.asarray(branch['prechecked_paths']['lift'][-1]);T=ik.fk(q);start=time.monotonic();samples=[]
 for z in np.linspace(0,.13,66):
  if time.monotonic()-start>10:raise RuntimeError('bounded IK deadline')
  result=ik.solve_diagnostic(T[:3,3]+[0,0,z],T[:3,:3],q);q=np.asarray(result.joints_rad)
  samples.append({'position_error_m':result.position_error_m,'orientation_error_rad':result.orientation_error_rad,'within_limits':bool(np.all(q>=ik.lower)&np.all(q<=ik.upper))})
 F=ik.fk(q);passed=all(x['within_limits'] and x['position_error_m']<=.0015 and x['orientation_error_rad']<=math.radians(.6) for x in samples)
 rows.append({'symmetry':branch['grasp_symmetry_id'],'passed':passed,'wall_s':time.monotonic()-start,'end_xyz_m':F[:3,3].tolist(),'end_rpy_deg':Rotation.from_matrix(F[:3,:3]).as_euler('xyz',degrees=True).tolist(),'max_position_error_m':max(x['position_error_m'] for x in samples),'collision_checked':False,'payload_validated':False,'curobo_free_lift_validated':False})
(O/'hold230_ik_only.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
