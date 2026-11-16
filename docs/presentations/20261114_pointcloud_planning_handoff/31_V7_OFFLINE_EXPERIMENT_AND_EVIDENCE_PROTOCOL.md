# V7 对照实验、研发工件与证据验证实施规程

本文件的目的是**真实补足甲方期待的研发过程**，不重写历史、不连接设备、不靠AI造数。所有实验均为归档点云/规划请求的软件离线运行；如果无法复现则登记缺件、退回已有历史证据，不得填假数据。

## 1. 工作优先级与实验归属

| 等级 | 实验或核验 | 预计产物 | 状态说明 |
|---|---|---|---|
| P0 | 已上传V6的DBSCAN九格来源复核 | `results.json`、图片、输入SHA、版本、统计定义 | V6有数值与九张图，但repo文档分支未确认原始JSON存在 |
| P0 | 支撑层高度/凸起阈值敏感性 | 同一帧曲线、分类图、对照表、logs | 源码已具备，**不等于历史已跑完整扫描** |
| P0 | 局部几何OLD/NEW真实同源图放大 | 同视角ROI、点覆盖、局部误占据归因 | 历史证据现成，不必新跑 |
| P0 | cuRobo历史候选/碰撞参数复核 | P3.3四档×3、P3.4种子/Graph、限制障碍图 | 历史日志现成；不虚构成功率 |
| P0 | 10/19持物修正与Golden恢复日志核验 | 检查点事件、照片匹配、源hash | 实机已发生，必须保留故障 |
| P1 | 支撑/局部网格消融及几何覆盖 | 网格规模、覆盖率、运行时、切面图 | 新增离线，若公平合同不成立可标NOT_COMPARABLE |
| P1 | ServoJ同一次run命令/反馈复核 | 关节曲线、速度、误差峰值、到位判定 | 只能用真实控制器读回；不存在则用已有两类独立证据 |
| P1 | 持物/SceneSnapshot/关节映射代码回归 | commit、diff片段、测试日志、失败注入 | 软件测试≠实机 |
| P2 | 附录中的多工况扩展与完整统计 | 只纳入备查材料 | 不影响19页正文和交付 |

**不把每个历史截图都算一组实验**。按真实run ID、SHA、参数向量去重；同一次运行提取不同切面只能算同一次案例的多视角。

## 2. 证据分层：每一张图先定“来源级别”

| 级别 | 物理含义 | 可用于正文的描述 |
|---|---|---|
| H1 | 真实机械臂/控制器/AMR回执 | “受监督实机执行”“控制器到位/中止”“真实运动耗时” |
| H2 | 历史实测点云的冻结规划或预处理JSON | “冻结真实数据回放”“规划级验证” |
| N1 | 此次新执行的历史实测点云离线参数实验 | “补充离线试验”，必须注明新日期和代码版本 |
| R1 | 生产源码与测试 | “模块开发与回归测试”，不得说物理执行 |
| S0 | 为解释而手绘的机制示意 | “示意图”，**不计入已完成研发试验** |

**实验台账统一字段：**

`experiment_id, source_case, raw_sha256, input_sha256, body_frame_revision, robot_state_sha, tool_geometry_sha, scene_snapshot, code_commit, source_script, changed_parameter, fixed_parameters_json, repeat_id, result_json, validation_level, wall_time_s, cpu_time_s, outcome, caveat`

任何一组没有source_case和参数/版本记录，不得进入“实验次数”统计。

## 3. P0-A｜V6已出现DBSCAN九格的原始证据核查

V6第05页九格实际写有（保留点数）：

```
EPS(mm) x min_points   5       8       12
8                   4111     107        0
12                  8469    8100     2451
16                  8535    8484     8379
```

**这些数据已显示于用户上传的V6 PPTX；但仅凭PPT图片不能推定输入处理合同/噪声/簇数已经完全核实。**

