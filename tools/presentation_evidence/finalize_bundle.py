"""Caption untouched UI captures, audit manifest, assemble gallery/contact sheets."""
import argparse,json,hashlib,re,html,math,zipfile,csv
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from replay_rasc import load,save,sha
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args();o=a.output;manifest=load(o/'ASSET_MANIFEST.json');assets=manifest['assets'];m=load(o/'runlogs/rasc_stage_metrics.json');font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',32)
# Never paint buttons/status. Add a separate caption below the original UI pixels.
for image in sorted((o/'panels/runtime').glob('webui_*.png')):
 original=a.private/'ui_originals'/image.name;original.parent.mkdir(exist_ok=True)
 if not original.exists():original.write_bytes(image.read_bytes())
 im=Image.open(original).convert('RGB');canvas=Image.new('RGB',(im.width,im.height+110),'white');canvas.paste(im,(0,0));draw=ImageDraw.Draw(canvas);draw.text((38,im.height+14),'OFFLINE UI FIXTURE / source HTML + local API / NO DEVICE CONNECTION',font=font,fill='#263d52');draw.text((38,im.height+57),'Scene: frozen Oct10 cloud; task failure: ReplayCapabilityProvider; no physical execution.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',25),fill='#435266');canvas.save(image)
 entry=dict(assets[0]);entry.update(asset_id=image.stem,path=str(image.relative_to(o)),title=image.stem,source_kind='OFFLINE_SYNTHETIC',experiment_id='ACTUAL_UI_SOURCE_LOCAL_FIXTURE',source_artifact_sha256=sha(ROOT/'src/ares_r/webui/index.html' if image.stem not in ['webui_task_state','webui_object_envelope_inspector'] else ROOT/'src/ares_r/webui/workbench.html'),scene_snapshot_id=None,robot_state_hash=None,tool_calibration_revision=None,generation_script='tools/presentation_evidence/capture_ui.cjs + finalize_bundle.py',generation_params={'viewport':[1920,1080],'deviceScaleFactor':1.5,'all_network_requests_intercepted':True,'source_unmodified':True,'caption_outside_original_pixels':True},input_count=None,output_count=None,runtime_ms=None,interpretation_limit='Task state from actual ReplayCapabilityProvider; scene from frozen cloud. Does not prove hardware/GPU execution. Workbench example is a historical dimension schematic.',sha256=sha(image));assets=[x for x in assets if x['asset_id']!=entry['asset_id']]+[entry]
qa=load(a.private/'ui_browser_qa.json');save(o/'runlogs/ui_browser_qa.json',qa)
# Source custody records exclude filenames/paths that identify an operator or controller.
media=[]
for root in [Path.home()/'Downloads/LANDrop',Path.home()/'Documents',Path.home()/'Desktop']:
 if not root.exists():continue
 for deck in root.rglob('*.pptx'):
  try:
   with zipfile.ZipFile(deck) as z:items=[dict(entry=i.filename,bytes=i.file_size,sha256=hashlib.sha256(z.read(i)).hexdigest()) for i in z.infolist() if i.filename.startswith('ppt/media/')]
   media.append(dict(deck_basename=deck.name,deck_sha256=sha(deck),media=items,videos=[x['entry'] for x in items if x['entry'].lower().endswith(('.mp4','.mov','.wmv','.avi','.webm'))],public_media_release_approved=False))
  except (OSError,zipfile.BadZipFile):continue
