"""Render exact frozen planner collision evidence. No hardware/network I/O."""
import json,itertools
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from ares_r.perception.robot_collision import arm_link_transforms
from ares_r.perception.robot_owned_filter import grid_spheres_local
from ares_r.motion.independent_path_validation import _quaternion_rotation,validate_dense_world
R=Path('/home/yikun/ARES-R-RC1-20261019')
O=R/'worklog/evidence/20261019-place-collision-explained';O.mkdir(exist_ok=False)
P=R/'worklog/evidence/scene-aware-motion/PLAN_6a461e93d9544b8e8ed80cd4c686d0f5/planner_request.json'
r=json.loads(P.read_text());a=r['attached_object_collision'];body=np.asarray(r['T_body_model'])
frames=arm_link_transforms(r['robot_yaml_urdf'],r['start_rad']);L=body@frames['link6']
points=np.load(R/'worklog/evidence/scene-aware-motion/scene_20261019T095258Z_fc7b11b0/scene/clean_residual.npz')['points_body_m']
proof=validate_dense_world([r['start_rad']]*2,r,subdivisions=2)
name=proof['limiting_object_id'];raw=r['compiled_scene']['cuboids'][name]
def compiled_box(b):return body[:3,:3]@np.asarray(b['pose'][:3])+body[:3,3],body[:3,:3]@_quaternion_rotation(b['pose'][3:]),np.asarray(b['dims'])/2
red=compiled_box(raw)
yellow=(L[:3,:3]@np.asarray(a['link6_aabb']['center_m'])+L[:3,3],L[:3,:3],np.asarray(a['link6_aabb']['dims_m'])/2)
obj=L@np.asarray(a['T_link6_object']);purple=(obj[:3,3],obj[:3,:3],np.asarray(a['object_dimensions_m'])/2+a['inflation_m'])
signs=np.asarray(list(itertools.product((-1,1),repeat=3)))
edges=[(i,j) for i in range(8) for j in range(i+1,8) if np.sum(signs[i]!=signs[j])==1]
def corners(b):c,rot,h=b;return signs*h@rot.T+c
def draw_box(ax,b,color,label=None,lw=1.4,alpha=1.):
    v=corners(b)
    for index,(i,j) in enumerate(edges):ax.plot(*v[[i,j]].T,color=color,lw=lw,alpha=alpha,label=label if index==0 else None)
spheres=grid_spheres_local(a['link6_aabb'],float(r['planning_parameters'].get('active_sphere_cell_m',.035)))
centers=np.asarray([s['center'] for s in spheres])@L[:3,:3].T+L[:3,3];radii=np.asarray([s['radius'] for s in spheres])
local=(centers-red[0])@red[1];delta=np.abs(local)-red[2]
gap=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(1),0)-radii
k=int(np.argmin(gap));spherecenter=centers[k];radius=radii[k]
nearbox=np.clip(local[k],-red[2],red[2])@red[1].T+red[0]
inside_red=np.all(np.abs((points-red[0])@red[1])<=red[2]+1e-6,axis=1)
inside_obj=np.all(np.abs((points-purple[0])@purple[1])<=purple[2],axis=1)
delta=np.abs((points-purple[0])@purple[1])-purple[2]
pointgap=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(1),0)
report={'source_request':str(P),'scene_snapshot_id':r['scene_snapshot_id'],'frozen_not_current_live_scene':True,
    'limiting_object_id':name,'limiting_robot_component':proof['limiting_robot_component_id'],
    'modeled_sphere_box_gap_mm':float(gap[k]*1000),'points_inside_padded_object_obb':int(inside_obj.sum()),
    'minimum_point_to_padded_object_obb_mm':float(pointgap.min()*1000),
    'limiting_world_box_body_center_m':red[0].tolist(),'limiting_world_box_dimensions_m':(red[2]*2).tolist(),
    'link6_aabb_dimensions_m':a['link6_aabb']['dims_m'],'object_dimensions_m':a['object_dimensions_m'],
    'inflation_m':a['inflation_m'],'limiting_sphere_radius_mm':float(radius*1000),'observed_points_inside_limiting_world_box':int(inside_red.sum()),
    'collision_is_model_overlap_not_proof_of_physical_contact':True}
