"""Focused source-based views: parameter sweep, measured recovery, GPU path receipts."""
import argparse,sys,time,json,csv
from pathlib import Path
import numpy as np
from dataclasses import replace
from render_assets import Renderer
from replay_rasc import save,load,sha
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ares_r.perception.support_decomposition import DecompositionProfile,decompose_support_objects
from ares_r.demo_workbench import timing_report
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=Renderer(a);sweep=[];cloud=r.arr['clean']
sweep_path=a.output/'runlogs/geometry_complexity_sweep.json'
if sweep_path.exists():
 sweep=load(sweep_path)['runs'];assert all(x['total_points']==len(cloud) for x in sweep)
else:
 for tile in [.02,.04,.06]:
  times=[]
  for _ in range(4):
   at=time.perf_counter();d=decompose_support_objects(cloud,[],replace(DecompositionProfile(),tile_xy_m=tile));times.append((time.perf_counter()-at)*1000)
  covered=np.zeros(len(cloud),bool)
  for b in d['primitives']:covered|=np.all(np.abs(cloud-b['center_m'])<=np.asarray(b['dims_m'])/2+1e-9,axis=1)
  sweep.append(dict(tile_xy_m=tile,slice_z_m=.03,padding_m=.007,k=len(d['primitives']),covered_points=int(covered.sum()),total_points=len(cloud),sum_padded_volumes_m3=sum(np.prod(np.asarray(b['dims_m'])+.014) for b in d['primitives']),cold_ms=times[0],warm_ms=times[1:],warm_median_ms=float(np.median(times[1:]))))
fig=r.figure();ax=fig.add_subplot()
for v in sweep:
 ax.scatter(v['k'],v['sum_padded_volumes_m3'],s=110,color='#298c7a');ax.annotate(f"tile {v['tile_xy_m']*1000:.0f}mm\n{v['covered_points']}/{v['total_points']} points\nCPU {v['warm_median_ms']:.1f}ms",(v['k'],v['sum_padded_volumes_m3']),xytext=(12,10),textcoords='offset points',fontsize=13)
ax.margins(.4);ax.set(xlabel='Number of observed primitives',ylabel='Sum of padded box volumes [m³]');ax.grid(alpha=.2);r.finish(fig,'performance/geometry_complexity_tradeoff','分块尺寸改变几何复杂度，不能据此直接决定部署参数','Same Oct10 cleaned points / fixed 7mm inflation / 30mm Z slices\nAll cleaned observations retained; no GPU latency or unseen-space safety inferred',limits='This is a geometry tradeoff, not a validated safety/latency Pareto optimum. Padded boxes overlap.')
save(a.output/'runlogs/geometry_complexity_sweep.json',dict(source_kind='FROZEN_REPLAY',runs=sweep))
events=load(ROOT/'docs/golden/2026-10-19/evidence/v17-place-recovery-completed/events.json');timing=timing_report(events);rows=[x for x in timing['intervals'] if x['stage']!='PLANNING_ATTEMPT'];fig=r.figure();ax=fig.add_subplot();ax.barh([x['stage'] for x in rows],[x['elapsed_s'] for x in rows],color='#3c709a');ax.invert_yaxis();ax.set(xlabel='Historical stage wall [s]');ax.grid(axis='x',alpha=.2)
for i,v in enumerate(rows):ax.text(v['elapsed_s']+.2,i,f"{v['elapsed_s']:.2f}s",va='center',fontsize=12)
ax.set_xlim(0,max(x['elapsed_s'] for x in rows)*1.25);r.finish(fig,'attachments/place_recovery_stage_times','10月19日PLACE故障修正后的接续有真实阶段时间','Historical event timestamps / exclude nested PLANNING_ATTEMPT from additive bars\nThis is recovery execution, not an uninterrupted autonomous full cycle','HISTORICAL_EXTRACT',sha(ROOT/'docs/golden/2026-10-19/evidence/v17-place-recovery-completed/events.json'),limits='No original placement cloud/TF available for a spatial clearance reconstruction. Successful release ≠ verified precise seating.')
save(a.output/'runlogs/place_recovery_timing.json',timing)
# Actual GPU final paths and independent clearance. Never invent intermediate seeds.
paths=[]
for name in ['old','new']:
 p=a.private/(name+'_planning.json')
 if p.exists():
  v=load(p)
  if v.get('observed_result')=='SUCCESS':paths.append((name,v))
