#!/usr/bin/env python3
"""Large, occlusion-aware evidence views. All cropping is DISPLAY ONLY.
Uses frozen arrays/box outputs; never modifies scenes or reruns planning.
"""
import argparse,sys,json,hashlib,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle,Patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from replay_rasc import load,save,sha
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
CJK=font_manager.FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').get_name()
plt.rcParams.update({'font.family':['DejaVu Sans',CJK],'font.size':16,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
SIGNS=np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])
EDGES=[(i,j) for i in range(8) for j in range(i+1,8) if bin(i^j).count('1')==1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--assets',type=Path,required=True);a=p.parse_args();out=a.assets/'clarity_v2';out.mkdir(exist_ok=True);arr=np.load(a.private/'rasc_arrays.npz');cloud=arr['clean'];old=load(a.private/'old.json');new=load(a.private/'refined.json')['primitives'];m=load(a.assets/'runlogs/rasc_stage_metrics.json');entries=[]
 elev,az=np.deg2rad([30,-110]);normal=np.array([np.cos(elev)*np.cos(az),np.cos(elev)*np.sin(az),np.sin(elev)]);right=np.cross([0,0,1],normal);right/=np.linalg.norm(right);up=np.cross(normal,right)
 def project(points):return np.asarray(points)@np.c_[right,up]
 def finish(fig,name,title,subtitle,params):
  fig.text(.055,.965,title,fontsize=24,weight='bold',va='top');fig.text(.055,.912,subtitle,fontsize=13,color='#435266',va='top')
  fig.text(.055,.029,'FROZEN_REPLAY / Oct10 real scan / DISPLAY ONLY / NO PHYSICAL MOTION',fontsize=11,color='#435266')
  path=out/(name+'.png');fig.savefig(path,dpi=200,facecolor='white');plt.close(fig);entries.append(dict(path=path.name,source_kind='FROZEN_REPLAY',source_camera_sha256=m['source_camera_sha256'],source_geometry=[sha(a.private/'old.json'),sha(a.private/'refined.json')],generation_script='tools/presentation_evidence/render_clarity_v2.py',generation_params=params,camera={'elevation_deg':30,'azimuth_deg':-110,'side':'BODY -Y toward +Y'},point_data_changed=False,planning_changed=False,sha256=sha(path)))
 def frame(bounds):
  fig=plt.figure(figsize=(12,9));ax=fig.add_axes([.055,.12,.90,.70]);lo,hi=np.array(bounds);corners=lo+(SIGNS+1)/2*(hi-lo);q=project(corners);low,high=q.min(0),q.max(0);center=(low+high)/2;span=(high-low)*1.06
  ax.set(xlim=(center[0]-span[0]/2,center[0]+span[0]/2),ylim=(center[1]-span[1]/2,center[1]+span[1]/2));ax.set_aspect('equal');ax.axis('off')
  # Explicit scale / camera triad without a large XYZ grid surrounding a small subject.
  bar=.10;start=np.array([low[0]+.01,low[1]+.015]);ax.plot([start[0],start[0]+bar],[start[1],start[1]],c='#263d52',lw=3);ax.text(*(start+[bar/2,.008]),'100 mm',ha='center',fontsize=12)
  origin=np.array([high[0]-.08,low[1]+.055])
  for direction,label,c in zip(np.eye(3),['X','Y','Z'],['#b65743','#328975','#547ab0']):
   vec=project([direction*.045])[0];ax.annotate('',xy=origin+vec,xytext=origin,arrowprops=dict(arrowstyle='->',color=c,lw=1.5));ax.text(*(origin+vec*1.25),label,color=c,fontsize=11)
  return fig,ax
 def points(ax,p,c='#344c62',size=2.5):
  if len(p)==0:return
  order=np.argsort(p@normal);xy=project(p[order]);color=np.asarray(c)[order] if not isinstance(c,str) else c
  ax.scatter(xy[:,0],xy[:,1],s=size,c=color,linewidths=0,alpha=1,rasterized=True)
 def lines(ax,boxes,color,clip):
  lo,hi=np.asarray(clip);segments=[];count=0
  for b in boxes:
   center=np.asarray(b['center_m']);half=np.asarray(b['dims_m'])/2+.007
   if np.any(center+half<lo) or np.any(center-half>hi):continue
   # Clip only display edge segments; clipping does not change represented obstacle geometry.
   corners=center+SIGNS*half;count+=1
   for i,j in EDGES:
    before,after=corners[i],corners[j];d=after-before;t0,t1=0.,1.;valid=True
    for k in range(3):
     if abs(d[k])<1e-12:
      if not lo[k]<=before[k]<=hi[k]:valid=False;break
     else:
      ta,tb=sorted([(lo[k]-before[k])/d[k],(hi[k]-before[k])/d[k]]);t0=max(t0,ta);t1=min(t1,tb)
    if valid and t0<=t1:segments.append(project([before+t0*d,before+t1*d]))
  ax.add_collection(LineCollection(segments,colors=color,linewidths=.75,alpha=.8));return count
 full=[[.46,-.46,.77],[1.29,.66,1.12]]
 foreground=np.all(np.abs(cloud-np.asarray(old[0]['center_m']))<=np.asarray(old[0]['dims_m'])/2+1e-9,axis=1) if old[0]['primitive_id']=='residual_000' else np.zeros(len(cloud),bool)
 fig,ax=frame(full);colors=np.full((len(cloud),), '#36526b',dtype=object);colors[foreground]='#b26c54';points(ax,cloud,colors,size=3.0)
 ax.legend(handles=[Patch(color='#b26c54',label=f'前方结构：{int(foreground.sum())}点'),Patch(color='#36526b',label='其他观测：保留原始空间位置')],loc='upper left',frameon=False,fontsize=13)
 finish(fig,'01_large_context','全景只交代位置：前方结构确实遮挡后层',f'{len(cloud)} cleaned points / camera from BODY −Y / opaque fine dots, no stacked box fills\n前方窄长结构约Y=−0.42m；后层不会因换色自动变得可见',dict(display_bounds=full,render='depth-sorted opaque points; no alpha accumulation',full_point_count=len(cloud),visible_count=len(cloud)))
 crop=[[.577,-.188,.872],[.866,-.041,.986]];lo,hi=np.asarray(crop);keep=np.all((cloud>=lo)&(cloud<=hi),axis=1);local=cloud[keep]
 fig,ax=frame(crop);points(ax,local,size=6);finish(fig,'02_rear_layer_cutaway','剖开前方显示层，后方观测才能读清楚',f'DISPLAY CUT: BODY X[0.577,0.866], Y[−0.188,−0.041], Z[0.872,0.986] m\n只显示 {len(local)}/{len(cloud)} 个点；其余点仍保留在完整世界与规划中',dict(display_bounds=crop,visible_count=len(local),hidden_for_display_only=len(cloud)-len(local),full_point_count=len(cloud)))
 for name,boxes,color,label in [('03_old_cutaway',old,'#bf644c','OLD 连通簇单框'),('04_new_cutaway',new,'#258574','NEW 多基元')]:
  fig,ax=frame(crop);points(ax,local,c='#7a8890',size=2.0);n=lines(ax,boxes,color,crop);finish(fig,name,label+'：把包络与点云分开读',f'完全相同的相机、剖切范围与 {len(local)} 个可见点 / uniform 7mm inflation\n仅线框、无半透明填充；全场景K={len(boxes)}，当前裁切相交K={n}',dict(display_bounds=crop,visible_count=len(local),display_intersecting_k=n,total_k=len(boxes),inflation_m=.007))
 # Exact XY section through both box worlds: remove occlusion instead of painting fake free space.
 z=.905;slab_half=.006;xy_bounds=[[.56,-.25],[.91,.015]];near=cloud[(abs(cloud[:,2]-z)<=slab_half)&np.all((cloud[:,:2]>=xy_bounds[0])&(cloud[:,:2]<=xy_bounds[1]),axis=1)]
 for name,boxes,color,title in [('05_old_section',old,'#d08067','OLD：单框在剖面上跨越观测稀疏区域'),('06_new_section',new,'#398f7c','NEW：多基元更贴近同一层观测')]:
  fig=plt.figure(figsize=(10,8));ax=fig.add_axes([.10,.14,.84,.65]);ax.set_aspect('equal');ax.set(xlim=(xy_bounds[0][0],xy_bounds[1][0]),ylim=(xy_bounds[0][1],xy_bounds[1][1]),xlabel='BODY X [m]',ylabel='BODY Y [m]');ax.tick_params(labelsize=12)
  for b in boxes:
   c=np.asarray(b['center_m']);h=np.asarray(b['dims_m'])/2+.007
   if abs(c[2]-z)>h[2] or np.any(c[:2]+h[:2]<xy_bounds[0]) or np.any(c[:2]-h[:2]>xy_bounds[1]):continue
   ax.add_patch(Rectangle(c[:2]-h[:2],*(2*h[:2]),edgecolor=color,facecolor=color,alpha=.18,linewidth=1.0,clip_on=True))
  ax.scatter(near[:,0],near[:,1],s=10,c='#263d52',linewidths=0,zorder=4);ax.grid(alpha=.12)
  message='单框跨过本层没有观测点的位置' if name=='05_old_section' else '同一批点；分块包络沿观测分布'
  destination=(.76,-.11) if name=='05_old_section' else (.603,-.10)
  ax.annotate(message,xy=destination,xytext=(.635,-.020),fontsize=12,color='#263d52',arrowprops=dict(arrowstyle='->',color='#263d52',lw=1.1))
  finish(fig,name,title,f'BODY Z={z:.3f}m / dots: measured points within ±{slab_half*1000:.0f}mm\n相同剖面、范围、膨胀；着色表示包络占据，不等于传感器已证明空闲',dict(section_z_m=z,point_slab_half_width_m=slab_half,xy_bounds_m=xy_bounds,visible_point_count=len(near),inflation_m=.007,view='TOP section; -Y bottom'))
 # Single isolated geometric role: no wall, no entire robot/world overlay.
 classes={}
 for semantic in ['SUPPORT_SURFACE','PROTRUDING_OBSTACLE','STRUCTURE','UNKNOWN_OCCUPIED']:
  mask=np.zeros(len(cloud),bool)
  for b in new:
   if b['semantic']==semantic:mask|=np.all(np.abs(cloud-b['center_m'])<=np.asarray(b['dims_m'])/2+1e-9,axis=1)
  classes[semantic]=mask
 colors={'SUPPORT_SURFACE':'#328975','PROTRUDING_OBSTACLE':'#c0714e','STRUCTURE':'#557eb4','UNKNOWN_OCCUPIED':'#8c71a4'}
 fig,ax=frame(crop)
 assigned=np.zeros(len(cloud),bool)
 for semantic,mask in classes.items():
  mask&=~assigned;assigned|=mask;points(ax,cloud[mask&keep],colors[semantic],size=4)
 ax.legend(handles=[Patch(color=colors[s],label=s) for s in colors],loc='upper left',fontsize=11,frameon=False)
 finish(fig,'07_roles_cutaway','几何分层单独展示，不与全部包络叠成一团',f'同一显示剖切 / same {len(local)} points / colors = geometric grouping, not neural recognition\n全点和原障碍仍保留；此图只解释分组结果',dict(display_bounds=crop,visible_count=len(local),semantics=list(colors)))
 # Before/after page uses images only; original v1 preserved beside the prototype.
 from PIL import Image,ImageDraw,ImageFont
 left=Image.open(a.assets/'panels/geometry_ab/new_primitives_zoom.png').convert('RGB');right_im=Image.open(out/'04_new_cutaway.png').convert('RGB');canvas=Image.new('RGB',(3200,1900),'white');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',32)
 for i,(im,label) in enumerate([(left,'V1: full-depth overlay'),(right_im,'V2: labelled display cutaway')]):
  im.thumbnail((1580,1750));canvas.paste(im,(i*1600+(1600-im.width)//2,85+(1750-im.height)//2));draw.text((i*1600+35,25),label,font=font,fill='#263d52')
 canvas.save(out/'comparison_v1_v2.png')
 pair=Image.new('RGB',(3200,1380),'white')
 for i,name in enumerate(['05_old_section.png','06_new_section.png']):
  im=Image.open(out/name).convert('RGB');im.thumbnail((1580,1360));pair.paste(im,(i*1600+(1600-im.width)//2,(1380-im.height)//2))
 pair.save(out/'section_old_new_pair.png')
 save(out/'MANIFEST.json',dict(source_kind='FROZEN_REPLAY',source_arrays_private=True,full_cloud_count=len(cloud),front_structure_point_count=int(foreground.sum()),display_hidden_points_not_removed_from_world=True,source_metrics_unchanged={p.name:sha(p) for p in (a.assets/'runlogs').iterdir() if p.name in ['rasc_stage_metrics.json','compare_planning.json','cpu_backend_comparison.json','contact_query_comparison.json']},assets=entries,review='Prototype readability revision; display cut explicitly excludes front wall and unrelated geometry. It is not a new self-filter or collision-world result.'))
 (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>点云可读性V2</title><style>body{font:18px system-ui;max-width:1400px;margin:30px auto;color:#263d52}img{width:100%}a{color:#28649a}</style><h1>点云可读性试版：全景、剖切、薄层剖面</h1><p>所有原始数据和规划不变。剖切仅影响显示，图注列出保留/隐藏点数。旧版保留。</p>'+''.join(f'<h2>{i+1}. {e["path"]}</h2><a href="{e["path"]}"><img src="{e["path"]}"></a>' for i,e in enumerate(entries)))
 # Keep the original pack intact; register a separately reviewed prototype supplement.
 manifest_path=out/'MANIFEST.json';manifest=load(manifest_path)
 for name in ['comparison_v1_v2.png','section_old_new_pair.png']:
  manifest['assets'].append(dict(path=name,source_kind='FROZEN_REPLAY',sha256=sha(out/name),interpretation_limit='Display comparison only; paired sections share geometry and scale. V1/V2 layout comparison is not an algorithm ablation.'))
 manifest['generation_script_sha256']=sha(Path(__file__));manifest['recommended_main_figures']=['02_rear_layer_cutaway.png','section_old_new_pair.png'];manifest['secondary_only']=['03_old_cutaway.png','04_new_cutaway.png'];manifest['review']='Full-depth 37-box wireframe remains visually busy; retain as evidence attachment, not main presentation figure.';save(manifest_path,manifest)
 (out/'README.md').write_text(f'''# 点云可读性V2试版

推荐先看index.html；主图是纯点云局部与section_old_new_pair.png。

## 根因
前方结构占{int(foreground.sum())}/{len(cloud)}点（约{foreground.mean()*100:.1f}%），Y约−0.42m，从−Y侧观察会遮住后层。大范围XYZ网格、文字和全深度包络叠加也压缩了主体。

## 表达分工
1. 全景只交代上下文和前方遮挡，保留全部3747点。
2. 纯点云局部固定BODY范围，显示{len(local)}点；其余只在显示中隐藏，仍保留在世界和规划。
3. 薄层剖面以Z=0.905m、点带宽±6mm显示原始观测；OLD/NEW同范围同7mm膨胀。着色是几何包络，不证明未观测空间可通行。
4. 多基元完整线框仍偏杂，作为审查附件；汇报主图用纯点云形状和剖面对照。

## 后续整套图的重排原则
场景占主体位置，完整审计字段放图注/表格；全景定位、自体过滤局部、支撑/对象局部各用适合的问题区域。不再把六个阶段都缩成同一种小全景。每组OLD/NEW/前后图继续固定相机、裁切与尺度；裁切范围/可见点数必须明示。

本轮未修改点云算法、障碍世界或GPU轨迹，未重跑GPU。MANIFEST.json保存输入与输出哈希；原68张图仍保留。本目录含9张试版/组合PNG，逐张审查后再扩展整套展示风格。
''')
 (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>点云可读性V2试版</title><style>body{font:18px system-ui;max-width:1500px;margin:30px auto;color:#263d52}img{width:100%;height:auto}a{color:#28649a}p{line-height:1.7}details{margin:30px 0}</style><h1>点云可读性V2：局部形状与薄层剖面</h1><p>主图推荐下面两张。原始世界、点云处理和规划不变；剖切只改变显示。</p><h2>局部原始观测：消除前方遮挡</h2><a href="02_rear_layer_cutaway.png"><img src="02_rear_layer_cutaway.png"></a><h2>同层对照：包络差异清楚，点位保持一致</h2><a href="section_old_new_pair.png"><img src="section_old_new_pair.png"></a><details><summary>展开全景、完整线框与审查辅助图</summary>'+''.join(f'<h3>{e["path"]}</h3><a href="{e["path"]}"><img loading="lazy" src="{e["path"]}"></a>' for e in entries if e['path']!='02_rear_layer_cutaway.png')+'</details><p><a href="README.md">表达方案与审查</a> · <a href="MANIFEST.json">溯源</a></p>')
 files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS');(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in files))
 root_manifest=load(a.assets/'ASSET_MANIFEST.json');root_manifest['supplemental_bundles']=[dict(path='clarity_v2/MANIFEST.json',sha256=sha(out/'MANIFEST.json'),status='READABILITY_PROTOTYPE_REVIEWED',independent_pngs=9,original_assets_preserved=True)];root_manifest['generation_scripts_sha256']['tools/presentation_evidence/render_clarity_v2.py']=sha(Path(__file__));save(a.assets/'ASSET_MANIFEST.json',root_manifest)
 note='新增：[点云可读性V2试版](clarity_v2/index.html)（9张，独立于原68张；含显示剖切与薄层对照）。\n\n'
 rp=a.assets/'README.md';text=rp.read_text()
 if '点云可读性V2试版' not in text:rp.write_text(text.replace('\n\n','\n\n'+note,1))
 ip=a.assets/'index.html';text=ip.read_text()
 if 'clarity_v2/index.html' not in text:ip.write_text(text.replace('<main>','<p><a href="clarity_v2/index.html">新增：点云可读性V2试版（局部＋剖面）</a></p><main>',1))
 files=sorted(p for p in a.assets.rglob('*') if p.is_file() and p!=a.assets/'SHA256SUMS');(a.assets/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(a.assets).as_posix()+'\n' for p in files))
 print(json.dumps(dict(assets=len(entries),cloud=len(cloud),front_structure=int(foreground.sum()),local_display=len(local),section_points=len(near))))
if __name__=='__main__':main()
