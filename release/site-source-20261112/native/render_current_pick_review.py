"""Offline current-scene review: explicitly distinguish IK from valid plans."""
import json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.motion.independent_path_validation import _quaternion_rotation
R=Path('/home/yikun/ARES-R-RC1-20261019');O=R/'worklog/evidence/2026-10-19-current-pick-rehearsal'
def load(p):return json.loads(p.read_text())
q=load(O/'pregrasp_plan/planner_request.json');T=np.asarray(q['T_body_model']);ik=RuntimeGoalIK(q['robot_yaml_urdf'],T,q['T_link6_tcp']);pre=load(O/'pregrasp_plan/contact_lift_precheck.json')['accepted'][0]
cloud=np.load(O/'epoch2/live_scene/scene/clean_residual.npz')['points_body_m'];cloud=cloud[np.all((cloud>[-.1,-.8,.5])&(cloud<[1.7,.8,1.6]),axis=1)];cloud=cloud[::max(1,len(cloud)//10000)]
edges=[(a,b) for a in range(8) for b in range(a+1,8) if bin(a^b).count('1')==1]
def corners(v):
 rot=T[:3,:3]@_quaternion_rotation(v['pose'][3:]);c=T[:3,:3]@v['pose'][:3]+T[:3,3];d=np.asarray(v['dims'])/2
 return np.asarray([c+rot@(d*[x,y,z]) for x in (-1,1) for y in (-1,1) for z in (-1,1)])
fig,axes=plt.subplots(2,3,figsize=(18,11));fig.suptitle('CURRENT LIVE SCENE | NO MOTION | current-to-pregrasp REJECTED\nDashed contact/lift = IK-only, NOT collision-approved',fontsize=15)
for ax,(ia,ib,title) in zip(axes[0],[(1,0,'TOP (+Y left, +X forward)'),(1,2,'REAR (+Y left, +Z up)'),(0,2,'RIGHT SIDE (+X forward, +Z up)')]):
 ax.scatter(cloud[:,ia],cloud[:,ib],s=.4,c='#aaaaaa',alpha=.35)
 for name,box in q['compiled_scene']['cuboids'].items():
  highlighted=name in ('observed_remaining_structure_structure_001','observed_remaining_structure_structure_002','observed_support_02_support_surface_001','observed_support_02_support_surface_002')
  if not highlighted:continue
  v=corners(box)
  for a,b in edges:ax.plot(v[[a,b],ia],v[[a,b],ib],color='red',alpha=.7,lw=1)
 frames=arm_link_transforms(Path(q['robot_yaml_urdf']),q['start_rad']);joints=np.asarray([T[:3,3]]+[(T@frames['link%d'%i])[:3,3] for i in range(1,7)]+[ik.fk(q['start_rad'])[:3,3]])
 ax.plot(joints[:,ia],joints[:,ib],'-o',color='#1877bc',lw=2,markersize=4,label='current right arm')
 for name,color in [('contact','#d28b00'),('lift','#8a2be2')]:
  xyz=np.asarray([ik.fk(row)[:3,3] for row in pre['prechecked_paths'][name]])
  ax.plot(xyz[:,ia],xyz[:,ib],'--',color=color,lw=2,label=name+' IK only')
  ax.scatter(xyz[[0,-1],ia],xyz[[0,-1],ib],c=color,s=35)
 ax.set_title(title);ax.set_xlabel('BODY '+['X','Y','Z'][ia]+' [m]');ax.set_ylabel('BODY '+['X','Y','Z'][ib]+' [m]');ax.grid(alpha=.3);ax.set_aspect('equal',adjustable='box')
 if ia==1:ax.invert_xaxis()
 axes[0,0].legend(fontsize=8)
axes[1,0].barh(['Oct16 contact old','Oct16 contact retimed','Current contact estimate','Oct16 lift old','Oct16 lift retimed','Current lift estimate'],[115.04,16.72,17.04,72.16,15.36,15.12],color=['#999','#197','#da0','#999','#197','#da0']);axes[1,0].set_xlabel('Native trajectory duration [s]');axes[1,0].set_title('Same speed ceilings; current estimates NOT collision-approved')
for ax in axes[1,1:]:ax.axis('off')
axes[1,1].text(0,1,'PASS: ID1 detection, fresh cloud, stable state\nPASS: NORMAL / FLIPPED contact + lift IK\nFAIL: both pregrasp goals in modeled collision\nFAIL: gripper union vs non-target structures\nUNTESTED: actual close, hold, payload, execution\nNo obstacle deletion / speed changes / motion',va='top',fontsize=12,linespacing=1.7)
axes[1,2].text(0,1,'Current TCP BODY [m]\n[0.73150, +0.07750, 1.05816]\nPregrasp [m]\n[0.75163, -0.21198, 0.99161]\nGrasp [m]\n[0.80662, -0.21215, 0.99062]\nLift100 [m]\n[0.80662, -0.21215, 1.09062]',va='top',fontsize=12,linespacing=1.6)
fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(O/'current_pick_review.png',dpi=150)
