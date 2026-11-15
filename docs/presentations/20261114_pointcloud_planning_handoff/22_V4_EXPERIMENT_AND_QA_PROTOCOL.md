# V4 补证实验、数据合同与PPT质量门禁

## 1. 实验优先级

### P0：DBSCAN ε×m真实参数组合实验——必须先尝试

这是甲方在录音中直接提出的问题。历史材料只证明DBSCAN配置为ε=12mm、m=8被使用，并没有提供完整ε×m参数扫描。不能把半径滤波18/3、20/4对照说成DBSCAN参数寻优。

**好消息：本轮需要的真实点云已经在ARES-R独立公开数据分支，不需要用户手动上传。**

数据源：
- 分支：codex/data-grasp-20261021-public；
- 原始点云包：20261021-study-clouds.tar.gz；
- 配套study包：20261021-center-grasp-planner-study.tar.gz；
- 数据索引：worklog/evidence/2026-10-21-grasp-source-data/DATA_INDEX.json；
- 两包SHA见21_V4_ASSET_MAP_AND_MANUAL_PREP.md。

### 1.1 先重建真实、同源、固定的聚类输入

优先复用已有离线流程：

- tools/presentation_evidence/replay_rasc.py；
- scripts/build_p3_production_scene.py中的deployment_prefilter；
- src/ares_r/perception/robot_owned_filter.py；
- src/ares_r/perception/residual_cloud.py中的clean_and_cluster；
- grasp_v3/MANIFEST.json。

先读取grasp_v3/MANIFEST.json中的：
- source_data_commit；
- source_camera_sha256；
- algorithm_source_sha256；
- code_base_commit；
- Python/依赖版本；
- ARCHIVED_CLEAN_EXACT_REPRODUCTION状态。

输入必须绑定：
- CAMERA SHA：62d45bd32a882bb6e8d3e080cc7b0edb239cdad8fab14d28c1dc69926d4f42a6；
- BODY SHA：56fa636b107a8bd568ea32e1b946adce0c1b287746f5c5cddb8a4a8738b43f99；
- observation：OBS_P3_LIVE_1792565261632216610；
- scene：SCENE_d9f27c83fc0949f1a709bd0c3e843b4a；
- 同帧双臂状态、几何、工具和固定外参revision。

注意：BODY文件已经是BODY/m坐标，不得再次转换。先按历史流程固定7.5mm ROI预处理、自体过滤、表格带排除、5mm cleanup voxel和radius_4_20mm前置滤波，再进入DBSCAN。必须先核对实际代码与历史manifest，不允许为了让结果更好看而临时改变上游。

### 1.2 九组参数矩阵

仅改变DBSCAN两个参数：

| ε / m | 5 | 8 | 12 |
|---|---|---|---|
| 8mm | A1 | A2 | A3 |
| 12mm | B1 | B2 | B3 |
| 16mm | C1 | C2 | C3 |

其余固定：
- CAMERA/BODY输入SHA；
- BODY转换、标定revision、ROI；
- 7.5mm deployment prefilter；
- robot-owned filter与同帧机器人状态；
- table band；
- cleanup内部5mm voxel；
- radius_4_20mm前置滤波；
- minimum_cluster_voxels=12；
- 支撑分解参数、基元膨胀、编译和计时环境；
- 代码commit、Open3D版本和线程数。

在clean_and_cluster中通过离线profile副本改变cluster_tolerance_m和cluster_min_points。不得修改生产默认值或仓库生产源码。新增脚本放tools/presentation_evidence/run_dbscan_grid.py，明确标注OFFLINE_ONLY，不连接硬件。

### 1.3 每组必须记录的指标

- 聚类簇数量；
- DBSCAN噪声点数量及比例；
- 后处理小簇剔除数量；
- 最终clean points；
- 关键结构/已登记参考区域保留率（只有源材料存在真实reference/holdout时才计算；没有就不编造）；
- 每个主要簇的AABB尺寸、中心和点数；
- 支撑分解后的基元数、观测点覆盖；
- 体积和（注明不是并集体积）；
- 清理和聚类分阶段耗时；
- 相同视角、同尺度点云可视化；
- 参数和代码版本SHA。

建议每格至少1次确定性结果＋3次计时重复；先预热，再计正式时间。计时统计口径保持一致。若Open3D/线程环境导致时间抖动，报告中保留median/P95和环境，不用单次最快值。