save(o/'runlogs/existing_media_index.json',media)
(o/'EXISTING_MEDIA_INDEX.md').write_text('# 已有媒体索引\n\n只读检查Downloads/LANDrop、Documents、Desktop下可读PPT，未更改原文件。\n\n'+ '\n'.join(f"- {x['deck_basename']}：SHA `{x['deck_sha256']}`，{len(x['media'])}个media，{len(x['videos'])}个嵌入视频。" for x in media)+'\n\n未找到包含点云与碰撞框拖拽视频的周进度PPT。原媒体没有公开发布许可，未提交或挪用；逐media hash在runlogs/existing_media_index.json。\n')
# Strict required fields and output hashes.
required=['asset_id','path','source_kind','experiment_id','source_artifact_sha256','scene_snapshot_id','robot_state_hash','tool_calibration_revision','repo_commit','generation_script','generation_params','input_count','output_count','runtime_ms','safety_constraints_digest','interpretation_limit','public_release_approved']
qa_rows=[]
for entry in assets:
 assert all(k in entry for k in required),entry['path'];path=o/entry['path'];assert path.exists();entry['sha256']=sha(path)
 if path.suffix=='.png':
  im=Image.open(path);assert max(im.size)>=1920,(path,im.size);entry['pixel_size']=list(im.size);qa_rows.append(dict(path=entry['path'],size=list(im.size),blank_variance=sum(im.convert('RGB').resize((64,36)).getextrema()[k][1]-im.convert('RGB').resize((64,36)).getextrema()[k][0] for k in range(3))))
