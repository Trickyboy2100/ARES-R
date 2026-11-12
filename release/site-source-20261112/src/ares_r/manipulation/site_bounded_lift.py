"""Additive continuous lift IK with the exact Native site margin at solve time."""
import math
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK

def solve_site_bounded_lift(package,request,site):
    ik=RuntimeGoalIK(request['robot_yaml_urdf'],request['T_body_model'],request['T_link6_tcp'])
    soft=float(site['soft_limit_margin_rad']);reserve=math.radians(.02)
    ik.lower=np.maximum(ik.lower,np.asarray(site['lower_rad'])+soft+reserve)
    ik.upper=np.minimum(ik.upper,np.asarray(site['upper_rad'])-soft-reserve)
    q=np.asarray(package['trajectories']['contact'][-1],dtype=float)
    if np.any(q<ik.lower) or np.any(q>ik.upper):raise ValueError('grasp itself outside Native site margin')
    grasp=ik.fk(q);rows=[q.tolist()];errors=[]
    for h in np.linspace(.002,.230,115):
        answer=ik.solve(grasp[:3,3]+np.array([0,0,h]),grasp[:3,:3],q)
        q=np.asarray(answer.joints_rad);rows.append(q.tolist())
        errors.append(dict(position_m=answer.position_error_m,rotation_rad=answer.orientation_error_rad))
    data=np.asarray(rows)
    return rows,dict(site_margin_rad=soft,numerical_reserve_rad=reserve,
        effective_lower_rad=ik.lower.tolist(),effective_upper_rad=ik.upper.tolist(),
        minimum_remaining_margin_rad=np.minimum(data-ik.lower,ik.upper-data).min(axis=0).tolist(),
        max_position_residual_m=max(v['position_m'] for v in errors),
        max_orientation_residual_deg=math.degrees(max(v['rotation_rad'] for v in errors)),
        source='constrained IK; no clipping of an executed/planned joint path',site_limits_changed=False)