### 执行步骤
1. 在原V5/V6本机制作目录优先定位：
   - `output/acceptance_v5/dbscan/results.json`；
   - `environment.json`；
   - `eps8-m5.png` ... `eps16-m12.png`。
2. 校验九格`kept_points`与V6中的9个数字逐项相同；记录输入点云SHA、相机/机器坐标、ROI、前置滤波、cluster_min_points与minimum_cluster_voxels的不同含义；
3. 如有原始日志，提取`n_clusters, n_noise, n_kept, runtime, median timing`；若无则不得创造；
4. 对每个图核对同源、同尺度、同视角；建议为主画面选择`8/12`、`12/8`、`16/8`，放大同一箱体/支撑区域；
5. 如目录不存在，读取公开10/21点云归档及`grasp_v3/MANIFEST.json`，在**离线只读副本**中使用相同上游处理重放；
6. 若代码版本差异产生不同结果，保留两份结果与diff，不可以为了追V6数字删点；无法匹配则把旧数据标为“V6成稿记载、原始实验文件未核验”，不将其作为独立重复实验事实。

### 输入数据已有出处
`codex/data-grasp-20261021-public` 分支：
`worklog/evidence/2026-10-21-grasp-source-data/`
- `20261021-study-clouds.tar.gz`，SHA256：
  `206e2fdef8886750ca7545ee9b23596c85a9252a45a949ed54d4cca60e3bbd60`；
- `20261021-center-grasp-planner-study.tar.gz`，SHA256：
  `f0e6d87e825b6f653d4154e4a1c1c31445ac2b32efc15da9d05a85f98c5188d8`。

归档关键文件：
- `logs/body_cloud/captures/20261021_144732_60b67baa/pointcloud_camera_mm.npy`；
- `logs/body_cloud/artifacts/20261021_144734_5a364d75/body_cloud.npz`；
- `.../manifest.json`；
- study目录中的`manipulation_observation.json`和`whole_robot_geometry.json`。

**BODY点云单位m，CAMERA原始单位mm。** 不能把BODY再除以1000或重复应用外参。

### 结果判据（不能只看点数）
- 核心结构有无丢失；
- 物体支撑与凸起是否错误并簇；
- 噪声保留/剔除比例；
- 簇数与小簇剔除数量；
- 点覆盖与几何基元数量；
- 运行时间。

不能提前指定12/8一定“最优”。如结构、速度比较不支持明显优越，使用“当前工程配置满足本案例需求；新增敏感性实验揭示参数耦合”。

## 4. P0-B｜支撑层高度与凸起检测的真实离线敏感性实验

### 当前源码结构（已查验）
文件：`src/ares_r/perception/support_decomposition.py`

`DecompositionProfile`默认值：

| 参数 | 基准 | 作用 |
|---|---:|---|
| `support_bin_m` | 0.005m | Z高度分箱 |
| `support_band_m` | 0.010m | 候选峰上下的支撑带 |
| `support_min_points` | 120 | 最少候选点数 |
| `support_min_span_m` | 0.100m | 最小水平跨度 |
| `protrusion_min_height_m` | 0.025m | 高于支撑的凸起阈值 |
| `component_tolerance_m` | 0.018m | 结构连通DBSCAN邻域 |
| `component_min_points` | 10 | 连通最小点数 |
| `tile_xy_m` | 0.040m | 局部XY网格 |
| `slice_z_m` | 0.030m | Z切片间隔 |
| `inflation_m` | 0.007m | 碰撞几何膨胀 |

**源码更详细的真实逻辑：**
- 使用Open3D混合邻域估计法向：搜索半径25mm、最多30邻点；
- 在Z向5mm高度直方图寻找局部峰；
- 支撑候选需要足够点数、平面跨度及`abs(normal_z)>=0.85`的水平法向比例≥0.45；
- 在XY局部足迹内按与支撑高度差分配观测，凸起阈值为25mm；
- 支撑/凸起/结构/未知点采用多基元表达，剩余已观测点不能直接删除；
- 是否已有真实试验扫过上述阈值，**待证据审计**。源码默认不等于最优性验证。