# No empty placeholder figures. Missing requested panels have explicit slots.
blocked=[('candidate_paths','GPU seed intermediate paths are not exported; no fabricated candidate lines'),('normal_full_task_servo_trace','Complete paired normal task sender logs unavailable; existing micro traces aborted'),('place_clearance_case','Original Oct19 placement geometry/TF/request package absent'),('three_physical_ownership_scenes','No three matched physical geometries available; source contract schematic delivered'),('dragging_demo_video','LOCAL_PPT_WITH_DRAGGING_DEMO_NOT_FOUND'),('physical_full_cycle_filmstrip','Authorized source video absent'),('real_clear_avoid_block_series','Three independently authenticated condition-labelled real scans absent')]
manifest.update(assets=assets,blocked_assets=[dict(asset_id=k,status='BLOCKED_MISSING_DATA',reason=v) for k,v in blocked]);save(o/'ASSET_MANIFEST.json',manifest)
pngs=[x for x in assets if x['path'].endswith('.png')];thumb_w,thumb_h=640,405;cols=4;sheet=Image.new('RGB',(cols*thumb_w,math.ceil(len(pngs)/cols)*thumb_h),'#e9eef1');draw=ImageDraw.Draw(sheet);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
for i,entry in enumerate(pngs):
 im=Image.open(o/entry['path']).convert('RGB');im.thumbnail((640,360));x=(i%cols)*thumb_w;y=(i//cols)*thumb_h;sheet.paste(im,(x+(640-im.width)//2,y));draw.text((x+8,y+364),entry['path'].split('/')[-1][:64],font=small,fill='#263d52');draw.text((x+8,y+384),entry['source_kind'],font=small,fill='#435266')
sheet.save(o/'contact_sheet.png')
# Six-panel overview preserves independently usable originals.
rasc=[next(x for x in pngs if x['path'].startswith('panels/rasc6/'+str(i).zfill(2)+'_') and x['path'].endswith('_iso.png')) for i in range(1,7)];composite=Image.new('RGB',(3840,2160),'white')
for i,entry in enumerate(rasc):
 im=Image.open(o/entry['path']);im.thumbnail((1280,1080));composite.paste(im,((i%3)*1280,(i//3)*1080+(1080-im.height)//2))
(o/'composites').mkdir(exist_ok=True);composite.save(o/'composites/RASC_six_stages_16x9.png')
# Public HTML index is a file-based gallery, not a deployed service.
cards=[]
for entry in pngs:cards.append(f'<article><a href="{html.escape(entry["path"])}"><img loading="lazy" src="{html.escape(entry["path"])}"></a><h3>{html.escape(entry.get("title",entry["asset_id"]))}</h3><small>{entry["source_kind"]}</small><p>{html.escape(entry["interpretation_limit"])}</p><a href="{entry["path"]}">PNG</a>'+ (f' · <a href="{entry["path"][:-4]}.svg">SVG</a>' if (o/(entry['path'][:-4]+'.svg')).exists() else '')+'</article>')
(o/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>RASC研发证据</title><style>body{font:16px system-ui;color:#263d52;max-width:1500px;margin:32px auto;background:#f6f8f9}h1{font-size:32px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:white;padding:16px;border:1px solid #d9e2e8}img{width:100%}small{color:#387e70}p{line-height:1.5}a{color:#28649a}</style><h1>RASC · 真实来源、独立子图与量化证据</h1><p>离线研发；无设备连接；真实点云重放与历史实测分开。OLD/NEW均通过本例规划，不能宣称旧失败/新成功。真实微运动日志均abort。</p><p><a href="README.md">推荐图与说明</a> · <a href="STATUS.md">状态</a> · <a href="reports/REVIEW_AND_LIMITATIONS.md">审查与限制</a> · <a href="ASSET_MANIFEST.json">溯源清单</a></p><main>'+''.join(cards)+'</main></html>')
save(o/'runlogs/visual_qa.json',dict(checked_pngs=len(qa_rows),minimum_long_edge=1920,all_nonblank=all(x['blank_variance']>0 for x in qa_rows),rows=qa_rows,review_rounds=['v1: identify font, mixed micro deletion, cross-arrow, read-before-send problems','v2: corrected source semantics, font registration, matched detail views, snake diagrams','final: source/hash/privacy checks, actual compiler outputs, named arm extraction, honest negative results'],one_third_width_review='640px contact sheet: titles and visual relations readable; dense UI/telemetry legends require full-page or focused crop. Not every panel is suitable at 1/3 width.'))
# The README starts with actual deliverables and recommendations.
(o/'README.md').write_text(f'''# RASC / cuRobo 技术汇报研发证据

先打开 **[离线素材总览 index.html](index.html)**；独立子图可直接下载，**没有制作最终PPT**。

本包含 **{len(pngs)}张独立PNG**、**{sum(x['path'].endswith('.svg') for x in assets)}张SVG**、六阶段16:9合集、CSV/JSON指标、源码与复现工具。所有原始点云/未经授权媒体留在本地私有目录。逐图来源见ASSET_MANIFEST.json，状态与缺口见STATUS.md。

| 素材组 | 独立路径 | 最适合讲什么 |
|---|---|---|
| 真实点云六阶段 | panels/rasc6/01..06_*_iso/top/front.png | 同一真实源帧、实际算法/计数/计时；18张 |
| 几何A/B | panels/geometry_ab/old_boxes/new_primitives + *_zoom + error_occupied_space_slice | 32簇框与235基元全点覆盖，统一7mm；sum体积降低约40.9%，不称union/已证空闲 |
| 真实GPU规划 | panels/planning/planning_old/new、route_overlay、gap_vs_path | 同一请求预算；两者都成功，独立world校验通过；无虚构候选 |
| cuRobo/ARES-R原理 | panels/runtime/curobo_native_principle、aresr_constraint_integration | 上游GPU能力与项目约束/验证分工 |
| 真实ServoJ | panels/servo/case1/case2_* | 六轴目标/实测、previous-command误差、差分动态；**两例均abort** |
| 性能分层 | panels/performance/* | 本轮CPU/查询等价实验 + 明确分开的历史三项、等待瀑布、GPU层次 |
| 框架/状态/界面 | panels/runtime/* | 四套独立代码图、ownership、真实HTML/fixture界面；不冒充设备任务 |
| 持物/恢复 | panels/attachments/* | 历史尺寸修正与故障后接续时间；无原几何净空结论 |

## 推荐优先使用的10张

1. [六阶段合集](composites/RASC_six_stages_16x9.png)：同源算法链；合集只作导航，正式汇报按需拆图。
2. [局部OLD](panels/geometry_ab/old_boxes_zoom.png) + [局部NEW](panels/geometry_ab/new_primitives_zoom.png)：同视角/全点覆盖；不能声称未观测空腔安全。
3. [占据剖面](panels/geometry_ab/error_occupied_space_slice.png)：OLD-only表示面积；最大差异Z层选择已公开。
4. [GPU路径并列](panels/planning/route_overlay.png)：真实保存的cuRobo结果；两者均成功，没有“旧失败新成功”。
5. [本轮CPU等价对照](panels/performance/cpu_backend_comparison.png)：301采样、同判决/净空，不能称GPU加速。
6. [本轮索引查询](panels/performance/contact_query_comparison.png)：相同235个bounds，输出数组一致；不是完整artifact scope。
7. [约束集成](panels/runtime/aresr_constraint_integration.png)：ARES-R工程贡献；结构图非实测。
8. [历史模块优化](panels/performance/latency_module_before_after.png)：历史17.023→1.125等，收益不叠加。
9. [关键路径](panels/performance/latency_critical_path_waterfall.png)：400.25s事件窗口，等待不能全归视觉。
10. [状态契约](panels/runtime/scene_state_contract.png)：scene/tool/payload/q如何使旧计划失效；现场ACK恢复仍有边界。

## 本轮验证

真实Oct10 CAMERA SHA `{m['source_camera_sha256']}`；BODY经固定TF重算逐元素一致；CPU1冷5热计时；GPU0 RTX3080 / pinned cuRobo；OLD/NEW均SUCCESS且独立world PASS。两次冷请求不是延迟分布。25项既有相关回归与5项新增关节映射回归通过。正式worker修复独立提交8fbd669。

几何235个基元保留3747/3747点；与历史同帧3736/31簇存在库/边界差异，未冒充9/21 7→167。capture q与transit规划q0不同，静态冻结世界A/B不能代替fresh实机状态绑定。原site runtime YAML不在本地，离线派生配置的区别已记录。independent self collision仍未实现；GPU内self collision启用。

复现：见[工具README](../../../../tools/presentation_evidence/README.md)，一键入口tools/presentation_evidence/run_all.sh。原始输入必须由有权限的数据盘提供；不会自动访问现场。先看[审查记录](reports/REVIEW_AND_LIMITATIONS.md)，最后看[最小现场/数据缺口](reports/ONSITE_ONLY_BACKLOG.md)。
''')
# Privacy gate applies to public assets, not private runtime or controlled input.
leaks=[]
for path in o.rglob('*'):
 if path.is_file() and path.suffix in ['.md','.json','.csv','.html','.svg','.tex']:
  text=path.read_text(errors='replace')
  if re.search(r'/home/[^/\s]+/|/Users/[^/\s]+/|192\.168\.\d+\.\d+',text):leaks.append(str(path.relative_to(o)))
assert not leaks,leaks
save(o/'runlogs/delivery_qa.json',dict(privacy_scan_pass=True,raw_arrays_submitted=False,physical_commands_sent=False,hardware_isolation='bwrap unshare-net; private /dev with GPU0 only when requested; no serial devices',ui_external_network_allowed=False,asset_count=len(assets),png_count=len(pngs),svg_count=sum(x['path'].endswith('.svg') for x in assets),golden_sha256={p:sha(ROOT/p) for p in ['scripts/run_first_pick_demo.py','demos/right_arm_epic_pick_lift_v1/demo.json']},not_verified='Site deployment, whole-body base sweep, new object tasks, original Oct21 input reproduction'))
# Hash all delivered files except this checksum file itself.
files=sorted(x for x in o.rglob('*') if x.is_file() and x.name!='SHA256SUMS');(o/'SHA256SUMS').write_text(''.join(f'{sha(x)}  {x.relative_to(o)}\n' for x in files));print(json.dumps(dict(PNG=len(pngs),SVG=sum(x['path'].endswith('.svg') for x in assets),privacy='PASS')))