(O/'diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
fig=plt.figure(figsize=(22,13));targets=[(25,-55,'BODY 3D overview',False),(90,-90,'TOP: X forward, Y left',True),(0,-90,'REAR: Y horizontal, Z up',True),(0,0,'SIDE: X horizontal, Z up',True),(27,-38,'Detail: exact sphere vs obstacle',True)]
mid=(purple[0]+red[0])/2
for i,(el,az,title,zoom) in enumerate(targets):
    ax=fig.add_subplot(2,3,i+1,projection='3d')
    pts=points[np.linalg.norm(points-mid,axis=1)<(.32 if zoom else 2.)]
    ax.scatter(*pts[::max(1,len(pts)//12000)].T,s=3,c='#77828c',alpha=.5,label='retained measured BODY points')
    if inside_red.any():ax.scatter(*points[inside_red].T,s=16,c='#d52124',label='points enclosed by red primitive')
    draw_box(ax,yellow,'#bc8a00','planner link6 AABB',1.5)
    draw_box(ax,purple,'#9c38c1','same padded object OBB',2.)
    draw_box(ax,red,'#df2028','limiting environment primitive',2.5)
    u,v=np.mgrid[0:2*np.pi:26j,0:np.pi:15j]
    ax.plot_wireframe(spherecenter[0]+radius*np.cos(u)*np.sin(v),spherecenter[1]+radius*np.sin(u)*np.sin(v),spherecenter[2]+radius*np.cos(v),color='#008c9e',alpha=.65,lw=.55)
    ax.plot(*np.array([spherecenter,nearbox]).T,color='#111111',lw=2,label='limiting sphere/box pair')
    tcp=body@frames['link6']@np.asarray(r['T_link6_tcp']);ax.scatter(*tcp[:3,3],s=50,c='#1a9b3c',label='TCP')
    if not zoom:
        joints=np.array([(body@frames[n])[:3,3] for n in ('base_link','link1','link2','link3','link4','link5','link6')])
        ax.plot(*joints.T,color='#315e9d',lw=3,label='right arm joint chain')
        for objid,b in r['compiled_scene']['cuboids'].items():
            if objid!=name and ('support_surface' in objid or objid.startswith('known_')):draw_box(ax,compiled_box(b),'#999999',lw=.45,alpha=.22)
        ax.set_xlim(0,1.25);ax.set_ylim(-.65,.35);ax.set_zlim(.7,1.65)
    else:
        ax.set_xlim(mid[0]-.22,mid[0]+.22);ax.set_ylim(mid[1]-.22,mid[1]+.22);ax.set_zlim(mid[2]-.22,mid[2]+.22)
    ax.set_box_aspect((1,1,1));ax.view_init(el,az);ax.set_title(title);ax.set_xlabel('BODY X / m');ax.set_ylabel('BODY Y / m');ax.set_zlabel('BODY Z / m')
    if i==0:ax.legend(loc='upper left',fontsize=7)
ax=fig.add_subplot(2,3,6);ax.axis('off')
text=('EXACT FROZEN FAILURE - NOT A NEW LIVE SCAN\n\n'
      f'World object: {name}\nRobot component: attached_object\n\n'
      f'Sphere / inflated cuboid gap: {gap[k]*1000:.2f} mm\n'
      f'Planner sphere radius: {radius*1000:.2f} mm\n'
      f'Points INSIDE padded object OBB: {inside_obj.sum()}\n'
      f'Closest point to padded OBB: {pointgap.min()*1000:.2f} mm\n\n'
      'YELLOW = extra empty volume of link6 AABB\nPURPLE = oriented object, same size + 4mm padding\nCYAN = one circumscribed planner sphere\nRED = one retained environment collision cuboid\nGRAY = actual retained point measurements\n\n'
      'A negative model gap is NOT proof of physical contact.\n'
      'No point deletion or safety threshold change was used.\n'
      'Inspect OBB, spheres, point-level geometry separately.')
ax.text(0,1,text,va='top',fontsize=11,family='monospace',linespacing=1.5)
fig.suptitle('ARES-R PLACE failure: what the planner actually checked',fontsize=18)
fig.tight_layout(rect=(0,0,1,.96));fig.savefig(O/'collision-explained.png',dpi=150);plt.close(fig)
print(json.dumps({'image':str(O/'collision-explained.png'),'diagnosis':report}),flush=True)
