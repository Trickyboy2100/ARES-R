#!/usr/bin/env python3
import base64,json,sys,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(Path(__file__).parent))
from build_replay import build,OUT,write,SOURCE
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
STAMP='SYNTHETIC SCENE / REAL CUROBO TRAJECTORY / NO PHYSICAL MOTION'

def main():
 data=build();stages=data['stages'];n=len(stages);idx=np.arange(n);fig,axes=plt.subplots(3,2,figsize=(17,15))
 ax=axes[0,0];left=np.zeros(n)
 for key,label,color in [('software_wall_s','Actual software wall','#447eb7'),('native_motion_s','Native expected movement','#36906e'),('base_nominal_s','Nominal base (no odometry)','#ba8e4e')]:
  values=[s[key] for s in stages];ax.barh(idx,values,left=left,label=label,color=color);left+=values
 ax.set_yticks(idx,[s['id'] for s in stages],fontsize=8);ax.invert_yaxis();ax.set_xlabel('seconds, separate clocks');ax.legend(fontsize=8);ax.set_title('19 stages: measured vs estimated vs nominal')
 gpu=[s for s in stages if s['gpu']];labels=['PREGRASP\ncold','HOLD230\ncold','PRELAND40\nwarm'];x=np.arange(3);ax=axes[0,1]
 solver=[]
 for label in ('PREGRASP','HOLD230','PRELAND40'):
  r=json.loads(next(SOURCE.glob('plan_'+label+'*/planning.json')).read_text());solver.append(sum(r['timing_s']['planning_samples']))
 ax.bar(x-.16,[s['gpu']['wall_s'] for s in gpu],.32,label='GPU pipeline wall (IPC/init/validation)',color='#447eb7');ax.bar(x+.16,solver,.32,label='Solver wall, CUDA synchronized',color='#36906e');ax.set_xticks(x,labels);ax.set_ylabel('actual seconds (not CUDA event time)');ax.legend(fontsize=8);ax.set_title('Real GPU solve timing; no invented device-only clock')
 ax=axes[1,0];moves=[s for s in stages if s['level']];v=[s['level']['max_level_error_deg'] for s in moves];ax.bar(np.arange(5),v,color='#447eb7');ax.set_xticks(np.arange(5),['pregrasp','contact','lift100','hold230','preland']);ax.set_ylabel('degrees');ax.set_title('Native URDF/FK maximum horizontal error; limit 3 degrees')
 for i,y in enumerate(v):ax.text(i,y,f'{y:.5f}',ha='center',va='bottom',fontsize=8)
 ax.set_ylim(0,max(v)*1.35+.0001)
 ax=axes[1,1];avoid=data['near_cases'][1]['result']['independent_dense_validation']['min_clearance_m'];vals=[s['clearance']*1000 for s in gpu]+[data['blocked_original']['min_clearance_m']*1000,avoid*1000];ax.bar(np.arange(5),vals,color=['#447eb7']*3+['#d35b61','#36906e']);ax.axhline(0,color='#333',lw=.7);ax.set_xticks(range(5),['RC pregrasp','RC hold','RC place','Old path\nnew obstacle','New AVOID']);ax.set_ylabel('mm, signed world clearance');ax.set_title('Independent world collision checks (contact/lift clearance N/A)')
 for i,y in enumerate(vals):ax.text(i,y,f'{y:.2f}',ha='center',va='bottom' if y>=0 else 'top',fontsize=8)
 ax=axes[2,0];ax.bar(x-.17,[s['gpu']['gpu_memory_bytes']['peak_allocated']/1048576 for s in gpu],.34,label='peak allocated',color='#447eb7');ax.bar(x+.17,[s['gpu']['gpu_memory_bytes']['peak_reserved']/1048576 for s in gpu],.34,label='peak reserved',color='#8c75b9');ax.set_xticks(x,labels);ax.set_ylabel('MiB, actual PyTorch counters');ax.set_title('Single-GPU offline memory; NOT site 10GB coexistence');ax.legend()
 ax=axes[2,1];from ares_r.motion.runtime_goal_ik import RuntimeGoalIK
 ik=RuntimeGoalIK(ROOT/'worklog/runtime/preview-model/robot.urdf',data['body'],data['tool']);grasp=ik.fk(stages[3]['q'][-1])[2,3]
 for s in stages:
  if not s['native_dt']:continue
  t=s['start']+s['compute_dwell_s']+np.arange(len(s['q']))*s['native_dt'];z=[(ik.fk(q)[2,3]-grasp)*1000 for q in s['q']];ax.plot(t,z,label=s['id'])
 ax.axhline(100,color='#888',ls='--',lw=.7);ax.axhline(230,color='#888',ls='--',lw=.7);ax.set_xlabel('modeled display clock, seconds');ax.set_ylabel('mm above saved grasp FK');ax.set_title('TCP height from saved native joints, not real feedback');ax.legend(fontsize=7)
 fig.suptitle('ARES-R RC1 | Evidence-derived engineering view\n'+STAMP,fontsize=13);fig.tight_layout(rect=(0,0,1,.95));fig.savefig(OUT/'stage_engineering_metrics.png',dpi=130);fig.savefig(OUT/'stage_engineering_metrics.svg');plt.close(fig)
 fig,ax=plt.subplots(figsize=(11,5));names=['Contact: same synthetic source path','Lift100: same synthetic source path'];old=[data['retiming'][k]['legacy_same_path_native_duration_s'] for k in ('contact','lift')];new=[data['retiming'][k]['rc_native_duration_s'] for k in ('contact','lift')];x=np.arange(2)
 ax.bar(x-.18,old,.36,label='Legacy native retiming',color='#a87b82');ax.bar(x+.18,new,.36,label='RC1 native, revalidated',color='#3d9274')
 for i in range(2):ax.text(i-.18,old[i],f'{old[i]:.2f}s',ha='center',va='bottom');ax.text(i+.18,new[i],f'{new[i]:.2f}s',ha='center',va='bottom')
 ax.set_xticks(x,names);ax.set_ylabel('expected native movement seconds');ax.set_ylim(0,118);ax.legend();ax.set_title('Same velocity/acceleration caps; geometry/collision/pose/dynamics revalidated');fig.suptitle(STAMP,fontsize=10);fig.text(.5,.015,'NOT a replay of the missing Oct16 115s / 72s original paths',ha='center',fontsize=11);fig.tight_layout(rect=(0,.04,1,.93));fig.savefig(OUT/'native_retiming_comparison.png',dpi=130);fig.savefig(OUT/'native_retiming_comparison.svg');plt.close(fig)
 def embedded(path):return '<img alt="'+path.stem+'" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'">'
 template=(Path(__file__).parent/'replay_template.html').read_text();renderer=(Path(__file__).parent/'replay_renderer.js').read_text()
 gaps=(OUT/'adapter_review_fragment.html').read_text() if (OUT/'adapter_review_fragment.html').exists() else '正式Live合同审查结果见 visuals/README.md；缺键、释放状态与Stop晚到计划保护已加入合同回归。现场SDK与物理反馈仍待验收。'
 html=template.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')).replace('__RENDERER__',renderer).replace('__CHARTS__',embedded(OUT/'stage_engineering_metrics.png')).replace('__RETIMING__',embedded(OUT/'native_retiming_comparison.png')).replace('__GAPS__',gaps)
 video=OUT/'full_cycle_replay.mp4'
 if video.exists():
  html=html.replace('__VIDEO__','<video controls preload="metadata" style="width:100%;max-height:720px" src="data:video/mp4;base64,'+base64.b64encode(video.read_bytes()).decode()+'"></video>')
 else:html=html.replace('__VIDEO__','视频文件尚未构建')
 (OUT/'full_cycle_replay.html').write_text(html)
 target=OUT/'near_obstacle_evidence';target.mkdir(exist_ok=True)
 for path in (ROOT/'worklog/runtime/visual-near-obstacles').rglob('*'):
  if path.is_file() and path.suffix in ('.json','.log'):
   to=target/path.relative_to(ROOT/'worklog/runtime/visual-near-obstacles');to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,to)
 print('standalone HTML bytes',len(html.encode()),'time',data['total_display_s'])
if __name__=='__main__':main()
