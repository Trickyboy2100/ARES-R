# V4 素材地图与本机准备清单：优先使用repo和已上传PPT，不向用户索要新图

## 1. 总原则

**本轮不要求用户重新拍照、重新录屏、手动导出PNG、手动整理点云或重新上传实验日志。** ARES-R中已有大量代码、报告、JSON、运行证据和高质量RASC图集；10/21原始点云也已存在于独立公开数据分支。此前上传的PPT包含现场照片、控制器界面、工具、料盘、箱体、轨迹、取放过程等媒体，Codex应自行提取原始媒体。

用户可能需要手动准备的唯一核心事项是：如果本机找不到原始母版和两份核心内容PPT，才把缺失的PPTX放进本地忽略目录。具体见第8节。

## 2. ARES-R仓库：必须先用的素材

基准分支：docs/acceptance-workload-draft-20261113  
本轮任务分支：docs/acceptance-workload-v4-20261116

### 2.1 RASC完整视觉资产

根目录：

~~~text
docs/presentations/assets/20261028_rasc_curobo/
~~~

优先使用：

- grasp_v3/index.html：可交互六阶段点云总览；
- grasp_v3/six_stages_overview.png：六阶段总览；
- grasp_v3/panels/rasc6/01_raw_cloud_iso.png；
- grasp_v3/panels/rasc6/02_roi_iso.png；
- grasp_v3/panels/rasc6/03_robot_owned_filter_iso.png；
- grasp_v3/panels/rasc6/04_support_decomposition_iso.png；
- grasp_v3/panels/rasc6/05_multi_primitive_iso.png；
- grasp_v3/panels/rasc6/06_curobo_world_iso.png；
- grasp_v3/details/ownership_before.png；
- grasp_v3/details/ownership_after.png；
- grasp_v3/details/ownership_removed.png；
- grasp_v3/geometry_ab/old_boxes.png；
- grasp_v3/geometry_ab/new_primitives.png；
- grasp_v3/geometry_ab/pair_section_z0.90.png；
- grasp_v3/geometry_ab/pair_section_z0.94.png；
- grasp_v3/geometry_ab/pair_section_z0.98.png；
- grasp_v3/metrics/counts.svg；
- grasp_v3/metrics/volume.svg；
- grasp_v3/metrics/timing.svg；
- grasp_v3/planning/；
- grasp_v3/runlogs/；
- grasp_v3/MANIFEST.json；
- grasp_v3/VISUAL_MANIFEST.json；
- grasp_v3/README.md。

同目录其他图集：

- panels/geometry_ab/old_boxes_zoom.png；
- panels/geometry_ab/new_primitives_zoom.png；
- panels/geometry_ab/error_occupied_space_slice.png；
- clarity_v2/03_old_cutaway.png；
- clarity_v2/04_new_cutaway.png；
- clarity_v2/section_old_new_pair.png；
- panels/planning/planning_old.png；
- panels/planning/planning_new.png；
- panels/planning/route_overlay.png；
- panels/performance/latency_module_before_after.png；
- panels/performance/cpu_backend_comparison.png；
- panels/performance/contact_query_comparison.png；
- panels/attachments/；
- panels/servo/。

注意：
- GRASP V3是2026-10-21/right_pick冻结数据；10/10 CAMERA、9/21 CLEAR7和S21-CLEAN是不同数据组。
- 旧/新几何图必须同视角、同尺度；剖切图必须注明是显示裁切。
- V3严格几何A/B的OLD/NEW端点均碰撞，未进入GPU；不能说几何精化后“旧规划失败、新规划成功”。
- V3另一个保留contact豁免的真实GPU重放与严格几何A/B不是同一世界，不能拼接。

### 2.2 点云与几何证据

- docs/reports/2026-09-21_P3_PRODUCTION_POINTCLOUD_CUROBO_REPORT.md
- docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md
- docs/reports/2026-09-21_CURRENT_BASE_AB_TCP_EXPERIMENT.md
- worklog/evidence/2026-09-21-p3-production-demo/avoid_final/cleanup/cleanup_benchmark.json
- worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png
- worklog/evidence/2026-09-21-p3-1-residual-support/clear_ab/comparison/
- worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/clear_vs_avoid_three_views.png
- worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/comparison/

### 2.3 cuRobo规划与控制证据