### 1.4 选择规则

不能预先指定12/8必须胜出。按以下顺序判断：

1. 是否保留真实关键结构；
2. 是否出现明显过合并或过分裂；
3. 是否将大量稀疏噪声带入障碍世界；
4. 净化后点覆盖和基元表达是否合理；
5. 处理耗时是否满足项目需求。

若多个配置效果接近，选用当前默认12/8并明确“满足本次工况要求”，不写“唯一最优”。若其他配置明显更好，只能提出新候选，不修改生产配置，不把它追记为历史采用参数。

### 1.5 复现差异处理

grasp_v3/MANIFEST.json中ARCHIVED_CLEAN_EXACT_REPRODUCTION为PARTIAL；已有README说明当前版本8,100点与历史8,086点有14点小簇保留差异。基线重放时必须记录这一差异，定位是small-cluster策略、代码revision还是其他输入变化。不能为了强行一致而删点，也不能把两个版本当作完全相同。

### 1.6 输出

~~~text
output/acceptance_v4/experiment/dbscan_grid/
  input_manifest.json
  frozen_pipeline.json
  grid_results.csv
  grid_results.json
  run_logs/
  pointcloud_panels/
  parameter_grid_contact_sheet.png
  selected_profile_rationale.md
  reproducibility_report.md
~~~

若实验因依赖/数据问题不能完成，记录真实错误和缺件，不用AI生成九宫格，不用模拟数据补齐。

## 2. P1：支撑层与局部细分独立贡献——可选，不阻塞正文

当前support_decomposition.py将支撑检测、凸起分解和XY/Z网格细分组合在一个实现中，并没有两个可直接切换的生产开关。不能简单把old AABB与new multi-primitive当成2×2独立因素消融。

只有在Codex能定义清楚、保持同一输入和同一几何合同的离线开关时，才运行：
- 支撑层分解开/关；
- 局部细分开/关。

四组固定同一输入、同一ROI、点云SHA、机器人过滤、碰撞膨胀、目标、规划预算。分别记录观测覆盖、基元数量、基元体积和、局部几何、碰撞检查、规划和CPU耗时。

如果无法独立控制因素或旧算法不可复现，标记NOT_COMPARABLE，不强行计算主效应/交互效应。此项不影响正文展示已经完成的支撑层实现和现有真实诊断。

## 3. 必须复核的历史实验与数据

### 3.1 S21-CLEAN

源：worklog/evidence/2026-09-21-p3-production-demo/avoid_final/cleanup/cleanup_benchmark.json。

| 前置滤波 | 剔除点 | clean点 | 簇 | 参考区 |
|---|---:|---:|---:|---:|
| radius18mm/3 | 14 | 12,744 | 13 | 53/53 |
| radius20mm/4 | 16 | 12,744 | 13 | 53/53 |
| statistical16/2.5 | 79 | 12,705 | 11 | 53/53 |

首组体素阶段包含冷启动开销，不得用该组总时间与后两组作纯性能比较。三组都保留53/53参考点。默认radius_4_20mm不是所有指标全面优于18/3的证明。

### 3.2 S21-ATTR / S21-CLEAR7

- S21-ATTR：212个实测点距最近P2 OBB≥30.01mm、距planner sphere≥20.52mm；旧膨胀AABB与sphere重叠27.40mm。
- S21-CLEAR7：7→167；基元体积和0.010413→0.004288m³；9,992/9,992点覆盖。
- 二者是不同snapshot，不能做成一张“同一帧修改前后”图。

### 3.3 S10-CAMERA与S21-GRASP-V3

- S10-CAMERA：32→235；3,747/3,747；体积和减少40.9%；OLD/NEW GPU都成功。
- S21-GRASP-V3：19→405；8,100/8,100；膨胀基元体积和减少68.6%；严格几何A/B两个端点都碰撞，未进入GPU。
- 不能把S10-CAMERA的GPU成功和GRASP V3的几何图拼成同一次成功A/B。

### 3.4 P3.3

四档碰撞代价激活距离10/20/30/40mm，每档3次重复求解；12次均未达到30mm模型净空门槛。每档重复结果相同哈希，不是12个独立随机样本。未生成执行包，无实机动作。

### 3.5 P3.4

