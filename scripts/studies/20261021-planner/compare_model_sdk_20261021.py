"""Compare frozen live SDK center TCP to pinned FK, no hardware access."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/20261021-center-grasp-planner-study'
r=json.loads((O/'frozen-pregrasp-only-request.json').read_text());a=json.loads((O/'after-center.json').read_text())['arms']['right']
s=RuntimeGoalIK(r['robot_yaml_urdf'],r['T_body_model'],r['T_link6_tcp']);model=s.fk(a['joints_rad']);sdk=np.array(a['T_body_tcp'])
result=dict(model_body_tcp=model.tolist(),sdk_body_tcp=sdk.tolist(),position_delta_m=(model[:3,3]-sdk[:3,3]).tolist(),position_error_m=float(np.linalg.norm(model[:3,3]-sdk[:3,3])),rotation_error_deg=float(np.degrees(np.linalg.norm(Rotation.from_matrix(model[:3,:3].T@sdk[:3,:3]).as_rotvec()))),hardware_access=False)
(O/'model-sdk-center-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
