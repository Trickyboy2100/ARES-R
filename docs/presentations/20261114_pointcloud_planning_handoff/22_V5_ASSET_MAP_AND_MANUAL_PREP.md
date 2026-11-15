# V5 素材地图与最小手动准备清单

## 1. 结论：不需要用户重新制作或上传实验素材

本轮优先使用：
1. ARES-R仓库中已经提交的代码、报告、JSON、runlog、点云图集和实机执行证据；
2. ARES仓库中JAKA URDF、夹爪模型、cuRobo YAML和仿真资产；
3. 用户此前上传的20261030母版、20261028大PPT/方法PPT、周报和参考PPT；
4. 10/21原始点云公开归档分支。

**不要求用户重新拍照、录屏、导出PNG、整理点云、手工做媒体索引或重新跑实机。** Codex必须先自行审计repo和本机已授权目录。

唯一可能需要用户手动做的事情：如果Codex在本机找不到原始母版、大PPT或方法PPT，才请用户把缺失的PPTX复制到本机repo的忽略目录。具体见第8节。

## 2. ARES-R中已经存在的点云与规划视觉素材

### 2.1 RASC/GRASP V3六阶段图集

根目录：

~~~text
docs/presentations/assets/20261028_rasc_curobo/
~~~

最重要入口：

- grasp_v3/index.html：交互式点云总览；
- grasp_v3/six_stages_overview.png；
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
- grasp_v3/README.md；
- grasp_v3/REVIEW.md。

其他可用素材：

- panels/rasc6/；
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

必须阅读README、MANIFEST、VISUAL_MANIFEST和REVIEW，不能只凭文件名使用图。

### 2.2 点云、几何分解和碰撞世界报告

- docs/reports/2026-09-21_P3_PRODUCTION_POINTCLOUD_CUROBO_REPORT.md
- docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md
- docs/reports/2026-09-21_CURRENT_BASE_AB_TCP_EXPERIMENT.md
- worklog/evidence/2026-09-21-p3-production-demo/avoid_final/cleanup/cleanup_benchmark.json
- worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png
- worklog/evidence/2026-09-21-p3-1-residual-support/clear_ab/comparison/
- worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/clear_vs_avoid_three_views.png
- worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/comparison/

### 2.3 cuRobo规划、控制和真实执行报告

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
- worklog/evidence/2026-09-28-p3-9/low_code_acceptance.json
- worklog/evidence/2026-09-28-p3-9/replay_acceptance.json

### 2.4 10/19 Golden真实任务与PLACE恢复

权威材料：

- docs/golden/2026-10-19/README.md；
- docs/golden/2026-10-19/evidence/v17-place-recovery-completed/COMPLETED.md；
- docs/golden/2026-10-19/evidence/v17-place-recovery-completed/REPORT.json；
- docs/reports/2026-10-19_CENTER_GRASP_PREPARATION_CHECKPOINT.md；
- docs/reports/2026-10-19_NEXT_DEMO_PLACE_CONTACT_AND_PREPARATION.md；
- 大PPTslide42真实操作关键帧；
- 10/23周报slide08持物模型修正图；
- repo docs/presentations/assets/20261028_rasc_curobo/panels/attachments/。

关键事实：
- 10/19 Golden已完成取料、230mm连续抬升、1.53m底盘转运；
- 原始全链在PLACE故障；
- 持物模型修订后，从PLACE检查点恢复完成50mm下降、释放和底盘返回；
- 125.34s是恢复事件跨度，不是整个任务时长；
- recovery不是不中断的无人干预全链；
- 没有额外视觉证据证明精确落座，也没有精密SLAM站位认证；
- 持物模型修订是Demo限定override，不是通用自动持物估计。

**10/17失败数字：** 当前公开repo的审计报告主要包含CHAT_TOOL_EVIDENCE和INFERENCE，不等同原始run/event日志。必须在本机授权工作目录搜索原始事件日志；找不到就不把172.0s、257.3s等数字放入PPT正文。不要把V3摘要表当作原始运行记录。

### 2.5 ARES主仓库：机器人模型和仿真背景

主仓库：Trickyboy2100/ARES，默认分支main。它是机器人模型/仿真和早期开发资产来源；本次真实规划与控制结果以ARES-R报告和日志为准。