- docs/reports/2026-09-22_P3_2_CUROBO_ONLY_AB_PLANNING_REPORT.md
- docs/reports/2026-09-22_P3_3_EXECUTION_HARDENING_REPORT.md
- docs/reports/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION_REPORT.md
- docs/reports/2026-09-23_P3_6_SCENE_AWARE_MOTION_REPORT.md
- docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md
- docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md
- docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md
- worklog/evidence/2026-09-22-p3-3-execution-hardening/sweep_v2/sweep_summary.json
- worklog/evidence/2026-09-22-p3-3-execution-hardening/visualization_final/p33_clearance_profile_sweep.png
- worklog/evidence/2026-09-23-p3-4/summary.json
- worklog/evidence/scene-aware-motion/
- docs/reports/2026-09-24_P3_8A_TRAY_TO_GROOVE_SYSTEM_AUDIT_REPORT.md

### 2.4 长程抓放、故障和恢复证据

- docs/reports/2026-10-17_ROUNDTRIP_DEMO_FAILURE_AND_GATE_AUDIT.md
- docs/reports/2026-10-16_GRASP_PLACE_ROUNDTRIP_PREPARATION.md
- docs/reports/2026-10-19_SINGLE_LIFT230_CHECKPOINT.md
- docs/reports/2026-10-19_DEMO_LIFT230_FIXTURE_ESCAPE_PREFLIGHT.md
- docs/golden/2026-10-19/README.md
- docs/golden/2026-10-19/evidence/v17-place-recovery-completed/REPORT.json
- 20261028大PPT slide42中的真实操作关键帧
- 10/23周报slide08中的放置端局部画面

注意：10/19 Golden是GOLDEN_TASK_COMPLETED_WITH_RECOVERY；故障历史保留，修订持物几何后从检查点接续完成。不是一键无人干预全链成功。10/19旧持物包络220×217×113mm；新主体160×100mm、原厚度沿用、夹持后段20mm；不得补写缺失的新模型完整三轴尺寸。

## 3. 原始点云数据：已经在repo独立分支，不需要用户重新上传

数据分支：

~~~text
codex/data-grasp-20261021-public
~~~

目录：

~~~text
worklog/evidence/2026-10-21-grasp-source-data/
~~~

其中两份已获公开授权的数据归档：

1. 20261021-study-clouds.tar.gz  
   大小41,684,942 bytes；SHA256：
   206e2fdef8886750ca7545ee7e03? 
~~~

请注意：上面SHA必须从仓库DATA_INDEX.json和SHA256SUMS复制，不得使用此处被截断的占位。正确SHA为：
206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60

2. 20261021-center-grasp-planner-study.tar.gz  
   大小18,069,187 bytes；SHA256：
   f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8

同时有DATA_INDEX.json、README.md、PUBLICATION.md和SHA256SUMS。10月28日已明确授权公开这两份原始GRASP数据包及必要现场信息。

Codex在本地repo中可用以下只读方式获取，不需要合并数据分支：

~~~bash
mkdir -p .local/acceptance_sources/grasp_oct21
git fetch origin codex/data-grasp-20261021-public
git show origin/codex/data-grasp-20261021-public:worklog/evidence/2026-10-21-grasp-source-data/20261021-study-clouds.tar.gz > .local/acceptance_sources/grasp_oct21/20261021-study-clouds.tar.gz
git show origin/codex/data-grasp-20261021-public:worklog/evidence/2026-10-21-grasp-source-data/20261021-center-grasp-planner-study.tar.gz > .local/acceptance_sources/grasp_oct21/20261021-center-grasp-planner-study.tar.gz
git show origin/codex/data-grasp-20261021-public:worklog/evidence/2026-10-21-grasp-source-data/SHA256SUMS > .local/acceptance_sources/grasp_oct21/SHA256SUMS
cd .local/acceptance_sources/grasp_oct21
shasum -a 256 -c SHA256SUMS
mkdir -p unpacked
tar -xzf 20261021-study-clouds.tar.gz -C unpacked
tar -xzf 20261021-center-grasp-planner-study.tar.gz -C unpacked
~~~

预期关键输入：

- CAMERA：unpacked/logs/body_cloud/captures/20261021_144732_60b67baa/pointcloud_camera_mm.npy
- BODY：unpacked/logs/body_cloud/artifacts/20261021_144734_5a364d75/body_cloud.npz
- BODY manifest：同目录manifest.json
- study：unpacked/worklog/evidence/20261021-center-grasp-planner-study/
- observation：study/pick-epoch/manipulation_observation.json
- geometry：study/pick-epoch/live_scene/whole_robot_geometry.json
- 原始scene：study/pick-epoch/live_scene/scene/

