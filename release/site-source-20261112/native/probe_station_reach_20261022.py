"""Frozen-only reach sensitivity, not a navigation recommendation or motion."""
import json,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261022-pick-reset-timing'
p=json.loads((R/'demos/right_arm_grasp_place_roundtrip_v1/parameters.json').read_text());request=json.loads((R/p['template_plan']/'planner_request.json').read_text());obs=json.loads((O/'epoch-retry/manipulation_observation.json').read_text());check=json.loads((O/'preparation-retry/contact_lift_precheck.json').read_text());s=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp']);lim=json.loads((R/'config/jaka_mini2_motion.site.json').read_text());s.lower=np.maximum(s.lower,np.array(lim['lower_rad'])+lim['soft_limit_margin_rad']);s.upper=np.minimum(s.upper,np.array(lim['upper_rad'])-lim['soft_limit_margin_rad']);seeds=[request['goal_rad'],obs['robot_state_after']['right']['diagnostics']['joint_position_rad']];xyz=np.array(obs['target']['pose_m_rad'][:3]);rows=[];at=time.monotonic()
for name,delta,compensation_delta in [('CURRENT',0.,0.),('VIRTUAL_FORWARD20MM',.02,0.),('VIRTUAL_FORWARD40MM',.04,0.),('VIRTUAL_FORWARD60MM',.06,0.),('DIAGNOSTIC_REMOVE_COMPENSATION',0.,10.)]:
 for symmetry in ('NORMAL','FLIPPED_180'):
  rot=np.array(next(b['target_rotation_body'] for b in check['branches'] if b['symmetry_id']==symmetry));rot=rot@Rotation.from_rotvec([0,0,np.radians(compensation_delta)]).as_matrix();best=None
  for seed in seeds:
   a=s.solve_diagnostic(xyz-[delta,0,0],rot,seed);row=dict(case=name,symmetry=symmetry,position_error_m=a.position_error_m,orientation_error_deg=float(np.degrees(a.orientation_error_rad)),joints_rad=list(a.joints_rad),passed=bool(a.position_error_m<=.0015 and a.orientation_error_rad<=np.radians(.6)))
   if best is None or row['position_error_m']<best['position_error_m']:best=row
   if row['passed']:break
  rows.append(best);print(json.dumps(best),flush=True)
(O/'reach-sensitivity.json').write_text(json.dumps(dict(physical_motion=False,parameters_modified=False,scope='DIAGNOSTIC_ENDPOINT_ONLY_NOT_EXECUTION_APPROVAL',elapsed_s=time.monotonic()-at,rows=rows),indent=2)+'\n')
