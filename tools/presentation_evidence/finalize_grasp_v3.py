#!/usr/bin/env python3
"""Assemble a stand-alone GRASP viewer, measured charts and reproducible evidence."""
import argparse, csv, hashlib, io, json, platform, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
from render_grasp_v3 import plt, FONT, NAMES
from replay_rasc import ROOT, load, save, sha
sys.path.insert(0,str(ROOT/'src'))
from ares_r.motion.independent_path_validation import _urdf_joint_origins

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--private',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--model',type=Path,required=True);a=p.parse_args()
    out=a.output;study=a.source/'worklog/evidence/20261021-center-grasp-planner-study'
    m=load(out/'runlogs/rasc_stage_metrics.json');v=load(out/'VISUAL_MANIFEST.json');gpu=load(out/'runlogs/grasp_gpu_replay.json');ab=load(out/'runlogs/compare_planning.json')
    plan=load(a.private/'source_refined_planning.json');req=load(a.private/'source_refined_request.json')
    def chart(fig,name,title,note,kind='FROZEN_REPLAY'):
        fig.text(.07,.96,title,fontsize=20,weight='bold',va='top',color='#203b51');fig.text(.07,.89,note,fontsize=11,va='top',linespacing=1.5,color='#465c70')
        fig.text(.07,.025,kind+' / GRASP Oct21 / NO PHYSICAL MOTION',fontsize=10,color='#465c70')
        target=out/name;target.parent.mkdir(exist_ok=True,parents=True)
        fig.savefig(str(target)+'.png',dpi=200,facecolor='white');fig.savefig(str(target)+'.svg',facecolor='white');plt.close(fig)
    # Directly read historical raw receipts. These are never labeled Ubuntu remeasurements.
    independent=load(study/'independent-backend-comparison.json');query=load(study/'contact-index-comparison.json')
    h=[['Dense world check',independent['runs'][0]['wall_s'],independent['runs'][1]['wall_s']],
       ['Contact geometry',load(study/'contact-build-reference.json')['wall_s'],query[1]['wall_s']],
       ['Pregrasp preparation',load(study/'prepare-pregrasp-only-timing.json')['wall_s'],load(study/'indexed-prepare-timing.json')['wall_s']]]
    save(out/'runlogs/historical_performance.json',dict(source_kind='HISTORICAL_EXTRACT',rows=h,source_sha256={n:sha(study/n) for n in ['independent-backend-comparison.json','contact-build-reference.json','contact-index-comparison.json','prepare-pregrasp-only-timing.json','indexed-prepare-timing.json']},scope='Original Oct21 site CPU receipts; no local remeasurement claim'))
    fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(top=.73,bottom=.18,left=.12,right=.95);x=np.arange(3)
    ax.bar(x-.18,[r[1] for r in h],width=.36,label='Before',color='#bd7359');ax.bar(x+.18,[r[2] for r in h],width=.36,label='After',color='#16836d');ax.set_xticks(x,[r[0] for r in h]);ax.set_ylabel('Seconds');ax.legend()
    for i,r in enumerate(h):
        for xx,value in [(i-.18,r[1]),(i+.18,r[2])]:ax.text(xx,value+.25,f'{value:.3f}',ha='center',fontsize=11)
    chart(fig,'metrics/historical_cpu','历史同输入CPU优化：直接来自原始实验记录','431 dense samples unchanged / contact artifact revision equal / preparation scope only\n这些是10月21日原始记录，不是本轮Ubuntu重测，也不是完整抓取时长。','HISTORICAL_EXTRACT')
    t=gpu['timing_s'];labels=['CUDA import','World / init','World update','GPU solve wall','Post validation'];values=[t['cuda_import'],t['curobo_world_and_planner_init'],t['world_update_samples'][0],t['planning_samples'][0],t['postprocess_and_validation']]
    fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(top=.73,bottom=.22,left=.12,right=.95);ax.bar(labels,values,color='#337f89');ax.set_ylabel('Software wall seconds');ax.tick_params(axis='x',rotation=12)
    for i,x in enumerate(values):ax.text(i,x+.15,f'{x:.3f}',ha='center')
    chart(fig,'metrics/gpu_time','本轮RTX3080真实cuRobo预抓取重放',f'Original refined world / {len(plan["trajectory_points_rad"])} saved joint samples / SUCCESS + independent world PASS\n初始化/求解/后验证为不同计时范围；不是native运动时间。独立验证不另检self-collision。')
    fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(top=.73,bottom=.18,left=.12,right=.95);clear=np.asarray(plan['planner_clearance_trace_m'])*1000;ax.plot(np.linspace(0,1,len(clear)),clear,color='#16836d');ax.axhline(0,color='#b75b47',ls='--');ax.set(xlabel='Trajectory sample progress (not physical time)',ylabel='cuRobo modeled clearance [mm]');ax.grid(alpha=.15)
    chart(fig,'planning/planner_clearance','真实GPU轨迹的模型净空',f'Independent CPU minimum: {gpu["independent_dense_validation"]["min_clearance_m"]*1000:.3f}mm / original contact exemption retained\n曲线为planner trace；独立验证最小值单独列示。orientation=FREE，不声称水平姿态通过。')
    # Recompute pinned URDF FK from every saved q sample; match saved TCP positions.
    origins=_urdf_joint_origins(a.model/'jaka_minicobo_gripper.urdf');T=np.asarray(req['T_body_model']);tool=np.asarray(req['T_link6_tcp']);chains=[]
    for q in plan['trajectory_points_rad']:
        frame=T.copy();chain=[frame[:3,3].copy()]
        for origin,angle in zip(origins,q):
            c,s=np.cos(angle),np.sin(angle);R=np.eye(4);R[:2,:2]=[[c,-s],[s,c]];frame=frame@origin@R;chain.append(frame[:3,3].copy())
        chain.append((frame@tool)[:3,3]);chains.append(chain)
    chains=np.asarray(chains);tcp=np.asarray(plan['tcp_path_body_m']);fk_error=float(np.max(np.linalg.norm(chains[:,-1]-tcp,axis=1)));assert fk_error<1e-8
    save(out/'runlogs/trajectory_fk_receipt.json',dict(source_kind='FROZEN_REPLAY',samples=len(chains),max_tcp_error_m=fk_error,urdf_sha256=sha(a.model/'jaka_minicobo_gripper.urdf'),plan_sha256=sha(a.private/'source_refined_planning.json'),source='Every saved cuRobo joint sample, independent URDF FK; no native retiming; GIF timing is presentation timing'))
    e,az=np.deg2rad([26,-110]);normal=np.array([np.cos(e)*np.cos(az),np.cos(e)*np.sin(az),np.sin(e)]);right=np.array([-np.sin(az),np.cos(az),0]);up=np.cross(normal,right);P=np.c_[right,up]
    cloud=np.load(study/'pick-epoch/live_scene/scene/clean_residual.npz');cloud=cloud[cloud.files[0]];dots=cloud@P;allxy=chains.reshape(-1,3)@P;lo=np.minimum(dots.min(0),allxy.min(0));hi=np.maximum(dots.max(0),allxy.max(0));margin=(hi-lo)*.08
    def motion_frame(index):
        fig=plt.figure(figsize=(12,7));ax=fig.add_axes([.05,.13,.90,.62]);ax.set_aspect('equal');ax.axis('off');ax.set(xlim=(lo[0]-margin[0],hi[0]+margin[0]),ylim=(lo[1]-margin[1],hi[1]+margin[1]))
        ax.scatter(dots[:,0],dots[:,1],s=1.8,color='#afbac0',linewidths=0,rasterized=True);q=tcp@P;ax.plot(q[:,0],q[:,1],color='#cd7743',lw=2,label='actual cuRobo TCP path')
        xy=chains[index]@P;ax.plot(xy[:,0],xy[:,1],'-o',color='#236c86',lw=5,ms=5,label='pinned URDF FK skeleton');ax.scatter(*xy[-1],s=85,c='#cc563e',zorder=5);ax.legend(loc='upper left',frameon=False,fontsize=10)
        fig.text(.05,.96,'真实cuRobo预抓取：保存关节序列驱动pinned URDF FK',fontsize=20,weight='bold',va='top');fig.text(.05,.89,f'sample {index+1}/{len(chains)} · MODEL REFERENCE skeleton · original archived refined world\nFREE orientation / pregrasp only / presentation timing, no native retiming or robot readback',fontsize=11,va='top');fig.text(.05,.035,'FROZEN_REPLAY / REAL CUROBO TRAJECTORY / NO PHYSICAL MOTION',fontsize=10)
        return fig
    fig=motion_frame(len(chains)//2);fig.savefig(out/'planning/real_gpu_fk.png',dpi=200);fig.savefig(out/'planning/real_gpu_fk.svg');plt.close(fig)
    frames=[]
    for index in np.linspace(0,len(chains)-1,32,dtype=int):
        fig=motion_frame(index);buf=io.BytesIO();fig.savefig(buf,format='png',dpi=90);plt.close(fig);buf.seek(0);frames.append(Image.open(buf).convert('RGB'))
    frames[0].save(out/'planning/real_gpu_fk.gif',save_all=True,append_images=frames[1:],duration=160,loop=0)
    # Explicit failed same-input endpoints, not invented routes through invalid goals.
    fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(top=.73,bottom=.18,left=.12,right=.95);gaps=[r['endpoints']['goal']['min_clearance_m']*1000 for r in ab['rows']];ax.bar(['OLD goal','NEW goal'],gaps,color=['#bd7359','#16836d']);ax.axhline(0,color='#2c4557');ax.set_ylabel('Independent goal gap [mm]')
    for i,x in enumerate(gaps):ax.text(i,x/2,f'{x:.2f}mm\nBLOCKED',ha='center',color='white',weight='bold')
    chart(fig,'planning/strict_ab_endpoints','严格几何A/B：两者目标端点均碰撞','Same q0 / qgoal / geometry / 7mm padding / no contact exemption in either world\n未为该A/B求解GPU路径；不能把另一个归档细化世界的成功结果移植到这里。')
    reduction=100*(1-m['new_inflated_sum_volume_m3']/m['old_inflated_sum_volume_m3'])
    summary=f'''<table><tr><th>项</th><th>本轮结果</th><th>解释</th></tr>
    <tr><td>真实GRASP六阶段</td><td>2,304,000 → 2,056,200 → 15,655 → 15,014 → 8,100</td><td>CAMERA/mm → BODY/m逐点位级一致；641点归属过滤</td></tr>
    <tr><td>几何对照</td><td>19 AABB → 405基元；{reduction:.1f}% padded sum volume reduction</td><td>8,100/8,100原始基元覆盖；416个编译障碍；非并集体积</td></tr>
    <tr><td>真实GPU预抓取</td><td>SUCCESS；241关节样本；独立净空3.706mm</td><td>原归档细化世界；orientation=FREE；保留原接触目标豁免；不能认证contact/lift</td></tr>
    <tr><td>严格OLD/NEW规划对照</td><td>两者目标端点碰撞</td><td>同7mm、无接触豁免；未启动无效端点GPU求解</td></tr>
    <tr><td>归档一致性</td><td>8,086 → 本轮8,100；归档点全部保留</td><td>额外14点在small-cluster保留边界；尚未定位完整版本/浮点根因，不宣称逐点历史复现</td></tr>
    </table>'''
    groups=[('六阶段局部主图',[(f'panels/rasc6/{n}_iso_focus.png',TITLES_LABEL) for n,TITLES_LABEL in zip(NAMES,['原始观测','ROI','自体过滤（归属点在左侧，另见专用局部）','几何分层','多基元线框','编译世界'])]),
            ('自体过滤：同一局部与尺度',[(f'details/ownership_{n}.png',label) for n,label in [('before','过滤前'),('after','过滤后'),('removed','移除点')]]),
            ('分层与几何剖面',[(f'details/{n}.png',label) for n,label in [('target_observation','纯点云局部'),('target_roles','几何类别')]]+[(f'geometry_ab/pair_section_z{z:.2f}.png',f'OLD/NEW Z={z:.2f}m') for z in [.90,.94,.98]]),
            ('规划与性能',[(f'{n}.png',label) for n,label in [('planning/real_gpu_fk','真实GPU轨迹与URDF FK'),('planning/strict_ab_endpoints','严格A/B端点拒绝'),('planning/planner_clearance','模型净空'),('metrics/timing','本轮CPU耗时'),('metrics/counts','点数'),('metrics/volume','几何体积'),('metrics/gpu_time','本轮GPU软件耗时'),('metrics/historical_cpu','历史优化')]])]
    gallery=''
    for title,items in groups:
        gallery+=f'<h2>{title}</h2><div class="grid">'
        for name,label in items:
            svg=Path(name).with_suffix('.svg').as_posix();link=f' · <a href="{svg}">SVG</a>' if (out/svg).exists() else ''
            gallery+=f'<article class="card"><h3>{label}</h3><a href="{name}"><img loading="lazy" src="{name}"></a><a href="{name}">原尺寸PNG</a>{link}</article>'
        gallery+='</div>'
    gallery+='<h2>可播放的真实GPU关节序列</h2><a href="planning/real_gpu_fk.gif"><img class="hero" loading="lazy" src="planning/real_gpu_fk.gif"></a><p>仅预抓取，GIF以样本进度播放；不代表native或实机运动时长。</p><details><summary>完整三视角六阶段审查图</summary>'
    for view in ['iso','front','top']:
        gallery+=f'<h3>{view.upper()}</h3><div class="grid">'+''.join(f'<a href="panels/rasc6/{n}_{view}.png"><img loading="lazy" src="panels/rasc6/{n}_{view}.png"></a>' for n in NAMES)+'</div>'
    gallery+='</details>'
    template=(ROOT/'tools/presentation_evidence/grasp_v3_viewer.html').read_text();payload=(out/'viewer_data.json').read_text().replace('</','<\\/')
    (out/'index.html').write_text(template.replace('__SUMMARY__',summary).replace('__GALLERY__',gallery).replace('__PAYLOAD__',payload))
    (out/'README.md').write_text(f'''# GRASP V3：真实点云完整六阶段

直接打开 **index.html**。交互点云内嵌、无需服务器/网络，原始包不必随图集携带。图片、SVG、GIF可单独使用。

## 输入与复算
数据分支 `codex/data-grasp-20261021-public`，固定提交 `dc70016a8fc95d8d0e6efb52ef935d5cec9d408e`。两份完整tar均通过SHA256，源许可见原数据目录PUBLICATION.md。
GRASP `right_pick` / ID1 / `{m['historical_scene_id']}` / `{m['observation_id']}`。
CAMERA SHA256 `{m['source_camera_sha256']}`；BODY SHA256 `{m['body_sha256']}`。
CAMERA单位mm，BODY单位m；有效点经固定TF转为float32与归档BODY完全相等，不重复转换。
同帧双臂诊断关节与geometry一致、capture前后最大变化0；过滤revision完全一致。过滤仅覆盖模型中声明owned的OBB/sphere，不保证未知机器人部件。

## 实际结果
原始2,304,000 → 有效2,056,200 → ROI体素15,655 → 外部15,014 → 清理8,100；自体移除641。
19单AABB → 405多基元，原始未膨胀基元逐点覆盖8,100/8,100；两组统一7mm膨胀。SceneCompiler输出416 cuboids，实际编译角点映回BODY最大中心误差{v['compiler_max_center_roundtrip_error_m']:.3g}m。
膨胀盒体积和{m['old_inflated_sum_volume_m3']:.8f} → {m['new_inflated_sum_volume_m3']:.8f} m³（减少{reduction:.1f}%，不是并集）。
原始归档清理8,086点/18簇/390多基元/401编译障碍；当前归档点全部有精确匹配，另外14点来自small-cluster保留差异。当前版本与归档并非逐点相同。

## 规划证据分组
1. **本轮严格几何A/B**：同一q0/qgoal与统一7mm，两个世界均不继承旧目标ID的contact豁免；OLD/NEW端点均碰撞，因此拒绝进入GPU求解。见compare_planning.json。不能称为OLD失败/NEW成功。
2. **本轮真实GPU重放**：原始归档refined55请求，完整保留世界、起终点、40%夹爪模型与目标contact豁免；只迁移pinned URDF/YAML路径。cuRobo SUCCESS + 独立world PASS，241样本，净空3.706mm，GPU峰值allocated {gpu['gpu_memory_bytes']['peak_allocated']/2**20:.1f}MiB、reserved {gpu['gpu_memory_bytes']['peak_reserved']/2**20:.1f}MiB。源request为orientation=FREE，无水平姿态证明；独立validator不独立检查self-collision。该世界与重建统一AABB消融世界不同。
3. GIF及FK静帧由本轮实际保存的关节序列驱动pinned URDF，FK TCP与保存路径误差{fk_error:.3g}m。仅骨架模型参考、非CAD外观；GIF按样本播放，不冒充native重定时或JAKA反馈。
4. contact/lift预检的历史IK失败保留；本包不能声称整次抓取可执行。未产生新的JAKA真实反馈，旧V1历史反馈曲线不可标为本GRASP帧。

## 可读性与审查
主视图BODY −Y朝+Y，纯观测、角色分层与几何包络分开；OLD/NEW固定尺度。局部裁切仅显示，不删除桌面/dock/隔板。焦点图使用同一清理后点投影范围+18%边距；原始/包络超出投影框部分可能裁切，完整三视角附图保留固定BODY范围。薄层为Z=.90/.94/.98m，点带宽±6mm。
PNG为2400×1600（剖面2000×1600），组合剖面3200×1280；SVG内点层栅格化、线/文字可编辑。完整矩阵24张，主图不把六张全景缩到一页。
体素ROI不代表解析IK可达集；无观测空间不等于自由空间；没有RGB、没有表面补洞、没有新实机运动。

## 复现
在本离线工作树执行 `bash tools/presentation_evidence/run_grasp_v3.sh`。脚本只读取固定Git对象/数据文件，处理和GPU阶段均经offline_sandbox隔离设备I/O，仅用GPU0。重放模型来自pinned ARES `b978cbd669b5a3f6bc0bd19defcbe5256692f145`，cuRobo `8e734f3ced1df898990bcd92de40abce475907db`。运行环境与代码hash见MANIFEST.json；runtime YAML为明确披露的离线派生，不等于现场commissioning。
''')
    (out/'REVIEW.md').write_text('''# 真实性、可读性与缺口审查

- 初版已实际检查：局部主体仍被3D边界留白压小、完整线框拥挤。因此二版按同一清理后观测投影放大焦点图，追加六阶段局部矩阵；主报告优先纯点图与薄层对照，完整全景线框移至审查折叠区。
- 核对源包SHA、CAMERA→BODY位级一致、同帧双臂状态、过滤revision、实际编译世界坐标回转、逐点覆盖。原始现场包和V1/V2不修改。
- 发现已清理的突出物边界网格2点被minimum_points门槛二次丢弃。独立修复后新增1基元，未膨胀覆盖8098/8100→8100/8100；4项分解回归通过。原7mm膨胀覆盖本来为全覆盖，不能声称修复前物理碰撞已发生。
- 当前清理8100与归档8086差14点；归档所有点精确保留。差异定位到small_cluster_removed149→135、kept_clusters18→19；完整源版本/数值边界根因尚未证实。保留当前实测与原始值，不改成历史数字。
- OLD/NEW重新编译后目标组件编号不再稳定。旧contact ignore ID不能跨表示复用；对照统一取消豁免，端点碰撞直接拒绝。首轮元数据不匹配失败单独存档，不伪称GPU碰撞求解失败。
- 原归档细化请求真实GPU SUCCESS保留原contact合同，orientation FREE，只有预抓取。与统一7mm几何对照分组，不能混用。
- 缺口：本帧完整contact/lift通过证据、水平姿态约束求解证明、完整JAKA目标/反馈正常结束轨迹、现场runtime YAML等效性、完整GRASP→PLACE→GRASP本帧物理回放。SITE_PENDING，不阻塞本点云六阶段素材。
- HTML纯离线，Canvas仅显示真实点序列/实际编译盒，无合成表面；截图QA与交互检查见browser_qa.json（如已生成）。
''')
    from scipy.spatial import cKDTree
    current=np.load(a.private/'rasc_arrays.npz')['clean'];arch=np.load(study/'pick-epoch/live_scene/scene/clean_residual.npz');arch=arch[arch.files[0]]
    forward=cKDTree(arch).query(current)[0];reverse=cKDTree(current).query(arch)[0]
    save(out/'runlogs/coverage_and_archive_audit.json',dict(source_kind='FROZEN_REPLAY',archived_clean_sha256=sha(study/'pick-epoch/live_scene/scene/clean_residual.npz'),archived_count=len(arch),current_count=len(current),archive_points_without_match_at_1e8=int((reverse>1e-8).sum()),current_points_without_archive_match_at_1e8=int((forward>1e-8).sum()),new_uninflated_point_coverage=m['new_point_coverage'],before_fix_uninflated_point_coverage=8098,before_fix_clean_points=8100,after_fix_primitive_count=405,before_fix_primitive_count=404,fix='fc3a396',regression_result='4 tests PASS; test_support_decomposition.py',root_cause='Protrusion already labeled but boundary tile below second minimum_points threshold skipped',historical_cleanup_difference='small_cluster_removed149->135; full original version/numerical boundary cause unproven'))
    save(out/'runlogs/initial_ab_metadata_rejection.json',dict(source_kind='FROZEN_REPLAY',result='REJECTED_BEFORE_VALID_GPU_COMPARISON',old_error="RuntimeError: ignore_cuboid_ids names objects the scene does not contain: ['observed_support_02_component_01_protruding']",resolution='Do not reuse contact target IDs across representations; strict uniform-padding A/B uses no contact exemption in BOTH worlds. Retain archived refined request as a separate GPU replay.'))
    # Runtime measurements remain frozen; generation only indexes their hashes.
    scripts=['qa_grasp_v3.cjs','verify_grasp_v3.py','prepare_model.py','replay_rasc.py','compute_comparisons.py','fetch_grasp_v3.py','render_grasp_v3.py','replay_grasp_gpu.py','finalize_grasp_v3.py','grasp_v3_viewer.html','run_grasp_v3.sh']
    manifest=dict(source_data_commit='dc70016a8fc95d8d0e6efb52ef935d5cec9d408e',source_archives=load(a.source.parents[0]/'DATA_INDEX.json')['archives'] if (a.source.parent/'DATA_INDEX.json').exists() else [],
        source_camera_sha256=m['source_camera_sha256'],source_kind='FROZEN_REPLAY',source_geometry_sha256=m['source_geometry_sha256'],original_snapshot_sha256=m['original_snapshot_sha256'],
        code_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),python=sys.version,platform=platform.platform(),
        generation_scripts_sha256={str(Path('tools/presentation_evidence')/n):sha(ROOT/'tools/presentation_evidence'/n) for n in scripts if (ROOT/'tools/presentation_evidence'/n).exists()},
        algorithm_source_sha256={n:sha(ROOT/n) for n in ['src/ares_r/perception/support_decomposition.py','src/ares_r/perception/residual_cloud.py','src/ares_r/perception/robot_owned_filter.py','src/ares_r/world/scene_compiler.py','src/ares_r/motion/production_scene_worker.py']},
        status=dict(REAL_GRASP_SOURCE='PASS',SIX_STAGE_REPLAY='PASS',RAW_BODY_BIT_EXACT='PASS',ROBOT_STATE_BINDING='PASS',POINT_COVERAGE='PASS',ARCHIVED_CLEAN_EXACT_REPRODUCTION='PARTIAL',GEOMETRY_AB='PASS',UNIFORM_AB_GPU_PATH='BLOCKED_ENDPOINT_COLLISION',ARCHIVED_REFINED_REAL_GPU='PASS',PHYSICAL_GRASP='SITE_PENDING'),
        no_physical_io=True,visual_manifest_sha256=sha(out/'VISUAL_MANIFEST.json'),files=[])
    for file in sorted(out.rglob('*')):
        if file.is_file() and file.name not in ['MANIFEST.json','SHA256SUMS']:
            manifest['files'].append(dict(path=file.relative_to(out).as_posix(),bytes=file.stat().st_size,sha256=sha(file)))
    save(out/'MANIFEST.json',manifest)
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    print(json.dumps(dict(files=len(manifest['files']),fk_max_error_m=fk_error,status=manifest['status'])))

if __name__=='__main__':main()
