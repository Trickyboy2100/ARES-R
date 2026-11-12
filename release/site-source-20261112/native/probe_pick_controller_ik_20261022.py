"""Read-only controller IK/FK crosscheck, never sends joint or gripper motion."""
import json,sys,time,math
from pathlib import Path
R=Path('/home/yikun/ARES-R-RC1-20261019');sys.path[:0]=[str(R/'src'),str(R/'scripts')]
from ares_r.adapters.jaka_sdk import JakaSdkArm,_value
from ares_r.world_geometry import load_world_geometry,base_tcp_to_world
from design_named_poses import matrix_rpy,world_to_controller
O=R/'worklog/evidence/20261022-pick-reset-timing'
cfg=json.loads((R/'config/system.json').read_text());obs=json.loads((O/'epoch-retry/manipulation_observation.json').read_text());check=json.loads((O/'preparation-retry/contact_lift_precheck.json').read_text());world=load_world_geometry(Path(cfg['world_geometry_file']))
arm=JakaSdkArm('right',cfg['jaka']['arms']['right'],cfg['jaka']);rows=[];at=time.monotonic()
try:
 q=list(_value(arm.robot.get_joint_position(),'current joints'))
 seeds=[q,[0]*6]
 for symmetry in ('NORMAL','FLIPPED_180'):
  rot=next(b['target_rotation_body'] for b in check['branches'] if b['symmetry_id']==symmetry)
  xyz=obs['target']['pose_m_rad'][:3];direction=[rot[i][2] for i in range(3)]
  for label,point in [('PREGRASP',[v-.055*d for v,d in zip(xyz,direction)]),('GRASP',xyz),('LIFT230',[xyz[0],xyz[1],xyz[2]+.23])]:
   pose=point+matrix_rpy(rot);controller=world_to_controller(world['arms']['right'],pose);attempts=[]
   for seed in seeds:
    t=time.monotonic();result=arm.robot.kine_inverse(seed,controller);row=dict(code=int(result[0]),elapsed_s=time.monotonic()-t)
    if int(result[0])==0:
     row['joints_rad']=list(result[1]);fk=list(_value(arm.robot.kine_forward(row['joints_rad']),'candidate FK'));body=base_tcp_to_world(world['arms']['right'],fk);row['sdk_fk_body']=body;row['position_error_m']=math.sqrt(sum((a-b)**2 for a,b in zip(body[:3],point)))
    attempts.append(row)
    if row['code']==0 and row['position_error_m']<=.0015:break
   rows.append(dict(symmetry=symmetry,stage=label,controller_target_mm_rad=controller,body_target=pose,attempts=attempts));print(json.dumps(rows[-1]),flush=True)
finally:arm.close()
(O/'controller-ik-crosscheck-multiseed.json').write_text(json.dumps(dict(physical_motion=False,method='read-only controller kine_inverse and kine_forward',elapsed_s=time.monotonic()-at,rows=rows),indent=2)+'\n')