数据索引已核验：
- CAMERA SHA：62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6
- BODY SHA：56fa636b107a8bd568ea32e1b946adce0c1b287746f5c5cddb8a4a8738b43f99
- observation：OBS_P3_LIVE_1792565261632216610
- scene：SCENE_d9f27c83fc0949f1a709bd0c3e843b4a
- 原始CAMERA点数2,304,000；有效点2,056,200；BODY单位m，CAMERA单位mm。

不要覆盖原始归档。所有派生文件放在output/experiment/或忽略目录。

## 4. 用户此前上传PPT：精确候选文件名、页数和用途

这些原始PPTX目前没有以二进制形式放进本交接目录。仓库中已有可读文本引用、媒体页级索引和独立RASC图集，但不能把文本摘录冒充原PPTX。

| ID | 本机应定位的精确文件名 | 已知页数/比例 | 用途 |
|---|---|---|---|
| TEMPLATE | 生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx | 8页，16:9 | 唯一母版，必须继承 |
| LARGE | 20261028-水分细度目标识别与场景自适应规划控制.pptx | 60页，4:3 | 现场图片、几何、轨迹、真实操作关键帧；后部45–60页重点抽媒体 |
| METHOD | 20261028-水分细度目标识别与场景自适应规划控制-2.pptx | 12页，4:3 | 方法框架、算法讲述备注；正文只取必要图形/公式，不照搬算法科普结构 |
| EXAMPLE_2025 | 参考用 智能机器人实验员技术开发及应用-阶段汇报-朱翔2025.12.10 copy.pptx | 28页，4:3 | 只学习研发过程如何呈现，不复制结果 |
| EXAMPLE_2026 | 25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）.pptx | 16页，4:3 | 只学习“候选—对照—选择—训练/验证”证据组织，不复制视觉结果 |
| WEEK_0924 | 金隅项目-周进度-20260924(1).pptx | 16页，16:9 | TCP、几何、A/B轨迹、视频 |
| WEEK_1016 | 金隅项目-周进度-20261016.pptx | 12页左右，16:9 | Golden真实控制器/抓取关键帧 |
| WEEK_1030 | 金隅项目-周进度-20261030.pptx | 16页左右，16:9 | 现场阶段与执行素材 |
| OLD_DRAFT | 点云场景重建与机械臂规划_研发工作量汇报_原模板14加2页.pptx | 16页，16:9 | 只取内容、数字和备注；不复制旧页面视觉/组织 |

本机搜索命令：

~~~bash
mdfind -name "生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制-2"
mdfind -name "参考用 智能机器人实验员实验员技术开发及应用-阶段汇报-朱翔2025.12.10 copy"
mdfind -name "25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）"
mdfind -name "金隅项目-周进度-20260924"
mdfind -name "金隅项目-周进度-20261016"
mdfind -name "金隅项目-周进度-20261030"
mdfind -name "点云场景重建与机械臂规划_研发工作量汇报_原模板14加2页"
~~~

如Spotlight没有结果，仅在用户授权的常规目录查找：~/Downloads、~/Documents、~/Desktop、~/Library/Mobile Documents/com~apple~CloudDocs/以及当前ARES-R项目目录。不要全盘递归搜索邮件、隐藏目录或无关个人数据。

本机找到的私有绝对路径只写入忽略文件，例如 .local/acceptance_source_paths.json；不得提交public GitHub。

## 5. 大PPT的已核验原嵌媒体索引（重点）

20261028大PPT共60页。以下是已核验的slide/shape对象和原始媒体尺寸；Codex应按实际OOXML关系提取原媒体，而不是截图整页。

