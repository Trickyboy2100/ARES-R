# V7 来源PPT、真实图件与V6增量复用地图

## 1. 最小手动准备原则

**默认不向用户索要新图、不要求现场拍摄、不要求上传点云或重做代码。**

此次用户已上传：
- \`ARES-R_甲方研发工作量汇报_V6_丰富过程版.pptx\`（16张、16:9、实际约29MB）；
- \`Recording 154(2).txt\`（2026-11-13，14m57s）；
此前对话已上传原模板与20261028大PPT/方法PPT、若干周报。

这些字节在ChatGPT对话中可访问，但不代表用户Mac/Ubuntu本地Codex自动拥有。Codex先从本机授权项目目录、Downloads、Documents、Desktop、iCloud/移动盘目录寻找，找不到时**只请用户复制确实缺失的单个PPTX**到 \`ARES-R/.local/acceptance_sources/\`（gitignore），不要求人工截图或压缩全仓库。

Mac：
\`\`\`bash
mdfind -name "ARES-R_甲方研发工作量汇报_V6_丰富过程版"
mdfind -name "20261028-水分细度目标识别与场景自适应规划控制"
mdfind -name "生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂"
\`\`\`
Ubuntu（限定在授权目录，避免全盘扫描）：
\`\`\`bash
find "$HOME/Downloads" "$HOME/Documents" "$HOME/Desktop" .local -type f \
  \( -iname "*ARES-R*V6*.pptx" -o -iname "*20261028*水分细度*.pptx" -o -iname "*20261030V0.95*机械臂*.pptx" \) 2>/dev/null
\`\`\`
不要向公开仓库上传私人原始PPTX、用户录音、照片原件和本机绝对路径。

## 2. 重要原始PPT及用途

| 文件 | 已知资产 | 主要用途 |
|---|---|---|
| \`ARES-R_甲方研发工作量汇报_V6_丰富过程版.pptx\` | 16页，已继承验收模板，嵌入33张以上真实/数据图片 | **V7增量母件**；直接复制shape、notes和原图，而不是旧V5重做 |
| \`生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx\` | 原BBMG验收模板 | 保留官方Logo/页眉/红线/页面比例、字体 |
| \`20261028-水分细度目标识别与场景自适应规划控制.pptx\` | 60页，后16页有较多可复用的点云与实物素材 | 工位全景、真实夹爪、箱体、轨迹、Golden关键帧 |
| \`20261028-水分细度目标识别与场景自适应规划控制-2.pptx\` | 方法版与讲述备注 | 查原方法参数定义/公式，但不再以原理为主角 |
| \`25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）.pptx\` | 甲方视觉参考 | **只参考研发过程呈现方式**，不得复制视觉模型训练数据到本组 |
| 9/11、9/24、10/16、10/23、10/30周报（存在者） | 实机、控制器、TCP、箱体、取放流程 | 补真实照片/演示，不混用源run数值 |

优先提取**原始嵌入媒体**而不是截图整个4:3 PPT；保留文件SHA、slide号、shape关系及crop信息。20261028大PPT第45–60页必须生成contact sheet逐页审阅，优先挖掘真正清晰的现场图，不要为了显示图多而使用缩小的垃圾画面。

现有旧索引（需本机OOXML再次校验）：
- slide11–14：六阶段点云/ROI/本体过滤/支撑结构；
- slide17–19：旧/新几何和规划对照；
- slide26：夹爪与料盘耳部；
- slide27–32：规划时间、路径、运动控制；
- slide37：持物模型修正；
- slide40–41：性能计时；
- slide42：取料/抬升/放置关键帧；
- slide45–60：独立高清媒体素材。

## 3. Repo中已经存在且建议实际使用的图件

根目录：
\`docs/presentations/assets/20261028_rasc_curobo/\`

### 点云处理（V7页02/05/06/07）
- \`grasp_v3/panels/rasc6/01_raw_cloud_iso_focus.png\`
- \`grasp_v3/panels/rasc6/02_roi_iso_focus.png\`
- \`grasp_v3/panels/rasc6/03_robot_owned_filter_iso_focus.png\`
- \`grasp_v3/panels/rasc6/04_support_decomposition_iso_focus.png\`
- \`grasp_v3/panels/rasc6/05_multi_primitive_iso_focus.png\`
- \`grasp_v3/panels/rasc6/06_curobo_world_iso_focus.png\`
- \`grasp_v3/details/ownership_before.png\`、\`ownership_removed.png\`
- \`grasp_v3/MANIFEST.json\`、\`VISUAL_MANIFEST.json\`、\`README.md\`

同一阶段的top/front/iso以及.svg在同目录，优先高清矢量或PNG主体裁切版本。**这6张来自同一10/21 GRASP源数据，不是9月或10/10 CAMERA。**

### 多基元几何（V7页07）
- \`panels/geometry_ab/old_boxes_zoom.png\`
- \`panels/geometry_ab/new_primitives_zoom.png\`
- \`panels/geometry_ab/error_occupied_space_slice.png\`
- \`clarity_v2/section_old_new_pair.png\`
- \`grasp_v3/geometry_ab/pair_section_z0.94.png\`（不同数据组，图注区分）

另从
\`worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png\`
取212点误占据归因，属于S21-ATTR，与S10-CAMERA旧/新图不可画同源箭头。

### 规划（V7页09–13）
- \`panels/planning/planning_old.png\`
- \`panels/planning/planning_new.png\`
- \`panels/planning/route_overlay.png\`
- \`panels/planning/gap_vs_path.png\`
- P3.3：
  \`worklog/evidence/2026-09-22-p3-3-execution-hardening/visualization_final/p33_clearance_profile_sweep.png\`
- \`panels/performance/fast_vs_quality_profiles.png\`
- \`grasp_v3/planning/real_gpu_fk.png\`（10/21 GRASP回放，不可作为9/21 S21-CBASE的同一次轨迹）
- 9/21 S21-CBASE真实三视图/大PPT原始图。

注意：
- S10-CAMERA old/new均可规划，不制造“OLD失败NEW成功”；
- S21-GRASP V3严格几何A/B端点均碰撞而未进入GPU，不与“成功GPU图”跨条件合成；
- P3.3的12次均不放行；\`gap_vs_path.png\`若来自其他数据组，只能用来说明方法，不与P3.3图表做同次前后对照。

### ServoJ与控制（V7页14）
- \`panels/servo/case1_tracking_error_6joints.png\`
- \`panels/servo/case1_joint_velocity_acceleration.png\`
- \`panels/servo/case1_joint_target_vs_actual_J1.png\`... \`J6.png\`
- \`panels/servo/case2_tracking_error_6joints.png\`
- \`panels/servo/case2_joint_target_vs_actual_J1.png\`... \`J6.png\`

以上case1/case2是独立的实机诊断素材，**不能无核对地当成P3.4五档commission同一run**。P3.4数值来自P3.4报告和现场回执。需在图例标注运行ID/类别。

### 持物与Golden（V7页17–18）
- \`panels/attachments/payload_wrong_footprint.png\`
- \`panels/attachments/payload_corrected.png\`
- \`panels/attachments/place_recovery_stage_times.png\`
- 10/19 Golden \`README.md\`、\`COMPLETED.md\`、\`REPORT.json\`
- 大PPT slide42原图，优先真正的实物抓取/抬升/预放置/松爪四关键帧。

### 性能（V7页19）
- \`panels/performance/latency_critical_path_waterfall.png\`
- \`panels/performance/latency_module_before_after.png\`
- \`panels/performance/cpu_backend_comparison.png\`
- \`grasp_v3/metrics/historical_cpu.png\`

与源\`P3.8E\`任务时间审计和10/21 CPU benchmark分别配对，不能跨源合成一个“整机加速倍率”。

## 4. V6具体视觉缺陷→V7证据补齐

| V6 | 现状 | V7修订要求 |
|---|---|---|
| 01 | 3张实物图、概述偏理念 | 加经核实研发里程碑和两项工作包，去问句 |
| 02 | 4张点云阶段图，多数主体较小 | 同一10/21局部点云固定视角，扩大robot-owned变化与输入SHA |
| 03 | 3张几何图，但主要展示最后“32→235” | 移至支撑实验之后，增加源内剖面与独立212点归因标签 |
| 04 | **0张嵌入图片**，体素和滤波挤一页 | 分V7-03/04两页；体素真实ROI、滤波同源对照＋参考区域 |
| 05 | 9张DBSCAN小图，投屏看不出关键结构 | 保留九格，另3张典型同ROI放大；找原results.json |
| 06 | 2张控制器/夹爪图 | 放大工具、实体与控制点区分，加入实际模型与代码工件 |
| 07 | 1张GPU轨迹，接口修复都在文字 | 增真实joint mapping代码/测试日志和输入输出差异 |
| 08 | 两张轨迹和表，解释偏结果 | 补现场箱体与world构造、BLOCK拒绝、源SHA与状态流 |
| 09 | 1张净空图，限制物体不够醒目 | 加同源限制对象ROI与四档真实轨迹；保留12/12负结果 |
| 10 | **0张嵌入图片**，种子/Graph/常驻混在一起 | 分V7-12/13；profile对照和真实worker调用时序分别展示 |
| 11 | 1张独立保护中止曲线，另一组速度数据 | 找同run曲线；找不到则明确“不同运行的两种诊断” |
| 12 | 1张D1点云路径 | 加真实工位局部与实际控制器回执，放大起点/终点 |
| 13 | 2张，表格压住实机内容 | 实机3关键帧＋五段快照/轨迹哈希连续示意 |
| 14 | 3张持物几何图 | 更突出旧盒/新盒/实物边界，确认来源是Golden |
| 15 | 5张现场照片 | 保留并放大一张主帧，区分原任务段与恢复段 |
| 16 | **0张嵌入图片**，CPU数据像普通对照表 | 改为任务事件堆叠/瀑布＋三个模块before/after大图；两种数据源明显分区 |

## 5. 原生媒体提取要求

Codex可使用python-pptx和OOXML，但必须留存：
- 原V6原件SHA；
- slide顺序、layout/master映射；
- shape IDs、图片relationship、图片原二进制SHA、尺寸和crop；
- 本次实际采用的\`source_ppt/repo_path\`；
- 数据组/run ID、验证等级、放到V7哪页。

不直接截图整页放到下一版，不丢V6原有讲者备注，复杂媒体的备注中必须能回到同一原始来源。

媒体台账建议CSV：
\`v7_slide,v6_slide,source_path,source_slide,shape_id,source_sha256,role,crop,source_case,evidence_level,notes\`

## 6. 甲方可读性与真实性的双审查

### 看得清
- 图片上对象主体、轨迹和图例在普通投影比例下能辨识；
- 原始图中小字可遮挡/裁掉，用PPT原生文字大字重写；
- 同源比较统一视角、透视、尺度、单位、膨胀条件；
- 表格字体不因行数过多缩小到无法阅读；二级细项转speaker notes；
- 不用AI合成相似点云代替实验。

### 讲得明白
- 各页明确“我们做的研发动作”，如\`配置→运行→比对→取舍\`或\`代码→回归→物理执行\`；
- 每张图说明来自哪里，不能让领导以为规划界面图就是实机执行；
- 成功案例与负结果都留下，不能消除P3.3故障而只显示后续的D1/P3.7；
- 不把示意图写成实验图片，不让RASC名称掩盖其组成的成熟算法。

## 7. 依赖状态与回退策略

必须先完成source audit，输出：

- \`SOURCE_V6_FOUND\`；
- \`SOURCE_LARGE_PPT_FOUND\`；
- \`DBSCAN_RAW_RESULTS_VERIFIED\`；
- \`SUPPORT_OFFLINE_ABLATION_RUN\`；
- \`P33_RAW_SWEEP_VERIFIED\`；
- \`P34_PROFILE_AND_WORKER_VERIFIED\`；
- \`GOLDEN_RECOVERY_EVIDENCE_VERIFIED\`。

任何关键媒体缺失时：
- 先用V6已经嵌入的真实媒体；
- 再用repo当前图集；
- 再用原大PPT；
- 最后用**标记为示意的原生PowerPoint几何图**。
不阻塞全篇，不伪造结果，也不让用户承担大量手工素材提取任务。
