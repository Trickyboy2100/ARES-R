"""Frozen-data numerical reach study, no device adapters or motion."""
import json,time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
r=json.loads((O/'frozen-pregrasp-only-request.json').read_text())
s=RuntimeGoalIK(r['robot_yaml_urdf'],r['T_body_model'],r['T_link6_tcp'])
site=json.loads((R/'config/jaka_mini2_motion.site.json').read_text());margin=site['soft_limit_margin_rad']
s.lower=np.maximum(s.lower,np.array(site['lower_rad'])+margin);s.upper=np.minimum(s.upper,np.array(site['upper_rad'])-margin)
xyz=np.array(r['task_target_pose_body_m_rad'][:3]);rng=np.random.default_rng(21);rows=[];start=time.monotonic()
for meta,q in zip(r['goal_candidate_metadata'],r['goal_candidates_rad']):
 rot=np.array(meta['target_rotation_body']);seeds=[q,r['start_rad']]+[rng.uniform(s.lower+.001,s.upper-.001) for _ in range(12)]
 for lift in [0.,.23]:
  target=xyz+[0,0,lift];best=None
  for seed in seeds:
   def residual(q):
    p=s.fk(q);return np.r_[p[:3,3]-target,.18*Rotation.from_matrix(rot.T@p[:3,:3]).as_rotvec()]
   a=least_squares(residual,np.clip(seed,s.lower+1e-5,s.upper-1e-5),bounds=(s.lower,s.upper),max_nfev=180,xtol=1e-9,ftol=1e-9,gtol=1e-9)
   pose=s.fk(a.x);pos=float(np.linalg.norm(pose[:3,3]-target));ang=float(np.degrees(np.linalg.norm(Rotation.from_matrix(rot.T@pose[:3,:3]).as_rotvec())))
   row=dict(symmetry=meta['grasp_symmetry_id'],lift_m=lift,position_error_m=pos,orientation_error_deg=ang,joints_rad=a.x.tolist(),passed=pos<=.0015 and ang<=.6)
   if best is None or pos+.003*ang<best['position_error_m']+.003*best['orientation_error_deg']:best=row
   if row['passed']:break
  rows.append(best);print(json.dumps(best),flush=True)
result=dict(diagnostic_only=True,physical_motion=False,scene_modified=False,elapsed_s=time.monotonic()-start,rows=rows)
(O/'contact-reach-multiseed.json').write_text(json.dumps(result,indent=2)+'\n')