- slide04 shape12.png：1800×1050，方案演进/空间理解；shape14、shape16也有相关原图。
- slide11 shape05/08/11/14/17/20：六阶段点云媒体，2400×1600。
- slide12 shape05/07：ROI和点云输入。
- slide13 shape05/07/09：自体过滤。
- slide14 shape05：支撑/结构处理输出，2400×1600。
- slide17 shape11/12：旧/新几何对照，660×490，优先寻找repo高清图。
- slide18 shape07/09：旧/新AABB和覆盖量化图，2400×1400。
- slide19 shape05/07/09：同源规划场景截图；OLD/NEW本次都规划通过。
- slide27 shape05/07：求解性能/迭代配置图，使用前核对数据组。
- slide28/29 shape05：旧场景A/B与线路对照。
- slide30 shape05/07/09：三段实际绕障和控制预览。
- slide32 shape05/07/09：执行跟踪轨迹。
- slide37 shape05/07/09：持物几何错误/修正/恢复。
- slide40 shape09/11：性能模块比较。
- slide41 shape05/07/09：耗时图与回放。
- slide42 shape05/08/11/14/17/20/23/26：真实取放操作照片，优先大图＋3帧局部。
- slide45–60：后部独立素材/截屏，必须生成contact sheet并逐张选择。特别注意：
  - slide50 shape05.png：3240×1440；
  - slide51 shape04.png：3960×1260；
  - slide54 shape09.png：1600×1000；
  - slide55 shape05.png：1600×1000，shape07.jpg：3298×2473；
  - slide59 shapes05/07/09/11/13/15/17：多张高分辨率物理/几何证据。

以上页码/shape索引来自已完成的媒体审计。若本机原PPT版本不同，Codex必须重新解析关系并记录差异，不得硬套shape序号。

## 6. 周报和示例PPT的具体使用

### 9/24周报
- slide04/05：TCP界面、工具和现场校核；
- slide06：单盒到细分；
- slide07/08/09：同A/B轨迹；
- slide13：视频媒体。
只作为相应历史工况的图源，不与其他数据组的数值拼接。

### 9/11周报
- cuRobo右臂两段式规划实机闭环；
- 规划→轨迹门禁→ServoJ；
- 约194.3mm TCP反馈行程、513点、80ms周期、跟踪记录。
如用于“早期链路接通”，必须标注9/11历史记录，不与P3.4的0.20rad/s回程数据合并。

### 10/23周报
- slide08：放置端俯视投影与持物模型修正；
- 真实料盘、夹爪、秤台照片。

### 2025/2026示例PPT
只学习：
- 参数/数据的候选比较方式；
- 训练或实现过程如何一页一证；
- 模块选择和验证结果如何可视化。
绝不借用视觉模型的准确率、样本量或训练数据作为本项目结果。

## 7. 提取与媒体索引要求

对每份可读PPTX：
1. 解析presentation.xml的slide order；
2. 解析slide relationship，提取ppt/media中的原始图片/视频；
3. 原图保留像素尺寸、原始文件SHA和shape/slide来源；
4. 对每页生成contact sheet，特别检查大PPT45–60页；
5. 优先原始media，不把整页截图放大；
6. 对视频记录文件名、duration、FPS、原始媒体SHA；视频播放时长不是机器人运行耗时；
7. 对每个被采用媒体登记source_ppt、slide、shape、media_rel、pixel size、crop、dataset_id、evidence_level。

media_index.csv至少包含：
source_id, source_basename, slide_ordinal, shape_id, relationship_id, media_path, media_sha256, pixel_width, pixel_height, dataset_id, validation_level, used_in_slide, crop_note。

## 8. 用户需要手动准备什么？

**优先方案：不需要准备任何新图片、点云、截图或实验日志。**

Codex先自行：
- 从ARES-R当前仓库读取全部代码、报告、图集和证据；
- 从codex/data-grasp-20261021-public取回并核验两份点云归档；
- 在用户本机已授权目录定位此前上传的PPTX；
- 从原PPT提取照片、图表、视频和控制器截图。

**仅当本机搜索确认原件不存在时，才需要用户手动复制缺失文件。** 最小必需集合是：

1. TEMPLATE：原始20261030V0.95机械臂母版；
2. LARGE：20261028 60页大PPT；
3. METHOD：20261028 12页方法版。

可选补充：
- 9/24、10/16、10/23、10/30周报；
- 2025研发汇报范例；
- 2026视觉考核范例；
- 旧16页半成品PPTX/PDF。

建议只把实际缺失的文件复制到：

~~~text
ARES-R/.local/acceptance_sources/
~~~

该目录必须在.gitignore中忽略。不要把私人原件提交到public repo。

用户不需要手工导出图片、不需要重新截图、不需要上传点云、不需要整理页码、不需要手动做媒体索引。Codex必须先尝试repo和本机搜索，不能一开始就向用户索要素材。

## 9. 字体和母版复核

原母版必须保留；字体按用户明确要求：
- 中文主字体黑体；
- 英文/数字主字体Arial；
- 中文辅助宋体；
- 英文辅助Times New Roman；
- 公式独立处理。

不得将4:3大PPT整页图片直接拉伸进16:9模板。提取单个原图/原生形状，按16:9母版内容区重新排布。