优先检查：
- README.md；
- jaka_ros2/src/jaka_description/urdf/jaka_minicobo.urdf；
- jaka_ros2/src/jaka_description/urdf/jaka_minicobo_gripper.urdf；
- jinyu_ros_pkg/nodes/simulation/jaka_minicobo_curobo.yml；
- isaac_sim/simforge/；
- isaac_sim/cad_assets/；
- scenes/、robot/和docs/中的JAKA/夹爪/工作台模型说明。

用途：
- 说明JAKA MiniCobo/Mini2机器人模型、夹爪模型、关节和工具碰撞模型的工程来源；
- 必要时提供仿真场景、CAD零件和模型截图；
- 用于解释早期仿真与模型适配背景。

禁止：
- 不把SimForge/PhysX仿真循环次数当成真实机械臂实机次数；
- 不把仿真抓取/FixedJoint结果当成P3.6/P3.7真实执行；
- 不把ARES仓库里的通用cuRobo配置当作现场最终commissioning配置；
- 不为了制作PPT修改ARES生产代码、仿真场景或里程碑文件。

## 3. 原始点云：已经在独立公开数据分支

分支：

~~~text
codex/data-grasp-20261021-public
~~~

路径：

~~~text
worklog/evidence/2026-10-21-grasp-source-data/
~~~

两份已公开授权归档：

1. 20261021-study-clouds.tar.gz  
   大小41,684,942 bytes  
   SHA256：206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60

2. 20261021-center-grasp-planner-study.tar.gz  
   大小18,069,187 bytes  
   SHA256：f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8

同目录还有DATA_INDEX.json、README.md、PUBLICATION.md和SHA256SUMS。

只读获取命令，不合并数据分支：

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

关键文件：
- CAMERA：unpacked/logs/body_cloud/captures/20261021_144732_60b67baa/pointcloud_camera_mm.npy
- BODY：unpacked/logs/body_cloud/artifacts/20261021_144734_5a364d75/body_cloud.npz
- BODY manifest：同目录manifest.json
- study：unpacked/worklog/evidence/20261021-center-grasp-planner-study/
- observation：study/pick-epoch/manipulation_observation.json
- geometry：study/pick-epoch/live_scene/whole_robot_geometry.json
- scene：study/pick-epoch/live_scene/scene/

已核验：
- CAMERA SHA：62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6
- BODY SHA：56fa636b107a8bd568ea32e1b946adce0c1b287746f5c5cddb8a4a8738b43f99
- observation：OBS_P3_LIVE_1792565261632216610
- scene：SCENE_d9f27c83fc0949f1a709bd0c3e843b4a
- CAMERA单位mm，BODY单位m。

不要覆盖原始归档。所有派生文件放本机output目录或忽略目录。

## 4. 用户此前上传PPT：已确认的附件与本机定位

以下原始文件已经在本次/此前ChatGPT对话中上传并可检索。文件在ChatGPT对话附件中存在，不代表本机Codex自动拥有其字节；Codex仍应在本机授权目录查找同名副本。

| ID | 已确认上传的文件名 | 文件大小 | 用途 |
|---|---|---:|---|
| TEMPLATE | 生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx | 93,871,535 bytes | 唯一母版，必须继承 |
| LARGE | 20261028-水分细度目标识别与场景自适应规划控制.pptx | 263,164,216 bytes | 60页大稿，主要原始图片/视频库，特别45–60页 |
| METHOD | 20261028-水分细度目标识别与场景自适应规划控制-2.pptx | 55,168,980 bytes | 方法框图/算法说明；页数必须以OOXML实际解析为准，当前文本提取出现07/09页码标记，与旧索引的12页记录不一致，Codex需核对 |
| EXAMPLE_2025 | 参考用 智能机器人实验员技术开发及应用-阶段汇报-朱翔2025.12.10 copy.pptx | 49,875,284 bytes | 只学习研发过程表达，不用其数据 |
| EXAMPLE_2026 | 25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）.pptx | 13,590,891 bytes | 只学习对照实验呈现，不用视觉结果 |
| WEEK_0911 | 金隅项目-周进度-20260911(1).pptx | 120,837,558 bytes | 早期cuRobo到ServoJ实机接口证据 |
| WEEK_0924 | 金隅项目-周进度-20260924(1).pptx | 13,829,903 bytes | TCP/工具/几何、A/B预览、P3.7实机图 |
| WEEK_1016 | 金隅项目-周进度-20261016 copy.pdf | 2,115,899 bytes | 运行时、抓放过程与工程进展；如本机另有PPTX版本，优先核验原PPTX |
| OLD_DRAFT | 点云场景重建与机械臂规划_研发工作量汇报_原模板14加2页.pptx | 26,880,699 bytes | 只复核数字/备注，不沿用页序和视觉 |

