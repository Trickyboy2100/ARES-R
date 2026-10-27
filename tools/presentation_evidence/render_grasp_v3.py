#!/usr/bin/env python3
"""Publication figures from authenticated GRASP replay; all crops are display-only."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle, Patch
from scipy.spatial.transform import Rotation
from PIL import Image, ImageDraw, ImageFont
from replay_rasc import load, save, sha

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font_manager.fontManager.addfont(FONT)
plt.rcParams.update({'font.family': ['DejaVu Sans', font_manager.FontProperties(fname=FONT).get_name()],
                     'font.size': 13, 'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False})
SIGNS = np.array([[x, y, z] for x in [-1, 1] for y in [-1, 1] for z in [-1, 1]])
EDGES = [(i, j) for i in range(8) for j in range(i + 1, 8) if bin(i ^ j).count('1') == 1]
COLORS = {'SUPPORT_SURFACE': '#14836b', 'PROTRUDING_OBSTACLE': '#d17337',
          'STRUCTURE': '#3978ae', 'UNKNOWN_OCCUPIED': '#9169a5'}
NAMES = ['01_raw_cloud', '02_roi', '03_robot_owned_filter', '04_support_decomposition', '05_multi_primitive', '06_curobo_world']
TITLES = ['真实GRASP观测：固定外参转入BODY', '工作区域ROI与7.5mm体素采样', '同帧关节与几何：机器人归属过滤',
          '支撑面、突出物、结构与未知观测', '保留全部观测的多基元表示', 'SceneSnapshot → cuRobo手臂坐标系']

def inside(p, bounds):
    return np.all((p >= bounds[0]) & (p <= bounds[1]), axis=1)

def sample(p, limit):
    return p[np.linspace(0, len(p) - 1, min(limit, len(p)), dtype=int)] if len(p) else p

def box_corners(b, padding=0):
    return np.asarray(b['center_m']) + SIGNS * (np.asarray(b['dims_m']) / 2 + padding)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    d, out = args.private, args.output
    out.mkdir(parents=True, exist_ok=True)
    arr = np.load(d / 'rasc_arrays.npz'); m = load(out / 'runlogs/rasc_stage_metrics.json')
    old = load(d / 'old.json'); new = load(d / 'refined.json')['primitives']
    geometry = load(d / 'geometry.json'); report = load(d / 'reference_report.json')
    compiled = load(d / 'new_compiled.json'); T = np.asarray(report['T_body_model'])
    target = np.asarray(m['target_body_m']); entries = []
    # Read actual compiler output (arm-local WXYZ cuboids); map back only for matched BODY views.
    compiled_corners = []
    for name, b in compiled['cuboids'].items():
        pose = b['pose']; rot = Rotation.from_quat([*pose[4:7], pose[3]]).as_matrix()
        local = (SIGNS * (np.asarray(b['dims']) / 2)) @ rot.T + pose[:3]
        body = local @ T[:3, :3].T + T[:3, 3]
        compiled_corners.append((name, body))
    compiler_errors = []
    by_id = dict(compiled_corners)
    for b in new:
        actual = by_id['observed_' + b['primitive_id']].mean(0)
        compiler_errors.append(float(np.linalg.norm(actual - b['center_m'])))
    assert max(compiler_errors) < 1e-9
    role_index = np.full(len(arr['clean']), 3, dtype=int)
    assigned = np.zeros(len(arr['clean']), dtype=bool)
    for i, semantic in enumerate(COLORS):
        mask = np.zeros(len(assigned), dtype=bool)
        for b in new:
            if b['semantic'] == semantic:
                mask |= np.all(np.abs(arr['clean'] - b['center_m']) <= np.asarray(b['dims_m']) / 2 + 1e-9, axis=1)
        role_index[mask & ~assigned] = i; assigned |= mask
    assert assigned.all()
    full = [[.20, -.78, .68], [1.32, .78, 1.42]]
    focus = [[.68, -.27, .85], [1.04, .09, 1.07]]
    ownership = [[.30, -.32, .96], [.44, -.04, 1.12]]
    point_sets = [arr['body'], arr['roi'], arr['roi'], arr['clean'], arr['clean'], arr['clean']]

    def finish(fig, name, title, subtitle, **meta):
        fig.text(.045, .965, title, fontsize=23, weight='bold', va='top', color='#203b51')
        fig.text(.045, .905, subtitle, fontsize=12, va='top', linespacing=1.6, color='#43576b')
        fig.text(.045, .027, 'FROZEN_REPLAY  ·  GRASP Oct21  ·  REAL SENSOR DATA  ·  NO PHYSICAL MOTION', fontsize=10, color='#43576b')
        path = out / name; path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path.parent/(path.name+'.png'), dpi=200, facecolor='white')
        fig.savefig(path.parent/(path.name+'.svg'), facecolor='white'); plt.close(fig)
        entries.append(dict(path=(path.parent/(path.name+'.png')).relative_to(out).as_posix(),
                            svg=(path.parent/(path.name+'.svg')).relative_to(out).as_posix(), source_kind='FROZEN_REPLAY', **meta))

    def frame(bounds, view):
        elev, az = {'iso': (26, -110), 'front': (0, -90), 'top': (90, -90)}[view]
        e, a = np.deg2rad([elev, az]); n = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
        right = np.array([-np.sin(a), np.cos(a), 0]); up = np.cross(n, right)
        P = np.c_[right, up]; q = (np.asarray(bounds[0]) + (SIGNS+1)/2 * (np.asarray(bounds[1])-bounds[0])) @ P
        low, high = q.min(0), q.max(0)
        if bounds == focus:
            fitted=arr['clean'][inside(arr['clean'],focus)]@P
            low,high=fitted.min(0),fitted.max(0)
        c=(low+high)/2; span=(high-low)*1.18
        fig=plt.figure(figsize=(12,8)); ax=fig.add_axes([.045,.11,.91,.67]); ax.set_aspect('equal'); ax.axis('off')
        ax.set(xlim=(c[0]-span[0]/2,c[0]+span[0]/2),ylim=(c[1]-span[1]/2,c[1]+span[1]/2))
        length=.05 if (np.asarray(bounds[1])-bounds[0]).max()<.5 else .2
        origin=low+np.array([span[0]*.025,span[1]*.02]);ax.plot([origin[0],origin[0]+length],[origin[1],origin[1]],lw=3,color='#233e54');ax.text(*(origin+[length/2,span[1]*.025]),f'{length*1000:.0f} mm',ha='center',fontsize=11)
        triad=high-np.array([span[0]*.08,span[1]*.88])
        for v,label,color in zip(np.eye(3),['X','Y','Z'],['#b65743','#328975','#547ab0']):
            vv=v@P*length*.35
            if np.linalg.norm(vv)<1e-8:continue
            ax.annotate('',xy=triad+vv,xytext=triad,arrowprops=dict(arrowstyle='->',color=color,lw=1.3));ax.text(*(triad+vv*1.35),label,color=color,fontsize=10)
        return fig,ax,P,n

    def dots(ax, p, P, n, color='#335a79', size=3, cap=60000):
        p=sample(p,cap); order=np.argsort(p@n); q=p[order]@P
        if not isinstance(color,str):color=np.asarray(color)[order]
        ax.scatter(q[:,0],q[:,1],s=size,c=color,linewidths=0,alpha=1,rasterized=True)
        return len(p)

    def wires(ax, corners, P, color, bounds=None, lw=.6):
        segments=[]
        for cor in corners:
            for i,j in EDGES:
                start,end=cor[i],cor[j];delta=end-start;t0,t1=0.,1.
                if bounds is not None:
                    for k in range(3):
                        if abs(delta[k])<1e-12:
                            if not bounds[0][k]<=start[k]<=bounds[1][k]:t0,t1=1.,0.;break
                        else:
                            a,b=sorted([(bounds[0][k]-start[k])/delta[k],(bounds[1][k]-start[k])/delta[k]])
                            t0=max(t0,a);t1=min(t1,b)
                if t0<=t1:segments.append(np.array([start+t0*delta,start+t1*delta])@P)
        ax.add_collection(LineCollection(segments,colors=color,linewidths=lw,alpha=.8))

    # The complete audit set uses identical BODY bounds and camera for all six stages.
    for view in ['iso','front','top','iso_focus']:
        bounds = focus if view=='iso_focus' else full
        camera = 'iso' if view=='iso_focus' else view
        for stage in range(6):
            fig,ax,P,n=frame(bounds,camera); p=point_sets[stage]; mask=inside(p,bounds); visible=p[mask]
            if stage==3:dots(ax,visible,P,n,np.array(list(COLORS.values()))[role_index[mask]],size=4)
            else:dots(ax,visible,P,n,size=1.2 if stage==0 else 3)
            if stage==2:
                dots(ax,arr['removed'],P,n,'#db6738',size=8)
                ax.legend(handles=[Patch(color='#335a79',label='外部保留点'),Patch(color='#db6738',label='机器人归属点（高亮叠加）')],loc='upper left',frameon=False)
            if stage==3:
                ax.legend(handles=[Patch(color=c,label=k) for k,c in COLORS.items()],loc='upper left',frameon=False,fontsize=10)
            if stage==4:wires(ax,[box_corners(b) for b in new],P,'#14836b',bounds)
            if stage==5:
                wires(ax,[cor for _,cor in compiled_corners],P,'#8165a5',bounds)
                # MODEL REFERENCE, not reconstructed observations.
                robot=[np.asarray(b['center_body_m'])+(SIGNS*np.asarray(b['half_extents_m']))@np.asarray(b['rotation_body']).T for b in geometry['boxes']]
                wires(ax,robot,P,'#97a6ad',bounds,lw=.85)
            q=target@P;ax.scatter(*q,s=75,marker='+',c='#d04d38',linewidth=2)
            ni,no=m['counts'][stage];note=(f'N_in {ni:,} → N_out {no:,}  |  warm median {m["median_ms"][stage]:.2f} ms'
                 +f'\nBODY −Y → +Y / same bounds / display {min(len(visible),60000):,} of {len(visible):,} in bounds')
            if stage==4:note+=f' / K={len(new)} (wireframe audit)'
            if stage==5:note+=f' / K_cuRobo={len(compiled_corners)}; compiled, then mapped back to BODY'
            finish(fig,f'panels/rasc6/{NAMES[stage]}_{view}',TITLES[stage],note,stage=stage+1,camera=camera,bounds_body_m=bounds,rendered_count=min(len(visible),60000),in_display_bounds_count=len(visible),point_source_count=len(p))
    # Main figures: intentionally remove front occluders from DISPLAY, never from collision world.
    for name,key,bounds,title in [('raw_full','body',[arr['body'].min(0).tolist(),arr['body'].max(0).tolist()],'完整观测范围：不补齐扫描空洞'),
                                 ('target_observation','clean',focus,'ID1附近真实观测：局部放大'),
                                 ('ownership_before','roi',ownership,'自体过滤前：同帧机器人附近点'),
                                 ('ownership_after','external',ownership,'自体过滤后：只保留外部观测'),
                                 ('ownership_removed','removed',ownership,'被移除的641个机器人归属点')]:
        p=arr[key];mask=inside(p,bounds);visible=p[mask];fig,ax,P,n=frame(bounds,'iso')
        if name.startswith('ownership_'):
            robot=[np.asarray(b['center_body_m'])+(SIGNS*np.asarray(b['half_extents_m']))@np.asarray(b['rotation_body']).T for b in geometry['boxes']]
            wires(ax,robot,P,'#aab5bc',bounds,lw=1.)
        dots(ax,visible,P,n,'#d17337' if key=='removed' else '#335a79',size=8 if key!='body' else 1.2)
        finish(fig,'details/'+name,title,f'{len(visible):,}/{len(p):,} points in display bounds / rendered cap 60,000\n'+('同一651点局部：641移除 / 10外部保留；灰线为MODEL REFERENCE，非观测点' if name.startswith('ownership_') else 'DISPLAY CUT ONLY · 隐藏点仍保留于完整数据和世界；无RGB，不伪造物体彩色'),camera='iso',bounds_body_m=bounds,visible_count=len(visible),source_key=key)
    # Focused stage four: geometry-derived roles, same crop as observation / boxes.
    fig,ax,P,n=frame(focus,'iso');mask=inside(arr['clean'],focus)
    dots(ax,arr['clean'][mask],P,n,np.array(list(COLORS.values()))[role_index[mask]],size=8)
    ax.legend(handles=[Patch(color=c,label=k) for k,c in COLORS.items()],loc='upper left',frameon=False,fontsize=11)
    finish(fig,'details/target_roles','几何分层：单独展示，不与包络叠加',f'{mask.sum()} measured points / same target crop\n颜色是几何分组，不是RGB或神经网络识别',bounds_body_m=focus,camera='iso')
    for name,boxes,color in [('old_boxes',old,'#bf674e'),('new_primitives',new,'#14836b')]:
        fig,ax,P,n=frame(focus,'iso');dots(ax,arr['clean'][mask],P,n,'#8795a0',size=3)
        wires(ax,[box_corners(b,.007) for b in boxes],P,color,focus,lw=.85)
        finish(fig,'geometry_ab/'+name,('OLD 连通簇单AABB' if name=='old_boxes' else 'NEW 多基元')+'：同范围审查',f'K全场景={len(boxes)} / same observed points / uniform 7mm inflation\nDISPLAY CUT ONLY · 完整线框供审查，主汇报推荐薄层剖面对照',bounds_body_m=focus,camera='iso',inflation_m=.007)
    for z in [.90,.94,.98]:
        slab=np.abs(arr['clean'][:,2]-z)<=.006;xy=arr['clean'][slab];pair=[]
        for label,boxes,color in [('old',old,'#bd7359'),('new',new,'#16836d')]:
            fig=plt.figure(figsize=(10,8));ax=fig.add_axes([.10,.15,.84,.62]);ax.set_aspect('equal');ax.set(xlim=(focus[0][0],focus[1][0]),ylim=(focus[0][1],focus[1][1]),xlabel='BODY X [m]',ylabel='BODY Y [m]');ax.grid(alpha=.12)
            for b in boxes:
                c=np.array(b['center_m']);h=np.array(b['dims_m'])/2+.007
                if abs(c[2]-z)<=h[2]:ax.add_patch(Rectangle(c[:2]-h[:2],*(2*h[:2]),facecolor=color,edgecolor=color,alpha=.20,clip_on=True,lw=.9))
            ax.scatter(xy[:,0],xy[:,1],s=12,color='#263c50',linewidths=0,zorder=4)
            name=f'geometry_ab/{label}_section_z{z:.2f}';pair.append(name+'.png')
            finish(fig,name,f'{label.upper()} 同层剖面：Z={z:.2f}m','dots = measured points within ±6mm / same bounds and 7mm padding\n包络差异 ≠ 已证明的自由空间；没有点不代表可通行',camera='top',section_z_m=z,point_slab_half_width_m=.006,bounds_body_m=focus)
        images=[Image.open(out/x).convert('RGB') for x in pair];canvas=Image.new('RGB',(3200,1280),'white')
        for i,im in enumerate(images):im.thumbnail((1600,1280));canvas.paste(im,(i*1600+(1600-im.width)//2,(1280-im.height)//2))
        canvas.save(out/f'geometry_ab/pair_section_z{z:.2f}.png')
    # Six independently reusable panels are primary; overview is just navigation.
    overview=Image.new('RGB',(3600,1600),'white')
    for i,name in enumerate(NAMES):
        im=Image.open(out/f'panels/rasc6/{name}_iso.png');im.thumbnail((1200,800));overview.paste(im,((i%3)*1200,(i//3)*800))
    overview.save(out/'six_stages_overview.png')
    # Current CPU metrics, separate from historical capture and field measurements.
    for kind in ['timing','counts','volume']:
        fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(left=.12,right=.95,bottom=.20,top=.76)
        if kind=='timing':
            x=np.arange(6);ax.bar(x,m['median_ms'],color='#2a7f83');ax.errorbar(x,m['median_ms'],yerr=np.maximum(0,np.array(m['p95_ms'])-m['median_ms']),fmt='none',color='#233c50',capsize=4);ax.set_xticks(x,['TF','ROI/voxel','Ownership','Clean/group','Refinement','Compile']);ax.set_ylabel('CPU milliseconds');title='本轮GRASP六阶段CPU耗时';note='3 warm runs: median + upper P95 / excludes disk I/O and rendering\n阶段4含清理与分组；阶段5为机器人邻近基元细分。不是机器人运动时长。'
        elif kind=='counts':
            vals=[len(arr[k]) for k in ['body','roi','external','clean']];ax.bar(range(4),vals,color=['#335a79','#3978ae','#14836b','#d17337']);ax.set_yscale('log');ax.set_xticks(range(4),['Valid BODY','ROI / voxel','External','Cleaned']);ax.set_ylabel('Points (log scale)')
            for i,v in enumerate(vals):ax.text(i,v*1.1,f'{v:,}',ha='center')
            title='数据量变化：裁剪、采样、自体过滤与清理';note='原始2,304,000 → 有效2,056,200 / 不把几何编译写成再次丢点\n分组和多基元保留所有清理后观测，点覆盖另行逐点验证。'
        else:
            vals=[m['old_inflated_sum_volume_m3'],m['new_inflated_sum_volume_m3']];ax.bar(['OLD','NEW'],vals,color=['#bd7359','#16836d']);ax.set_ylabel('Sum of padded box volumes [m³]')
            for i,v in enumerate(vals):ax.text(i,v+.001,f'{v:.6f}',ha='center')
            title='同源、同7mm膨胀下的几何体积';note=f'OLD K={len(old)} / NEW K={len(new)} / coverage {len(arr["clean"])}/{len(arr["clean"])}\n盒体积之和，不是并集体积；包络缩小不等于已验证运动可行。'
        finish(fig,'metrics/'+kind,title,note)
    # Compact viewer payload contains actual measured points / actual computed cuboids.
    viewer_sets=[arr['body'],arr['roi'],arr['external'],arr['clean'],arr['clean'],arr['clean']]
    payload=dict(stages=[sample(p,45000).round(6).tolist() for p in viewer_sets],stage_names=TITLES,
                 counts=[len(p) for p in viewer_sets],removed=arr['removed'].round(6).tolist(),
                 roles=role_index.tolist(),boxes=[box_corners(b,.007).round(6).tolist() for b in new],
                 compiled=[cor.round(6).tolist() for _,cor in compiled_corners],bounds=full,focus=focus,ownership=ownership,target=target.tolist(),metrics=m)
    (out/'viewer_data.json').write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False)+'\n')
    save(out/'VISUAL_MANIFEST.json',dict(source_kind='FROZEN_REPLAY',station='GRASP',source_camera_sha256=m['source_camera_sha256'],
        source_data_commit='dc70016a8fc95d8d0e6efb52ef935d5cec9d408e',assets=entries,
        compiler_max_center_roundtrip_error_m=max(compiler_errors),
        renderer='Orthographic, depth-sorted opaque measured points; deterministic display sampling only',semantic_display_assignment='Uninflated primitive containment; overlaps prioritize SUPPORT_SURFACE, PROTRUDING_OBSTACLE, STRUCTURE, UNKNOWN_OCCUPIED. Geometry-derived display grouping, not separate measured per-point labels.',
        display_only_crops=True,focus_viewport='Projected clean-point extent plus 18% margin; identical across focused comparisons; raw/background may be clipped for display',view_direction='BODY -Y toward +Y',source_arrays_changed_by_render=False,
        interpretation_limit='No RGB, no imputed surfaces, no physical motion; scene ROI is not exact IK reachability.'))
    print(json.dumps(dict(panels=len(entries),compiler_roundtrip_m=max(compiler_errors),all_clean_points_assigned=bool(assigned.all()))))

if __name__=='__main__': main()
