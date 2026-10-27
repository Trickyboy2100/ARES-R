#!/usr/bin/env python3
"""Render evidence panels from computed arrays/receipts; no hardware operations."""
import argparse,hashlib,json,sys,math,subprocess,textwrap,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,FancyBboxPatch,FancyArrowPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection,Line3DCollection
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from replay_rasc import load,save,sha,digest
from matplotlib import font_manager
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
CJK=font_manager.FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').get_name()
plt.rcParams.update({'font.family':['DejaVu Sans',CJK],'font.size':14,'axes.titlesize':20,'axes.labelsize':15,'legend.fontsize':12,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
COLORS={'SUPPORT_SURFACE':'#298c7a','PROTRUDING_OBSTACLE':'#ce6345','STRUCTURE':'#597cba','UNKNOWN_OCCUPIED':'#9674aa'}
class Renderer:
 def __init__(self,a):self.a=a;self.out=a.output;self.manifest=[];self.metrics=load(a.output/'runlogs/rasc_stage_metrics.json');self.arr=np.load(a.private/'rasc_arrays.npz');self.new=load(a.private/'refined.json')['primitives'];self.old=load(a.private/'old.json');self.geometry=load(a.private/'geometry.json');self.report=load(a.private/'reference_report.json');self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 def finish(self,fig,name,title,sub,kind='FROZEN_REPLAY',source=None,svg=True,limits=None):
  fig.suptitle(title,x=.055,y=.975,ha='left',fontsize=23,weight='bold');fig.text(.055,.913,sub,fontsize=13,color='#435266',va='top');fig.text(.055,.025,textwrap.fill(kind+'  |  '+(limits or 'OFFLINE • NO PHYSICAL MOTION • observed space only'),155),fontsize=10,color='#485567');fig.subplots_adjust(left=.085,right=.95,bottom=.14,top=.79)
  if name.startswith(('rasc6/','geometry_ab/','planning/')):fig.text(.95,.08,'VIEW: BODY −Y → +Y  |  TOP: −Y bottom',ha='right',fontsize=10,color='#435266')
  path=self.out/'panels'/name;path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path.with_suffix('.png'),dpi=200,facecolor='white')
  if svg:fig.savefig(path.with_suffix('.svg'),facecolor='white')
  plt.close(fig)
  stage_index=int(Path(name).name[:2])-1 if name.startswith('rasc6/') else None
  for suffix in ['.png']+(['.svg'] if svg else []):
   p=path.with_suffix(suffix);self.manifest.append(dict(asset_id=str(Path(name).with_suffix(suffix)).replace('/','_'),path=str(p.relative_to(self.out)),source_kind=kind,experiment_id='OCT10_RASC' if kind=='FROZEN_REPLAY' else name,source_artifact_sha256=source or self.metrics['source_camera_sha256'],scene_snapshot_id=self.metrics['scene_snapshot_id'] if kind=='FROZEN_REPLAY' else None,robot_state_hash=self.metrics['robot_state_hash'] if kind=='FROZEN_REPLAY' else None,tool_calibration_revision=self.metrics['tool_calibration_revision'] if kind=='FROZEN_REPLAY' else None,title=title,repo_commit=self.commit,generation_script='tools/presentation_evidence/render_assets.py',generation_params={'fixed_3d_bounds_m':[[-.05,-.8,.65],[1.35,.8,1.6]],'dpi':200,'camera':{'ISO':[24,-110],'FRONT':[0,-90],'TOP':[90,-90]},'view_convention':'BODY -Y toward +Y; TOP keeps -Y at bottom'},input_count=self.metrics['counts'][stage_index][0] if stage_index is not None else None,output_count=self.metrics['counts'][stage_index][1] if stage_index is not None else None,runtime_ms=self.metrics['median_ms'][stage_index] if stage_index is not None else None,safety_constraints_digest=None,interpretation_limit=limits or sub,public_release_approved=True,sha256=sha(p)))
 def figure(self):return plt.figure(figsize=(12.8,7.2))
 def ax3(self,fig,view='ISO',bounds=None):
  ax=fig.add_subplot(111,projection='3d');lo,hi=np.asarray(bounds or [[-.05,-.8,.65],[1.35,.8,1.6]])
  ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),zlim=(lo[2],hi[2]),xlabel='BODY X [m]',ylabel='BODY Y [m]',zlabel='BODY Z [m]');ax.set_box_aspect(hi-lo);ax.set_proj_type('ortho');ax.view_init(*{'ISO':(24,-110),'TOP':(90,-90),'FRONT':(0,-90)}[view]);ax.tick_params(labelsize=11);
  if view=='FRONT':ax.set_yticks([]);ax.set_ylabel('')
  if view=='TOP':ax.set_zticks([]);ax.set_zlabel('')
  ax.xaxis.pane.fill=False;ax.yaxis.pane.fill=False;ax.zaxis.pane.fill=False;return ax
 def points(self,ax,p,c='#647785',label='Observed points',s=1.0):
  p=np.asarray(p);p=p[::max(1,math.ceil(len(p)/65000))]
  if len(p):ax.scatter(*p.T,s=s,c=c,alpha=.58,depthshade=False,label=label,rasterized=True)
 def boxes(self,ax,boxes,color='#ce6345',alpha=.06,padding=.0,robot=False):
  segments=[];faces=[]
  for b in boxes:
   center=np.asarray(b['center_body_m'] if robot else b['center_m']);dims=2*np.asarray(b['half_extents_m']) if robot else np.asarray(b['dims_m'])+2*padding;rot=np.asarray(b.get('rotation_body',np.eye(3))) if robot else np.eye(3)
   corners=np.array([center+rot@(dims*np.array([x,y,z])/2) for x in [-1,1] for y in [-1,1] for z in [-1,1]])
   for i in range(8):
    for j in range(i+1,8):
     if bin(i^j).count('1')==1:segments.append([corners[i],corners[j]])
   for ids in [[0,1,3,2],[4,5,7,6],[0,1,5,4],[2,3,7,6],[0,2,6,4],[1,3,7,5]]:faces.append(corners[ids])
  if faces:ax.add_collection3d(Poly3DCollection(faces,facecolor=color,alpha=alpha,edgecolors='none'))
  if segments:ax.add_collection3d(Line3DCollection(segments,colors=color,linewidths=.55,alpha=.65))
 def rasc(self):
  titles=['原始有效点云保留真实扫描缺口','ROI与7.5mm采样压缩观测规模','同帧机器人几何剔除已归属点','高度、法向与连通分组产生几何角色','多基元保留清理后的全部观测','正式SceneCompiler完成BODY→右臂坐标编译']
  names=['01_raw_cloud','02_roi','03_robot_owned_filter','04_support_decomposition','05_multi_primitive','06_curobo_world'];m=self.metrics
  for view in ['ISO','TOP','FRONT']:
   for i,name in enumerate(names):
    fig=self.figure();ax=self.ax3(fig,view)
    if i==0:self.points(ax,self.arr['body'],label='Valid measured BODY cloud')
    elif i==1:self.points(ax,self.arr['roi'],label='ROI / first point per 7.5mm voxel')
    elif i==2:
     self.points(ax,self.arr['external'],label='Retained external');self.points(ax,self.arr['removed'],c='#d45348',label='Removed: modeled robot ownership',s=4);self.boxes(ax,self.geometry['boxes'],color='#667485',alpha=.025,robot=True)
    elif i==3:
     remaining=np.ones(len(self.arr['clean']),bool)
     for semantic in COLORS:
      mask=np.zeros(len(remaining),bool)
      for b in self.new:
       if b['semantic']==semantic:mask|=np.all(np.abs(self.arr['clean']-b['center_m'])<=np.asarray(b['dims_m'])/2+1e-9,axis=1)
      mask&=remaining;remaining&=~mask;self.points(ax,self.arr['clean'][mask],COLORS[semantic],semantic,s=6)
    else:
     self.points(ax,self.arr['clean'],s=3)
     if i==4:
      for semantic,c in COLORS.items():self.boxes(ax,[b for b in self.new if b['semantic']==semantic],c,alpha=.06,padding=.007)
     else:
      from ares_r.motion.independent_path_validation import _quaternion_rotation
      compiled=load(self.a.private/'new_compiled.json');T=np.asarray(self.report['T_body_model']);backprojected=[]
      for key,b in compiled['cuboids'].items():
       center=T[:3,:3]@np.asarray(b['pose'][:3])+T[:3,3];rotation=T[:3,:3]@_quaternion_rotation(b['pose'][3:]);backprojected.append(dict(center_body_m=center,half_extents_m=np.asarray(b['dims'])/2,rotation_body=rotation))
      self.boxes(ax,backprojected,color='#298c7a',alpha=.04,robot=True)
     if i==5:
      # Actual compiler outputs are inverse-projected to BODY for a fixed-view comparison.
      self.boxes(ax,self.geometry['boxes'],color='#4d667b',alpha=.035,robot=True)
      body_model=np.asarray(self.report['T_body_model']);origin=body_model[:3,3]
      for k,c in enumerate(['#ce6345','#298c7a','#597cba']):ax.plot(*np.array([origin,origin+.17*body_model[:3,k]]).T,color=c,lw=3)
      ax.text(*origin,'Right model frame',fontsize=10)
    ax.legend(loc='upper left',bbox_to_anchor=(-.25,1.02),frameon=False,fontsize=10)
    extra=f" | K={m['new_k']}" if i==4 else (f" | K_world={m['k_curobo_obstacles']}" if i==5 else '')
    sub=f"10 Oct frozen scan • {view} • N {m['counts'][i][0]:,} → {m['counts'][i][1]:,}{extra}\nCPU warm median {m['median_ms'][i]:.2f} ms / P95 {m['p95_ms'][i]:.2f} ms (n=5; OMP=2)"
    self.finish(fig,f'rasc6/{name}_{view.lower()}',titles[i],sub,svg=False,limits='ROI is not an exact IK reachability field. MODEL REFERENCE ≠ measured geometry.' if i in [2,5] else 'All views share camera, limits and scale. Display window clips distant raw points; counts use full input.')
 def geometry_ab(self):
  m=self.metrics
  for name,boxes,c,title in [('old_boxes',self.old,'#ce6345','连通簇单框跨越稀疏观测区域'),('new_primitives',self.new,'#298c7a','多基元减少包络体积，同时覆盖全部保留点')]:
   fig=self.figure();ax=self.ax3(fig);self.points(ax,self.arr['clean'],s=4);self.boxes(ax,boxes,c,alpha=.09,padding=.007)
   self.finish(fig,'geometry_ab/'+name,title,f"Matched Oct10 scan / uniform 7 mm padding / {len(boxes)} primitives\nPoint coverage {m['old_point_coverage'] if name=='old_boxes' else m['new_point_coverage']}/{m['clean_points']}; sum of padded box volumes {m['old_inflated_sum_volume_m3'] if name=='old_boxes' else m['new_inflated_sum_volume_m3']:.6f} m³",limits='Sum of volumes includes overlaps; unknown/occluded space is not certified free.')
  region=[ [.48,-.48,.79], [1.10,.03,1.08] ]
  for name,boxes,c in [('old_boxes_zoom',self.old,'#ce6345'),('new_primitives_zoom',self.new,'#298c7a')]:
   fig=self.figure();ax=self.ax3(fig,bounds=region);self.points(ax,self.arr['clean'],s=5);self.boxes(ax,boxes,c,alpha=.08,padding=.007)
   self.finish(fig,'geometry_ab/'+name,'同一局部视角揭示单框与多基元的包络差异',f'Matched zoom BODY X 0.48..1.10 / Y −0.48..0.03 / Z 0.79..1.08 m\nSame pointcloud and uniform 7mm padding; {len(boxes)} primitives in full representation',limits='Identical zoom for OLD and NEW; no observed point deletion. Sparse observations do not certify unseen free space.')
  # Same-world 2mm XY grid slice, choose Z with largest representational discrepancy.
  x=np.arange(.22,1.301,.002);y=np.arange(-.76,.761,.002);X,Y=np.meshgrid(x,y);xy=np.c_[X.ravel(),Y.ravel()]
  def occupancy(boxes,z):
   out=np.zeros(len(xy),bool)
   for b in boxes:
    center=np.asarray(b['center_m']);half=np.asarray(b['dims_m'])/2+.007
    if abs(z-center[2])<=half[2]:out|=np.all(np.abs(xy-center[:2])<=half[:2],axis=1)
   return out
  zs=np.arange(.8,1.25,.005);scores=[]
  for z in zs:scores.append(int(np.sum(occupancy(self.old,z)&~occupancy(self.new,z))))
  z=float(zs[np.argmax(scores)]);old,new=occupancy(self.old,z),occupancy(self.new,z);v=np.zeros(len(xy));v[new]=1;v[old&~new]=2;fig=self.figure();ax=fig.add_subplot();from matplotlib.colors import ListedColormap
  ax.imshow(v.reshape(X.shape),origin='lower',extent=[x[0],x[-1],y[0],y[-1]],cmap=ListedColormap(['white','#73ad9e','#e8a28f']),vmin=0,vmax=2,interpolation='nearest');cloud=self.arr['clean'];near=cloud[np.abs(cloud[:,2]-z)<=.015];ax.scatter(*near[:,:2].T,s=4,c='#25384a',label='Observed points within ±15 mm');ax.set(xlabel='BODY X [m]',ylabel='BODY Y [m]');ax.set_aspect('equal');ax.set_xlim(.45,1.12);ax.set_ylim(-.5,.04);from matplotlib.patches import Patch
  ax.legend(handles=[Patch(color='#e8a28f',label='OLD-only occupied representation'),Patch(color='#73ad9e',label='NEW occupied representation'),plt.Line2D([],[],marker='.',color='#25384a',ls='',label='Nearby measured points')],bbox_to_anchor=(1.02,1),loc='upper left',fontsize=10);fig.subplots_adjust(right=.73)
  self.finish(fig,'geometry_ab/error_occupied_space_slice','旧框额外占据的区域可量化，但不能直接称为空闲空间',f"Identical XY slice at BODY Z={z:.3f} m / grid=2 mm / both padding=7 mm\nOLD-only slice area = {max(scores)*.002**2:.5f} m²; slice chosen by maximum OLD-only area",limits='Orange means representation disagreement, not sensor-proven free volume. No scan-ray free-space proof.')
  save(self.out/'runlogs/geometry_ab_metrics.json',dict(source_kind='FROZEN_REPLAY',slice_z_m=z,grid_m=.002,old_only_slice_area_m2=max(scores)*.002**2,selection='Max OLD-only area over Z 0.800..1.245m at 5mm steps',sum_volume_not_union=True,point_coverage=[m['old_point_coverage'],m['new_point_coverage']],old_k=m['old_k'],new_k=m['new_k']))
 def servo(self):
  receipts=[]
  for case,p in enumerate(sorted((ROOT/'worklog/evidence/2026-09-07-curobo').glob('*/*jsonl'))):
   events=[json.loads(x) for x in p.read_text().splitlines()];samples=[x for x in events if x.get('event')=='sample'];t=np.asarray([x['monotonic'] for x in samples]);t-=t[0];target=np.asarray([x['target_rad'] for x in samples]);actual=np.asarray([x['actual_rad'] for x in samples]);current_error=np.rad2deg(actual-target);previous=np.vstack([target[0],target[:-1]]);err=np.rad2deg(actual-previous);joint=int(np.argmax(np.ptp(target,axis=0)));record=dict(source=str(p.relative_to(ROOT)),sha256=sha(p),samples=len(t),logged_span_s=float(t[-1]),sample_dt_median_s=float(np.median(np.diff(t))),sample_dt_max_s=float(np.max(np.diff(t))),moving_joint=joint+1,max_error_deg=float(np.max(abs(err))),rms_error_deg=float(np.sqrt(np.mean(err**2))),p95_abs_error_deg=float(np.percentile(abs(err),95)),per_joint_max_deg=np.max(abs(err),axis=0).tolist(),begin=events[0],end=events[-1],completion='ABORTED; target_reached absent',current_pair_max_error_deg=float(np.max(abs(current_error))),error_alignment='actual sample occurs before current send; use previous command for following error',feedback_source='dedicated telemetry joint_actual_position_rad; not SDK FK or controller_reported_rad');receipts.append(record)
   for j in range(6):
    fig=self.figure();ax=fig.add_subplot();ax.plot(t,np.rad2deg(target[:,j]),color='#3c709a',label='ServoJ target');ax.plot(t,np.rad2deg(actual[:,j]),'o-',color='#ce6345',ms=4,label='Measured telemetry (before current send)');ax.set(xlabel='Logged monotonic time since first sample [s]',ylabel=f'Joint {j+1} [deg]');ax.legend();ax.grid(alpha=.2)
    self.finish(fig,f'servo/case{case+1}_joint_target_vs_actual_J{j+1}',f'真实命令与回读：J{j+1}，保留全部日志样本',f"7 Sep historical ABORTED supervised micro-motion / {len(t)} logged paired samples\nRead before current send; abort and servo-disable retained; full commanded segment incomplete",'PHYSICAL_MEASURED',sha(p),limits='Historical small-amplitude motion, not the full grasp/place Demo and not a before/after optimization.')
   fig=self.figure();ax=fig.add_subplot()
   for j in range(6):ax.plot(t,err[:,j],'.-',label=f'J{j+1}')
   ax.axhline(0,c='#8e99a5',lw=.7);ax.set(xlabel='Logged monotonic time [s]',ylabel='Measured actual − previous command [deg]');ax.legend(ncol=6);ax.grid(alpha=.2)
   self.finish(fig,f'servo/case{case+1}_tracking_error_6joints','真实误差放大显示回读差异，不制造跟踪波形',f"max |error|={record['max_error_deg']:.6f}° / RMS={record['rms_error_deg']:.6f}° / P95={record['p95_abs_error_deg']:.6f}°",'PHYSICAL_MEASURED',sha(p),limits='Actual read precedes current send; first point uses initial command. ABORTED traces; no normal completion claim.')
   fig=self.figure();axs=fig.subplots(2,1,sharex=True)
   for q,c,label in [(target,'#3c709a','target'),(actual,'#ce6345','Measured telemetry')]:
    velocity=np.gradient(np.rad2deg(q[:,joint]),t);acc=np.gradient(velocity,t);axs[0].plot(t,velocity,'.-',c=c,label=label);axs[1].plot(t,acc,'.-',c=c,label=label)
   axs[0].set_ylabel(f'J{joint+1} [deg/s]');axs[1].set(xlabel='Logged monotonic time [s]',ylabel=f'J{joint+1} [deg/s²]');axs[0].legend();[x.grid(alpha=.2) for x in axs]
   self.finish(fig,f'servo/case{case+1}_joint_velocity_acceleration','稀疏实测差分仅用于观察，不能证明jerk安全',f"np.gradient on irregular logged timestamps; no smoothing\nMedian logged dt={record['sample_dt_median_s']*1000:.1f} ms; max dt={record['sample_dt_max_s']*1000:.1f} ms",'PHYSICAL_MEASURED',sha(p),limits='Logged telemetry is decimated relative to control stream. Differentiation amplifies noise; no jerk claim.')
  save(self.out/'runlogs/servo_trace_metrics.json',receipts)
 def performance(self):
  source=sha(ROOT/'docs/reports/2026-10-21_CENTER_GRASP_PLANNER_STUDY.md');fig=self.figure();ax=fig.add_subplot();names=['Dense independent\nworld validation','Contact geometry\nbuild','Pregrasp-only\npreparation'];before=np.array([17.023,15.176,15.866]);after=np.array([1.125,.830,1.437]);x=np.arange(3);ax.bar(x-.18,before,.34,color='#a5afb9',label='Before');ax.bar(x+.18,after,.34,color='#298c7a',label='After')
  for xs,vals in [(x-.18,before),(x+.18,after)]:
   for xx,v in zip(xs,vals):ax.text(xx,v+.35,f'{v:.3f} s',ha='center',fontsize=14)
  ax.set(xticks=x,xticklabels=names,ylabel='Historical wall time [s]',ylim=(0,20));ax.legend();ax.grid(axis='y',alpha=.2)
  self.finish(fig,'performance/latency_module_before_after','三项历史模块提速来自不同层，收益不可相加','21 Oct frozen study • exact output checks reported • CPU native loop / indexed inclusive query\n431-sample validator; preparation includes dependent work','HISTORICAL_EXTRACT',source,limits='Historical site CPU measurements, not this workstation or GPU speedup. Raw Oct21 tar absent locally.')
  for file,title in [('cpu_backend_comparison.json','相同轨迹与几何，独立CPU后端数值等价'),('contact_query_comparison.json','同一真实点云查询，索引保持输出逐数组一致')]:
   p=self.out/'runlogs'/file
   if not p.exists():continue
   d=load(p);rows=d['runs'];key='backend' if 'backend' in rows[0] else 'indexed';groups=list(dict.fromkeys(r[key] for r in rows));fig=self.figure();ax=fig.add_subplot();data=[[r['elapsed_s'] for r in rows if r[key]==g] for g in groups];xs=np.arange(len(groups));ax.bar(xs,[np.median(z) for z in data],color=['#a5afb9','#298c7a']);ax.set(xticks=xs,xticklabels=[str(g) for g in groups],ylabel='Whole measured scope [s]');
   for i,z in enumerate(data):ax.scatter([i]*len(z),z,c='#263d52',s=35);ax.text(i,max(z)*1.05,f'median {np.median(z):.3f}s\nn={len(z)} incl. cold',ha='center',fontsize=13)
   ax.set_ylim(0,max(max(z) for z in data)*1.25);ax.grid(axis='y',alpha=.2)
   self.finish(fig,'performance/'+file.replace('.json',''),title,'28 Oct local CPU replay / OMP=2 / points = same Oct10 scan\n'+d['interpretation_limit'],source=sha(p),limits='All repetitions shown, including first-call overhead. No samples, margins or predicates removed.')
  # Keep genuinely measured native-ready scope separate; no inferred scan/GPU segmentation.
  vals=[9.94,55.59,92.93,31.83,149.65,60.31];labels=['Ready→stream','Pregrasp motion','Wait→contact','Contact motion','Wait→lift','Lift motion'];colors=['#a9b3bd','#3c709a','#a9b3bd','#3c709a','#a9b3bd','#3c709a'];fig=self.figure();ax=fig.add_subplot();left=0
  for i,(v,l,c) in enumerate(zip(vals,labels,colors)):ax.barh(i,v,left=left,color=c);ax.text(left+v/2,i,f'{v:.2f}s',ha='center',va='center',color='white' if c=='#3c709a' else '#243746',fontsize=12);left+=v
  ax.set(yticks=range(6),yticklabels=labels,xlabel='Seconds from native-ready checkpoint');ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
  self.finish(fig,'performance/latency_critical_path_waterfall','原现场关键路径的大部分时间消耗在非运动窗口',f"24 Sep historical event boundaries / total {sum(vals):.2f}s = motion 147.73s + other 252.52s\nPublished audit rounds aggregate motion to 147.74s; no pure GPU timing inferred",'HISTORICAL_EXTRACT',sha(ROOT/'docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md'),limits='Non-motion includes gripper, sensing, I/O and manual handoff; cannot attribute entire window to vision.')
  # Report optimizer budgets honestly; no invented P95/success denominator.
  fig=self.figure();ax=fig.add_subplot();labels=['25 iter / 1 traj / 4 IK','25 / 2 / 4','50 / 2 / 4','25 / 2 / 4 no graph','Native refinement / 2 / 4'];values=[3.727,4.952,7.291,5.028,58.81];ax.barh(labels,values,color=['#298c7a']*4+['#8c789b']);ax.invert_yaxis();ax.set(xlabel='Historical warm request wall [s]',xlim=(0,68));
  for i,v in enumerate(values):ax.text(v+.5,i,f'{v:.3f}s',va='center')
  self.finish(fig,'performance/fast_vs_quality_profiles','迭代与额外细化改变计算预算，不能泛化为全场景延迟','21 Oct / 100mm diagnostic standoff / same frozen world\nEach row is a reported warm request; not P50/P95 or production FAST-vs-QUALITY robustness','HISTORICAL_EXTRACT',source,limits='Derived 55mm warm P50=3.561s/P95=3.646s belongs to a different diagnostic series; not mixed here.')
 def diagram(self,name,title,nodes,edges,source_paths,sub='Code-derived structure • not a measured runtime speedup',kind='SCHEMATIC'):
  nodes=[(label,(8.4-x+.1 if y<3 else x),y) for label,x,y in nodes]
  fig=self.figure();ax=fig.add_subplot();ax.set_xlim(-.2,11.5);ax.set_ylim(.3,5.9);ax.axis('off')
  for i,(label,x,y) in enumerate(nodes):
   box=FancyBboxPatch((x,y),2.6,.95,boxstyle='round,pad=.10',facecolor='#edf3f6',edgecolor='#56768b',lw=1.4);ax.add_patch(box);ax.text(x+1.3,y+.475,label,ha='center',va='center',fontsize=13)
  for i,j in edges:
   _,x,y=nodes[i];_,xx,yy=nodes[j]
   if abs(xx-x)<.2:start=(x+1.3,y if yy<y else y+.95);end=(xx+1.3,yy+.95 if yy<y else yy)
   elif xx>x:start=(x+2.6,y+.475);end=(xx,yy+.475)
   else:start=(x,y+.475);end=(xx+2.6,yy+.475)
   ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=17,color='#56768b',connectionstyle='arc3,rad=.03'))
  source=digest({p:sha(ROOT/p) for p in source_paths});self.finish(fig,'runtime/'+name,title,sub,kind,source,limits='Sources: '+'; '.join(p.split('/')[-1] for p in source_paths));return source
 def diagrams(self):
  self.diagram('curobo_native_principle','cuRobo提供GPU候选生成与轨迹优化能力',[('IK / c-space goal\ncuRobo upstream',.1,4.5),('Trajectory seeds\nGPU batches',4.2,4.5),('Parallel optimization\ngoal / collision / smooth',8.4,4.5),('Collision costs\nrobot / world / self',.1,1.4),('Trajectory selection\nsolver success criteria',4.2,1.4),('Interpolated result\nnot execution approval',8.4,1.4)],[(0,1),(1,2),(3,2),(2,4),(4,5)],['src/ares_r/motion/production_scene_worker.py','src/ares_r/motion/latency_solver.py'],sub='Upstream cuRobo capability; explanatory objective, not a claim of an ARES-R CUDA kernel')
  self.diagram('aresr_constraint_integration','ARES-R构造任务约束，并在规划后独立核验',[('BODY / both arms / TCP\nversioned capture',.1,4.5),('Goal + task phase\nlevel / limits / payload',4.2,4.5),('cuRobo request\nscoped collision world',8.4,4.5),('Dense validation\nFK + world + orientation',.1,1.4),('Native packaging\ndynamics / tracking',4.2,1.4),('Protected JAKA sender\nreadback / arrived',8.4,1.4)],[(0,1),(1,2),(2,3),(3,4),(4,5)],['src/ares_r/motion/scene_aware_planner.py','src/ares_r/motion/independent_path_validation.py','src/ares_r/motion/native_execution_package.py'],sub='ARES-R integration / adaptation / verification • exact contracts traced to source')
  self.diagram('skills_hierarchy','技能、复合动作与任务阶段通过明确契约连接',[('Atomic perception\nDetect / BuildScene',.1,4.5),('Atomic planning\nPlan / Validate',4.2,4.5),('Approach / Grasp\nVerify / Lift',8.4,4.5),('Transport / Place\nRecover',.1,1.4),('Composite task\nroundtrip stages',4.2,1.4),('Runtime resource locks\nscene / job ownership',8.4,1.4)],[(0,1),(1,2),(2,3),(3,4),(4,5)],['src/ares_r/manipulation/roundtrip_demo.py','src/ares_r/manipulation/roundtrip_job.py','src/ares_r/skills/runtime.py'] if (ROOT/'src/ares_r/skills/runtime.py').exists() else ['src/ares_r/manipulation/roundtrip_demo.py','src/ares_r/manipulation/roundtrip_job.py'],sub='Implemented interfaces ≠ all devices commissioned; historical full task completed with recovery')
  self.diagram('scene_state_contract','场景、关节与工具版本共同约束轨迹的有效性',[('ObservationEpoch\nsource SHA / capture',.1,4.5),('SceneSnapshot\nTF / joints / target',4.2,4.5),('Tool + payload\nbase pose revision',8.4,4.5),('Plan digest\nconsumes bound state',.1,1.4),('Execute / readback\nvalidate start + lease',4.2,1.4),('State changed\ninvalidate / observe',8.4,1.4)],[(0,1),(1,2),(2,3),(3,4),(4,5),(5,0)],['src/ares_r/world/scene_snapshot.py','src/ares_r/world/world_model.py','src/ares_r/motion/scene_aware_motion.py'])
  self.diagram('adapters_and_devices','规范服务隔离设备I/O与任务逻辑',[('WebUI / ART\nshared backend',.1,4.5),('Skill / task runtime\nresource ownership',4.2,4.5),('Canonical services\nscene / motion / jobs',8.4,4.5),('Epic / EpicEye\nvision adapters',.1,1.4),('cuRobo\npersistent GPU worker',4.2,1.4),('JAKA / Gripper / AMR\nprotected adapters',8.4,1.4)],[(0,1),(1,2),(2,3),(2,4),(2,5)],['src/ares_r/canonical_backend.py','src/ares_r/motion/persistent_planner_service.py','src/ares_r/webui/server.py'],sub='Real repository adapters; no invented ROS driver. This sprint connects to no devices.')
  self.diagram('scene_and_execution_lifecycle','观察到提交之间，每次状态改变都可能使旧计划失效',[('Observe → Compile\natomic scene epoch',.1,4.5),('Plan → Independent\nValidate',4.2,4.5),('Native Execute\nprotected sender',8.4,4.5),('Readback / settling\nARRIVED evidence',.1,1.4),('Commit / invalidate\nnext task stage',4.2,1.4),('Stop / fault / resume\nverified checkpoints',8.4,1.4)],[(0,1),(1,2),(2,3),(3,4),(4,0),(2,5),(5,3)],['src/ares_r/manipulation/roundtrip_demo.py','src/ares_r/motion/scene_aware_motion.py'],sub='Stop/cancellation support is implemented; ambiguous physical ACK reconciliation remains a site risk')
  self.diagram('object_ownership_transition','闭爪只是候选，受控抬升后才确认持物',[('WORLD\nscene obstacle',.1,4.5),('HOLD_CANDIDATE\nclose/readback',4.2,4.5),('GRASP_CONFIRMED\ncontrolled lift + evidence',8.4,4.5),('ATTACHED\nlocal geometry + filter',.1,1.4),('RELEASE_VERIFIED\nopen + readback',4.2,1.4),('WORLD / invalidate\nfresh observation',8.4,1.4)],[(0,1),(1,2),(2,3),(3,4),(4,5)],['src/ares_r/manipulation/grasp_verification.py','src/ares_r/manipulation/attached_world.py','src/ares_r/manipulation/roundtrip_demo.py'],sub='Code contract; no fabricated three-stage physical scene acquisition')
  self.diagram('pipeline_architecture','并发准备必须服从设备互斥与场景版本依赖',[('Camera / device owner\nIMPLEMENTED',.1,4.5),('CPU scene processing\nIMPLEMENTED',4.2,4.5),('Persistent cuRobo owner\nIMPLEMENTED',8.4,4.5),('Async evidence / next prep\ncode + replay only',.1,1.4),('5700 || 5000 capture\nPROPOSED / audit first',4.2,1.4),('Physical overlap saving\nNOT MEASURED',8.4,1.4)],[(0,1),(1,2),(2,3),(4,5)],['src/ares_r/motion/persistent_planner_service.py','docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md'],sub='Concurrency architecture, offline replay and measured site savings are separate evidence levels')
 def payload(self):
  for name,dims,title in [('payload_wrong_footprint',[.220,.217,.113],'旧持物包络把相邻结构合入工件尺寸'),('payload_corrected',[.160,.100,.105],'按物理尺寸限定主段，并保留20mm夹持后段')]:
   fig=self.figure();ax=fig.add_subplot();ax.add_patch(Rectangle((-dims[0]/2,-dims[1]/2),dims[0],dims[1],facecolor='#d9e9e4' if 'corrected' in name else '#f0dcd6',edgecolor='#298c7a' if 'corrected' in name else '#ce6345',lw=2));ax.add_patch(Rectangle((-.09,-.05),.18,.10,fill=False,edgecolor='#263d52',lw=2,linestyle='--',label='Known total footprint 180 × 100 mm'))
   if 'corrected' in name:ax.add_patch(Rectangle((-.10,-.05),.02,.10,facecolor='#8c789b',alpha=.6,label='Rear clamped segment 20 mm (schematic alignment)'))
   ax.set(xlim=(-.15,.15),ylim=(-.145,.145),xlabel='Object longitudinal reference [m]',ylabel='Object width reference [m]');ax.set_aspect('equal');ax.legend(loc='lower right');ax.grid(alpha=.2)
   self.finish(fig,'attachments/'+name,title,f"19 Oct historical model audit: {'padded old envelope ≈220×217×113 mm' if 'wrong' in name else 'exposed main section 160×100 mm; original thickness retained'}\nDimension diagram; original alignment/TCP transform is not reconstructed",'HISTORICAL_EXTRACT',sha(ROOT/'docs/golden/2026-10-19/README.md'),limits='Task-specific operator-sized correction, not automatic general object inference; missing place geometry prevents clearance proof.')
 def planning(self):
  p=self.out/'runlogs/compare_planning.json'
  if not p.exists():return
  d=load(p)
  for row in d['rows']:
   name=row['representation'];fig=self.figure();ax=self.ax3(fig);self.points(ax,self.arr['clean'],s=3);self.boxes(ax,self.old if name=='old' else self.new,'#ce6345' if name=='old' else '#298c7a',alpha=.04,padding=.007);planpath=self.a.private/(name+'_planning.json');plan=load(planpath) if planpath.exists() else {};path=plan.get('tcp_path_body_m')
   if path is not None and len(path):ax.plot(*np.asarray(path).T,lw=3,c='#234e82',label='Actual saved cuRobo result');ax.legend()
   if plan.get('trajectory_points_rad'):
    from ares_r.perception.robot_collision import arm_link_transforms
    req=load(self.a.private/(name+'_request.json'));T=np.asarray(req['T_body_model']);urdf=req['robot_yaml_urdf']
    for q,c,label in [(plan['trajectory_points_rad'][0],'#667485','Start model reference'),(plan['trajectory_points_rad'][-1],'#235a85','Goal model reference')]:
     frames=arm_link_transforms(urdf,q);points=np.array([(T@frames[k])[:3,3] for k in ['base_link']+['link%d'%j for j in range(1,7)]])
     ax.plot(*points.T,'o-',c=c,lw=2,ms=4,label=label)
    if path is not None and len(path):
     ax.scatter(*np.asarray(path)[[0,-1]].T,s=60,c=['#667485','#235a85']);ax.text(*np.asarray(path)[-1],'Goal',fontsize=11)
    ax.legend(loc='upper left',bbox_to_anchor=(-.2,1),fontsize=10)
   ep=row['endpoints'];self.finish(fig,'planning/planning_'+name,f"同条件{ name.upper()}规划：{row.get('result') or row.get('supervisor_error') or 'not solved'}",f"start gap {ep['start']['min_clearance_m']*1000:.2f} mm; goal gap {ep['goal']['min_clearance_m']*1000:.2f} mm\n50 iters / 2 traj seeds / 4 IK / same q0, goal, tool, payload / uniform 7mm",source=sha(p),limits='Reconstructed offline runtime; no physical approval. Capture q differs from planning q0; both representations share that q0.')
  with (self.out/'tables/failure_reason.csv').open('w') as f:
   w=csv.writer(f);w.writerow(['representation','result','start_gap_m','goal_gap_m','gpu_attempted']);w.writerows([[r['representation'],r.get('result') or r.get('supervisor_error'),r['endpoints']['start']['min_clearance_m'],r['endpoints']['goal']['min_clearance_m'],r['gpu_attempted']] for r in d['rows']])
 def run(self,groups=None):
  for name in (groups or ['rasc','geometry_ab','servo','performance','diagrams','payload','planning']):getattr(self,name)()
  previous=load(self.out/'ASSET_MANIFEST.json') if groups and (self.out/'ASSET_MANIFEST.json').exists() else dict(schema_version=1,assets=[],missing_value_policy='Null means unavailable/not applicable; see asset interpretation and reports.')
  changed={x['asset_id'] for x in self.manifest};previous['assets']=[x for x in previous['assets'] if x['asset_id'] not in changed]+self.manifest;save(self.out/'ASSET_MANIFEST.json',previous)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--groups',nargs='+',choices=['rasc','geometry_ab','servo','performance','diagrams','payload','planning']);a=p.parse_args();Renderer(a).run(a.groups)