### SUP-01｜支撑层带宽敏感性，建议3组
只改变`support_band_m`：
`0.005, 0.010, 0.015` m；
固定同一个源点云、BODY外参、ROI、前置净化、`support_bin_m=.005`、法向、凸起阈值、网格和编译规则。

记录：
- support候选个数及各自z中位数；
- 每个候选点数、水平法向比例；
- 已确认工位支撑ROI的实测覆盖；
- 被误归为支撑的凸起点数量（仅有真实标注ROI时才可统计）；
- `timing_s.support_detection`；
- 同一截面的支持/凸起标签图。

### SUP-02｜凸起高度阈值敏感性，建议3组
只改变`protrusion_min_height_m`：
`0.015, 0.025, 0.035` m；
其他固定（尤其support_band=10mm）；

记录：
- `SUPPORT_SURFACE/PROTRUDING_OBSTACLE/STRUCTURE/UNKNOWN_OCCUPIED`各类点数及基元数；
- 独立凸起组件数量、尺度和局部真实观测是否仍覆盖；
- **同一规划点对**的模型gap/可行状态仅在同一固定起终点与world条件下比较；
- 时间与局部几何变化。

### SUP-03｜支撑层与凸起阈值3×3交互（可选，若P0两组三档结果明显耦合）
组合band `5/10/15` mm × protrusion height `15/25/35` mm。9组全部固定输入与源代码commit，显示“支撑候选稳定性/正确结构归属”热图。若不能建立人工支撑参考标记，**不计算语义准确率**，只展示稳定性/几何变化，不称为精度最优。

### 可视化
对同源点云出四张高清图：
1. Z高度柱图/支持层候选峰位置；
2. support带位置及保留点；
3. protruding构件和unknown占据；
4. 基元输出与原始点云叠加。

横纵坐标、单位、视角/点大小一致；附输入SHA和图例。
如缺人工真值，“高度峰被识别”与“分类正确”不可混用。未知点不得自动转为自由空间。

### 实现纪律
- 使用`dataclasses.replace(DecompositionProfile(), support_band_m=...)`等**离线profile副本**；不可修改生产默认；
- 不接相机/机械臂，禁止把试验脚本导入现场服务；
- 在`tools/presentation_evidence/experiments/`新增只读可运行脚本，输出至被gitignore的`output/acceptance_v7/experiment/`；
- 每组记录seed（如果涉及）、输入SHA、代码commit、运行时、失败、空输出；
- 只有真实运行才写“SUP-01完成3组”，不能提前把规划矩阵写入已完成页。

## 5. P1-C｜局部网格与碰撞体表达对照

同一冻结S10-CAMERA或S21-GRASP V3输入（**每张图只用一个**）：

### GEO-01｜局部XY网格
`tile_xy_m`: 20/40/60mm；固定`slice_z_m=30mm`、`inflation_m=7mm`；
### GEO-02｜Z切片
`slice_z_m`: 15/30/45mm；固定`tile_xy_m=40mm`；
### GEO-03｜baseline
整簇单AABB vs 支撑/凸起多基元；保留相同膨胀、输入、碰撞世界编译和目标。

**必须记录**：
- 输入观测点数与唯一覆盖数（不是简单对每个primitive point_count求和后超过100%）；
- 碰撞基元数；
- `sum_i volume(primitive_i)`，标清“体积和”，不能写占据并集体积；
- 对同一固定ROI/切面的网格投影“桥接/填空”面积，不把稀疏未观测区直接定性为可安全通行；
- 场景编译耗时/峰值内存；
- 规划级可行性（如果对应同一可解的起/终点），不要为通过而调整碰撞门限。

