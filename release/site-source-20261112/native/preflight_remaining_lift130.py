"""Frozen-scene payload diagnostic only. No SDK, no sender, no network."""
import copy,json,os,time
from pathlib import Path
import numpy as np
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.motion.independent_path_validation import validate_dense_world
from ares_r.motion.tcp_orientation import validate_level_path
from ares_r.manipulation.attached_world import verify_world_identity

R=Path('/home/yikun/ARES-R-RC1-20261019')
O=Path(os.environ['ARES_R_REHEARSAL_DIR'])
if R/'worklog/evidence' not in O.parents:raise ValueError('isolated evidence required')
def load(p):return json.loads(p.read_text())
req=load(O/'pregrasp_plan/planner_request.json')
package=load(O/'preflight_package/first_pick_execution_package.json')
pre=load(O/'pregrasp_plan/contact_lift_precheck.json')
branch=next(x for x in pre['accepted'] if x['grasp_symmetry_id']=='NORMAL')
ik=RuntimeGoalIK(req['robot_yaml_urdf'],req['T_body_model'],req['T_link6_tcp'])
q=np.asarray(branch['prechecked_paths']['lift'][-1]);T=ik.fk(q);rows=[];at=time.monotonic()
for z in np.linspace(0,.13,66):
 solved=ik.solve_diagnostic(T[:3,3]+[0,0,z],T[:3,:3],q);q=np.asarray(solved.joints_rad);rows.append(q.tolist())
test=copy.deepcopy(req);payload=package['coarse_attached_object_collision'];object_id=payload['object_id']
test['attached_object_collision']=payload
test['compiled_scene']['attached_object_revision']=payload['revision']
removed=test['compiled_scene']['cuboids'].pop(object_id,None)
test['motion_constraints']=dict(test.get('motion_constraints',{}),attached_object_revision=payload['revision'],ignore_cuboid_ids=[])
verify_world_identity(test['compiled_scene'],payload)
proof=validate_dense_world(rows,test,subdivisions=4)
level=validate_level_path(ik.fk,rows,subdivisions=4,tolerance_deg=3.)
xyz=np.asarray([ik.fk(row)[:3,3] for row in rows])
result={'kind':'FROZEN_HYPOTHETICAL_POST100_PAYLOAD_LIFT130_DIAGNOSTIC',
 'physical_execution':False,'real_postgrasp_scan':False,'production_settings_changed':False,
 'start_xyz_m':T[:3,3].tolist(),'end_xyz_m':xyz[-1].tolist(),
 'max_horizontal_drift_m':float(np.linalg.norm(xyz[:,:2]-xyz[0,:2],axis=1).max()),
 'elapsed_s':time.monotonic()-at,'world_proof':proof,'level_proof':level,
 'payload_revision':payload['revision'],'payload_object_id':object_id,
 'only_exact_attached_identity_removed_from_world':removed is not None,
 'support_and_non_target_world_preserved':True,'operator_observation':'Above lift workspace reported empty; inactive left arm reported far on BODY left.',
 'result':'FROZEN_MODELED_WORLD_PASS' if proof['collision_free'] and level['passed'] else 'FROZEN_MODELED_WORLD_REJECTED',
 'execution_ready':False,'remaining':['fresh post100 observed state/scene','cuRobo free-lift trajectory and native packaging','physical payload verification']}
(O/'remaining_lift130_preflight.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('result','elapsed_s','start_xyz_m','end_xyz_m','max_horizontal_drift_m')} | {'limiting_object':proof['limiting_object_id'],'limiting_component':proof['limiting_robot_component_id'],'modeled_clearance_m':proof['min_clearance_m']}))