if paths:
 fig=r.figure();ax=r.ax3(fig);r.points(ax,r.arr['clean'],s=3)
 for name,v in paths:ax.plot(*np.asarray(v['tcp_path_body_m']).T,c='#ce6345' if name=='old' else '#298c7a',lw=2.5,label=f'{name.upper()} real cuRobo output')
 ax.legend(loc='upper left');r.finish(fig,'planning/route_overlay','同源OLD与NEW的真实GPU轨迹并列保留','Same requested start/target and solver budget • full URDF FK TCP paths\nNo OLD-fail/NEW-success effect is asserted when both pass',source=sha(a.output/'runlogs/compare_planning.json'),limits='Only final selected outputs are exported by worker; no fabricated seed trajectories. Reconstructed offline runtime, no motion.')
 fig=r.figure();ax=fig.add_subplot()
 with (a.output/'tables/gap_vs_path.csv').open('w') as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(['representation','sample_index','normalized_index','gap_m'])
  for name,v in paths:
   gaps=v['independent_dense_validation'].get('clearance_trace_m') or v['planner_clearance_trace_m'];x=np.linspace(0,1,len(gaps));ax.plot(x,np.array(gaps)*1000,lw=2,label=name.upper());w.writerows([[name,i,float(x[i]),g] for i,g in enumerate(gaps)])
 ax.axhline(0,c='#ce6345',ls='--');ax.set(xlabel='Normalized dense path sample index (not time)',ylabel='GPU sphere/world modeled gap [mm]');ax.legend();ax.grid(alpha=.2);r.finish(fig,'planning/gap_vs_path','全路径净空曲线与独立最小净空分别核对','Modeled GPU dense trace; independent CPU minimum in compare_planning.json\nTrace index is not physical time',source=sha(a.output/'runlogs/compare_planning.json'),limits='World validation is independent; independent self-collision coverage remains false. No physical clearance measurement.')
 # Timing layers, cold status kept visible.
 fig=r.figure();ax=fig.add_subplot();labels=[n.upper() for n,v in paths];bottom=np.zeros(len(paths))
 for label,key,c in [('Planner construction','curobo_world_and_planner_init','#a9b3bd'),('Solve','planning_reported_solve','#3c709a'),('Independent CPU check','independent_dense_validation','#298c7a')]:
  values=[v['timing_s'].get(key,0) for n,v in paths];ax.bar(labels,values,bottom=bottom,color=c,label=label);bottom+=values
 ax.set(ylabel='Instrumented interval [s]');ax.legend();r.finish(fig,'performance/gpu_ab_layers','初始化、GPU求解与独立CPU核验属于不同时间层','Matched geometry A/B / both receipts disclose runtime reuse status\nStack contains selected disjoint scopes, not whole-request time',source=sha(a.output/'runlogs/compare_planning.json'),limits='Single request per representation; do not infer P50/P95 or causally attribute latency difference to geometry alone.')
fig=r.figure();ax=fig.add_subplot();ax.axis('off')
rows=[['旧料盘','已有ID1 / 参考位姿','主段160×100 + 后段20','历史完成，含恢复'],['新筛网','新模板 / 抓取锚点','测量厚度与持物归属','接口可复用；未实测'],['新专机泊位','新站位 / 相机 / ID3 TF','新路线与全程碰撞核验','需要现场标定/验收']]
table=ax.table(cellText=rows,colLabels=['任务','对象/目标参数','世界与安全参数','证据状态'],cellLoc='left',loc='center',colWidths=[.14,.27,.34,.25]);table.auto_set_font_size(False);table.set_fontsize(13);table.scale(1,3.8)
for (i,j),cell in table.get_celld().items():cell.set_edgecolor('#d7e1e7');cell.set_facecolor('#edf3f6' if i==0 else 'white')
r.finish(fig,'runtime/task_parameterization_matrix','可迁移的是接口与参数，成功率不能预填','Code/config matrix • new object or berth still requires fresh geometry/calibration/validation','SCHEMATIC',limits='No physical generalization success claimed; full parameter source is tables/task_parameterization_matrix.csv.')
manifest=load(a.output/'ASSET_MANIFEST.json');manifest['assets']=[x for x in manifest['assets'] if x['asset_id'] not in {v['asset_id'] for v in r.manifest}]+r.manifest;save(a.output/'ASSET_MANIFEST.json',manifest)