重要：S10-CAMERA的32→235、3,747/3,747、体积和−40.9%是现有同源证据；S21-GRASP V3 19→405、8,100/8,100和−68.6%是另一组，不能混为一条A/B因果链。

`decompose_support_objects`同时执行支撑归属和局部网格，代码没有两种生产开关，**不得未经验证就把“只支撑”“只网格”当做公平独立2×2消融**。若需要比较，用离线明确实现的可控对照/输出替换，并标记`OFFLINE_ABLATION`；不能直接修改生产算法。

## 6. 规划与控制：优先复核真实历史实验，不靠虚构试验补页

### PLN-01｜CLEAR/AVOID/BLOCK
- 同一A/B目标，但CLEAR和AVOID使用不同真实场景快照；
- BLOCK为人工构造的封闭目标；
- 记录同源输入、轨迹长度、限制障碍、规划状态与拒绝输出。
- **规划级**，无任何现场运动证明。

### PLN-02｜P3.3四档×三次碰撞代价
- 固定冻结AVOID场景、A/B、工具几何、30mm门槛；
- 四档10/20/30/40mm，每档3次，12/12不通过；
- 最小模型gap 9.326/14.787/14.787/14.787mm；
- 独立CPU密集核验及限制对象`observed_support_03_component_01_protruding`；
- 每档内轨迹哈希相同、非独立随机采样；
- **不得修改工位、降低30mm门槛或虚构成功路径**。

### PLN-03｜P3.4种子数/Graph
- 8/8 no graph为历史范围；4/4、4/2 no graph、4/2 graph按报告比较；
- 明确profile/工况/计时P50；
- 选用4/2 no Graph，Graph没有显著增益；
- 对每次请求记录初始化、world update、formal solve、dense validation、后处理与包生成的存在性，但仅有实测阶段时长才画堆叠，不分摊“未知时间”。

### PLN-04｜常驻planner场景切换
- P3.4 CLEAR→AVOID→CLEAR、验证返回CLEAR轨迹哈希一致；
- 工程实现调用链：初始化+warmup一次→`update_world`→正式solve→后处理/核验；
- 需要显示真正改动的源码或commit/worker接口；
- 不声明一切系统瓶颈由CUDA Graph解决。

### CTRL-01｜右臂ServoJ速度调试
- 0.12/0.14/0.16/0.18/0.20rad/s是现场已commission的右臂A/B演示阶梯；
- 找原运行命令与读回J1–J6，确认每个leg时间和误差计算窗口；
- 同一run无法查到完整时序时，不编曲线。可用已存真实统计/回执＋独立保护中止曲线（明确不同run）；
- 原限速与碰撞保护不被调低；
- 0.20rad/s只属于`RIGHT_ARM_AB_DEMO_ONLY`。

### CTRL-02｜P3.6 D1、P3.7五段
- D1近障起点单次真实受监督：3.08s规划、11.41s实机、0.882°最大跟踪；
- P3.7五段真实运动，逐段fresh SceneSnapshot/trajectory hash，到位并保留初次P→Q被状态拒绝的记录；
- D1/P3.7不是同一输入的前后方法消融；
- 模型间隙不是现场物理测距或独立安全认证。

## 7. Golden持物修正：真实故障与恢复的时间序列

必须直接读取：
- `docs/golden/2026-10-19/README.md`；
- `docs/golden/2026-10-19/evidence/v17-place-recovery-completed/COMPLETED.md`；
- 同目录`REPORT.json`、`events.json`、`after.json`、`PLACE_DESCENT50.json`、`RELEASE.json`；
- Demo限定持物几何相关代码和配置。

分两段清楚表示：
1. 原任务已经实机完成：取料、连续230mm抬升、约1.53m底盘转运；
2. PLACE故障后：旧附着模型220×217×113mm，修订160×100mm主体＋20mm夹持后段，旧计划失效→fresh scene/plan→50mm下降→释放读回→底盘返回；恢复事件125.34s。