当前对话中没有检索到独立的10/23或10/30周报PPTX附件；不把它们列为必须手动准备。10/23 PLACE素材已在旧16页稿、10/28大PPT和Golden repo证据中有引用/副本。若本机正好有周报，可供Codex优先提取高清原图，但不是阻塞项。

本机搜索：

~~~bash
mdfind -name "生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制-2"
mdfind -name "参考用 智能机器人实验员技术开发及应用-阶段汇报-朱翔2025.12.10 copy"
mdfind -name "25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）"
mdfind -name "金隅项目-周进度-20260911"
mdfind -name "金隅项目-周进度-20260924"
mdfind -name "金隅项目-周进度-20261016"
mdfind -name "点云场景重建与机械臂规划_研发工作量汇报_原模板14加2页"
~~~

若Spotlight没有结果，只在用户授权的常规目录查找：~/Downloads、~/Documents、~/Desktop、~/Library/Mobile Documents/com~apple~CloudDocs和当前ARES-R项目目录。不要全盘递归搜索邮件、隐藏目录或无关个人数据。

本机私有绝对路径只写入.gitignore覆盖的.local/acceptance_source_paths.json，不提交public GitHub。

## 5. 60页大PPT的重点媒体位置

已核验的页级媒体索引如下；Codex仍需读取本机实际PPTX的OOXML关系，若版本不同需重新索引。

- slide04：方案演进/空间理解；
- slide11–14：六阶段点云、ROI、自体过滤、支撑/结构分解；
- slide17–19：旧/新几何、覆盖量化、规划场景；
- slide27：求解性能/迭代配置；
- slide28–32：A/B规划、绕障轨迹、真实执行跟踪；
- slide37：持物几何错误/修正/恢复；
- slide40–41：性能模块和耗时；
- slide42：真实取放操作照片；
- slide45–60：尾部独立素材库，必须全部生成contact sheet后逐张挑选。

重点原媒体：
- slide11 shapes05/08/11/14/17/20：六阶段点云媒体，2400×1600；
- slide14 shape05：支撑/结构处理输出，2400×1600；
- slide17 shape11/12：旧/新几何对照；
- slide18 shape07/09：AABB/覆盖量化图，2400×1400；
- slide37 shapes05/07/09：持物模型问题与修正；
- slide42 shapes05/08/11/14/17/20/23/26：真实取放关键帧；
- slide50 shape05.png：3240×1440；
- slide51 shape04.png：3960×1260；
- slide55 shape07.jpg：3298×2473；
- slide59 shapes05/07/09/11/13/15/17：高分辨率现场/几何证据。

不直接贴整页截图。提取原始媒体、记录shape ID、SHA、尺寸、数据集ID和用途。

## 6. 视觉参考与周报的使用方式

- 2025/2026范例只学习“数据/处理/对照/结果”的展示方式，不复制数据和图。
- 9/11周报可用于早期规划到ServoJ接口打通，须标注历史日期与虚拟障碍范围。
- 9/24周报用于P3.7五段实机与TCP/工具图。
- 10/23周报用于PLACE持物模型问题。
- 10/28大PPT用于真实现场图和操作过程。
- 10/30原验收PPT只做母版。

## 7. 用户需要手动准备什么？

**默认不需要准备任何新素材。** Codex必须先从repo和本机查找。

仅当本机搜索确认原件不存在时，用户才需要手动复制缺失PPTX。最小必需集合：
1. 原始20261030V0.95机械臂母版；
2. 20261028 60页大PPT；
3. 20261028 12页方法版。

其他周报和范例为优先查找的可选补充，不应一开始就向用户索要。

建议缺失文件复制到：

~~~text
ARES-R/.local/acceptance_sources/
~~~

该目录必须加入.gitignore。用户不需要手动导出图片、整理媒体、重新上传点云或制作截图。10/21原始点云已在公开数据分支。

## 8. 字体和母版要求

必须继承原始20261030V0.95机械臂母版，保留BBMG标识、红色页眉、分隔线、页脚、页面比例和原生组件。

字体按用户之前明确要求：
- 中文主字体：黑体；
- 英文/数字主字体：Arial；
- 中文辅助字体：宋体；
- 英文辅助字体：Times New Roman；
- 公式独立处理字体、上下标、希腊字母和单位。

不要将4:3大PPT整页截图拉伸到16:9。应提取原始单图/矢量/视频媒体，在16:9母版中重新设计。