- 5/7.5/10mm体素：4.039/3.191/2.672s；243/171/未报告基元；10mm箱体观测碎裂/丢失。
- seed：4/2 no Graph选用；Graph额外收益不明显。
- formal solve：CLEAR 5.095s、AVOID 6.822s。
- request wall：CLEAR 14.780s、AVOID 17.759s。
- A/B speed profile 0.20rad/s仅右臂A/B demo。
- AVOID fast roundtrip在P3.4未执行，不能宣传已完成。

### 3.6 P3.6/P3.7

P3.6 D1：198基元、模型gap 8.09/103.40mm、solve3.08s、execution11.41s、max tracking0.882°、0 fault/abort。

P3.7：五段真实运动逐段fresh scan/plan，全部到位。gap为模型间隙；不是抓取/接触/放置验证。

### 3.7 S19-PLACE / P3.8E / S21-PERF

- S19-PLACE：旧模型220×217×113mm；新主体160×100mm＋20mm夹持后段；从检查点恢复完成放置、释放和返回。不是无人干预连续全链。
- P3.8E：native-ready→HOLD 400.25s，motion147.74s、non-motion252.52s；observation→HOLD1266.92s含调试/人工交接；全任务周期未实测。
- S21-PERF：17.023→1.125s、15.176→0.830s、15.866→1.437s；15.1×/18.3×/11.0×是不同CPU模块，不可相加或外推整任务。

## 4. PPT证据矩阵和每页QA

每页建立一行evidence_matrix.csv，至少包含：

slide_no, slide_title, claim, dataset_id, source_report, source_json_or_log, source_code_commit, source_media, source_media_sha256, metric_definition, unit, validation_level, run_date, speaker_note, prohibited_inference, QA_status。

每页通过以下门禁：

- G0：原始报告/JSON/图/源码已找到；
- G1：数据集ID、输入SHA和代码版本确认；
- G2：图表数值与源文件逐字段一致；
- G3：页面结论不超过证据支持范围；
- G4：讲者备注含设置、限制、失败和来源；
- G5：渲染图检查后无视觉误导。

任一门禁失败，移到备查页或标记缺证，不进入正文“已完成成果”。

## 5. 真实媒体提取和视觉QA

- 必须从PPTX OOXML relationship提取原始图片/视频，记录SHA、shape、slide和像素尺寸。
- 大PPT45–60页必须逐页contact sheet检查。
- 不将整页截图放大；不把AI绘制的几何场景当作真实实验。
- 同源OLD/NEW固定视角和尺度；不同数据组分面标注。
- 表格和条形图用PowerPoint原生图表/表格；SVG可保留矢量。
- 公式按用户指定字体单独处理。
- 必须使用原20261030V0.95母版，保留Logo、页眉、页脚、红线和比例。

## 6. 最终渲染与质量门禁

必须交付：
- PPTX；
- PDF；
- 每页PNG；
- 完整contact sheet；
- speaker_notes.md；
- evidence_matrix.csv；
- media_index.csv；
- metric_source_ledger.csv；
- technical_qa.md；
- visual_qa.md；
- customer_requirement_check.md；
- missing_evidence.md。

至少完成两轮渲染：
1. 初排后逐页检查文字溢出、图片分辨率、字体替换、表格可读性、页脚和母版；
2. 修订后再次渲染，并逐页复核所有关键数字、图例、实验ID和验证等级。

若Mac PowerPoint可用，最终以PowerPoint实际渲染为准；否则使用LibreOffice导出并在QA中标注渲染环境。不得只凭PPTX能打开就宣称完成。

## 7. 绝对禁止

- AI编造历史失败、参数对照、成功率、规划时间、重试次数或实机视频。
- 将录音中的3cm/5cm、5次重试、20秒/100多秒等讨论举例写成实测。
- 把planning-only写成实机执行。
- 把冻结回放写成现场实时测试。
- 把独立world验证写成独立self-collision认证。
- 把模型净空写成物理测距保证。
- 把S21-ATTR和S21-CLEAR7拼成同帧前后对照。
- 把S10-CAMERA和S21-GRASP-V3的有利结果拼成同一次OLD失败/NEW成功。
- 把CPU模块加速宣传为整任务加速。
- 将P3.9估计的395s写成已测完整周期。
- 将10/19 Golden recovery写成一键无人干预连续成功。
- 为了视觉完整而填充未执行实验的表格/热力图。