**禁止：**
- 不说同一脚本无人干预全链成功；
- 不把125.34s当完整取放时间；
- 不从单次恢复推出自动泛化所有物料；
- 不说已独立视觉认证落座/力控插入。

## 8. 软件工程量需要什么工件

对于每一处“我们开发了模块”，Codex至少收集三样：
1. **调用点/源码**：`file:line`、函数与输入输出；
2. **一个明确的版本变化或设计决策**：例如`joint_names`映射、常驻planner、旧scene失效、持物归属；
3. **验证**：真实unittest/pytest结果、规划回放、native回执或故障注入。

优先关键模块：
- `src/ares_r/perception/robot_owned_filter.py`；
- `src/ares_r/perception/residual_cloud.py`；
- `src/ares_r/perception/support_decomposition.py`；
- `src/ares_r/motion/runtime_goal_ik.py`；
- `src/ares_r/motion/planner_joint_mapping.py`；
- `src/ares_r/motion/production_scene_worker.py`；
- `src/ares_r/motion/independent_path_validation.py`；
- `src/ares_r/manipulation/demo_place_contact.py`；
- `config/ab_demo_deployment_profile.json`；
- `docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md`。

如需“年度研发投入数量”则只统计本模块**实际验证**的独立提交/工件/工况，不把整仓库其他人/其他方向的代码行数算成本组工作量。

## 9. 性能时间定义与不可相加约束

各类时间必须分别标：
- capture time；
- fresh scan/state/scene；
- formal cuRobo solve；
- warm request wall；
- native execution；
- native-ready→HOLD audit；
- replay CPU module benchmark。

示例真实数据：
- P3.4 capture+NPY 2.873s，scene build3.417s，fresh scan/state/scene8.270s；
- formal solve CLEAR5.095s、AVOID6.822s；
- request wall CLEAR14.780s、AVOID17.759s；
- P3.8E native-ready→HOLD400.25s，motion147.74s，non-motion252.52s；
- S21-PERF三项独立CPU模块17.023→1.125s、15.176→0.830s、15.866→1.437s。

禁止：
- 把2.873+3.417简单作为8.270的全部分解；
- 把5.095s当整次请求；
- 把P3.8E400.25s当完整Tray→Groove；
- 把三种CPU倍数作为总任务加速；
- 把P3.9的395s工程估计写成实测。

## 10. 输出包与停止规则

在被忽略目录`output/acceptance_v7/experiment/`中生成：

```
dbscan/
  input_manifest.json
  raw_results.json
  grid_results.csv
  nine_panels/
  key_roi_comparison.png
  interpretation.md
  reproduction_notes.md
support/
  input_manifest.json
  supp01_band_sweep.csv
  supp02_protrusion_sweep.csv
  supp03_interaction.csv            # 只在真实执行后存在
  height_histogram.png
  classified_support_protrusion.png
  support_primitive_overlay.png
  comparison_notes.md
geometry/
  input_manifest.json
  same_source_old_new/
  coverage_metrics.json
  voxel_section_ab.png
planning/
  p33_traces_and_limits/
  p34_profile_reconciliation.csv
  p34_worker_callgraph.md
servo/
  matched_command_feedback.csv      # 只在真实回执存在时
  exact_run_trace.png
golden/
  recovery_event_timeline.csv
  image_event_links.csv
evidence_registry.csv
experiment_failure_log.md
```

**三类停止条件：**
- 缺input SHA/缺同一源点云/缺运行配置 → 该实验`INPUT_MISSING`，不跑假的；
- 多变量同时改变或世界约束不同 → 标`NOT_COMPARABLE`，不可宣传改善百分比；
- 实验在离线规划/安全门禁被拒 → 如实显示失败，不降低门槛、不绕过。

**最终只有真实完成的实验才能进入正文**；其他全部用已有H1/H2/R1证据和“已完成的模块开发”进行诚实、充分的结题展示。
