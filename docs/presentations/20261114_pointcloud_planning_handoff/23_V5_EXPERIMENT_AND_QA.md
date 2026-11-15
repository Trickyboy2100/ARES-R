# V5 补证实验、证据等级与最终QA门禁

## 1. 本轮最重要的补证：DBSCAN ε×min_points

### 1.1 当前真实证据状态

甲方点名问过DBSCAN两个参数如何确定。现有S21-CLEAN记录比较的是前置滤波方案：
- radius18mm/3邻点；
- radius20mm/4邻点；
- statistical16邻域/2.5σ。

三组都固定DBSCAN ε=12mm、min_points=8。因此现有材料**不能**证明ε=12mm、m=8是经过完整敏感性实验选择出来的最优参数。

### 1.2 原始数据搜索顺序

优先找历史S21-CLEAN或S21-CBASE原始点云：

- S21-CLEAN capture pointer：worklog/evidence/2026-09-21-p3-production-demo/avoid_final/capture_pointer.json；
- 目标manifest：/home/yikun/ARES-R/logs/body_cloud/artifacts/20260921_110615_8576001f/manifest.json；
- capture：20260921_110610_60662091；
- S21-CBASE capture pointer：worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/capture_pointer.json；
- 目标manifest：/home/yikun/ARES-R/logs/body_cloud/artifacts/20260921_161451_830b7857/manifest.json。

这些是历史服务器路径，不代表当前Mac一定有文件。Codex只在用户授权的本机项目目录、Downloads、Documents、Desktop、iCloud Drive等常规目录中查找；不得自动SSH实验室服务器。

检查：
- 原始点云文件是否真实存在；
- manifest与文件SHA；
- 点数、单位、坐标系、固定外参；
- 采集时双臂状态和机器人/工具几何revision；
- 原始ROI和前置处理参数；
- 是否能精确复现S21-CLEAN的12,791点净化输入或对应上游点集。

若S21-CLEAN原始数据可用，优先在同一历史数据上完成9组实验，结果可直接回答甲方对历史参数选择的追问。

### 1.3 S21原始数据不存在时的替代方案

ARES-R独立公开分支codex/data-grasp-20261021-public包含10/21 GRASP原始CAMERA/BODY和配套study归档，用户无需重新上传。Codex可以在核对SHA、代码revision和完整处理链后，在这组数据上开展**新的离线参数敏感性实验**。

但必须标注为：
- 数据集：S21-GRASP-V3 / 2026-10-21；
- 实验日期：本轮真实执行日期；
- 性质：新增冻结离线回放；
- 不得称为9/21 S21-CLEAN历史参数寻优；
- 不得将结果回填成历史已经完成的参数选择。

如果不能从原始BODY点云重建同一上游处理输入，或不能固定self-filter、ROI、体素和前置滤波，则不运行、不造图，输出INPUT_MISSING.md。

### 1.4 9组矩阵与固定合同

参数组合：

| ε / m | 5 | 8 | 12 |
|---|---|---|---|
| 8mm | A1 | A2 | A3 |
| 12mm | B1 | B2 | B3 |
| 16mm | C1 | C2 | C3 |

只改变：
- DBSCAN邻域半径ε；
- 最少邻点数min_points。

其他处理条件必须完全固定：
- 原始点云SHA；
- BODY坐标、单位、标定revision；
- 同帧双臂关节状态、工具几何；
- ROI和table band；
- 体素采样；
- robot-owned filter；
- 前置radius/statistical filter；
- minimum_cluster_voxels；
- 支撑分解和碰撞膨胀；
- CPU线程数、Open3D版本、计时口径。

注意DBSCAN min_points与后续minimum_cluster_voxels是两个不同参数，不得混为一谈。

### 1.5 每组必须记录

- cluster count；
- noise points及比例；
- small-cluster removal；
- final clean points；
- 关键结构/已登记参考区域保留率（仅当原始材料有真实holdout/reference时才计算）；
- 主要簇的AABB尺寸、中心和点数；
- 支撑分解后的基元数；
- 观测点覆盖；
- 基元体积和（不是并集体积）；
- 清理/聚类/几何编译分阶段耗时；
- 每组真实同视角点云PNG；
- 完整输入SHA、代码commit、参数hash和日志。

计时先warm-up，再至少3次正式重复；报告median/P95，冷启动单独列出。不能挑最快一次。

### 1.6 参数选择规则

依次判断：
1. 关键结构是否保留；
2. 是否出现误合并/过分裂；
3. 噪点和小簇是否可控；
4. 观测覆盖和几何基元是否合理；
5. 耗时是否满足场景构建要求。

如果12mm/8点仍是合理配置，写“本次冻结点云上满足当前工况要求”，不写“唯一最优”。若结果不支持12/8，保留真实结果，提出候选配置，但不得改生产默认。

### 1.7 输出目录

~~~text
output/acceptance_v5/experiment/dbscan_grid/
  input_manifest.json
  upstream_pipeline.json
  grid_results.csv
  grid_results.json
  run_logs/
  pointcloud_panels/
  parameter_grid_contact_sheet.png
  selected_profile_rationale.md
  reproducibility_report.md
  INPUT_MISSING.md
~~~

INPUT_MISSING.md只有在实验无法执行时生成；不能用模拟点云、AI生成图片、PNG反推坐标或估计数字补齐。

---

## 2. 其他历史证据的复核门禁

### 2.1 P3.3负结果

来源：
- docs/reports/2026-09-22_P3_3_EXECUTION_HARDENING_REPORT.md；
- worklog/evidence/2026-09-22-p3-3-execution-hardening/sweep_v2/sweep_summary.json；
- visualization_final/p33_clearance_profile_sweep.png。

准确表述：
- 同一冻结AVOID A→B；
- 10/20/30/40mm四档；
- 每档3次重复；
- 12/12低于30mm工程门槛；
- 每档内轨迹哈希相同，说明可复现，不是12个独立随机样本；
- 早停，不是60次全方向实验；
- planning-only，无硬件运动，无执行包。

### 2.2 P3.4

来源：docs/reports/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION_REPORT.md。

必须分开：
- 体素5/7.5/10mm场景构建时间；
- formal solve CLEAR/AVOID；
- warm request wall CLEAR/AVOID；
- scan pipeline；
- A/B右臂commissioning speed profile。

不得将5.095s正式求解写成整条请求耗时。0.20rad/s仅限RIGHT_ARM_AB_DEMO_ONLY。AVOID fast roundtrip当时延期至P3.5。

### 2.3 P3.6/P3.7

P3.6 D1：
- 单次任意可见障碍物；
- fresh scan；
- 198基元；
- 8.09/103.40mm模型间隙；
- 3.08s求解；
- 11.41s实机执行；
- 0.882°最大跟踪；
- 无fault/abort。

P3.7：
- 五段运行时目标真实运动；
- 每段新点云SHA/SceneSnapshot/trajectory hash；
- 全部到位；
- 自由空间/绕箱，不是抓取或放置。

### 2.4 10/19 Golden

权威来源：
- docs/golden/2026-10-19/README.md；
- evidence/v17-place-recovery-completed/COMPLETED.md；
- REPORT.json。

必须同时保留：
- 原任务完成230mm连续抬升和1.53m转运；
- PLACE阶段故障；
- 持物几何修订；
- 从PLACE检查点接续完成下降、释放和底盘返回；
- recovery_not_uninterrupted_full_cycle=true；
- 125.34s只属于恢复事件跨度；
- 无arm stow；
- 无独立视觉认证最终精确落座；
- Demo限定持物override，不代表通用自动持物估计。

### 2.5 10/17失败数字

公开仓库的10/17审计文档包含CHAT_TOOL_EVIDENCE/INFERENCE，不等于原始run/event log。Codex必须在本机授权目录查找原始运行记录，核对run ID、事件顺序、文件SHA和计时定义。找不到则删除172.0s/257.3s等数字，不得引用摘要表作为原始证据。

### 2.6 P3.8E与P3.9

P3.8E：
- AUDIT_ONLY；
- native-ready→HOLD 400.25s；
- motion147.74s；
- non-motion252.52s；
- observation→HOLD1266.92s含人工/交互调试；
- 完整Tray→Groove周期未实测。

P3.9：
- additive implementation、frozen replay、fault injection；
- 18节点Scheme replay通过；
- FAST/FALLBACK、Observation V2、TaskRuntime、SchemeRunner、故障注入；
- 531 tests OK, skipped=1；
- 395s是工程模型估计，不是实测周期；
- task run/package physical execution仍锁定，未发生物理运动。

S21-PERF：
- CPU模块17.023→1.125s、15.176→0.830s、15.866→1.437s；
- 15.1×/18.3×/11.0×不能相加或外推整任务。

---

## 3. 每页证据矩阵

建立evidence_matrix.csv，每页至少一行：

slide_no, slide_title, customer_question, claim, dataset_id, run_id, source_report, source_json_or_log, source_code_commit, source_media, source_media_sha256, metric_definition, unit, validation_level, date, speaker_note, prohibited_inference, QA_status。

验证等级统一：
- FROZEN REPLAY；
- PLANNING ONLY；
- CPU BENCHMARK；
- SUPERVISED PHYSICAL EXECUTION；
- PHYSICAL RECOVERY；
- AUDIT ONLY；
- ESTIMATE。

每页都必须回答：
1. 这页展示的具体研发工作是什么？
2. 输入/实验条件是什么？
3. 修改/实现了什么？
4. 哪个真实工件证明做过？
5. 结果和选择依据是什么？
6. 哪些结论不能从本页推出？

---

## 4. PPT媒体和视觉质量门禁

### 4.1 原始媒体

- 解析PPTX OOXML relationship提取原始media；
- 记录原PPT、slide、shape、media rel、SHA、像素尺寸；
- 大PPT45–60页逐页contact sheet检查；
- 优先原图/视频，不使用低清整页截图；
- 旧/新对比必须同视角同尺度；
- 不同数据集的图片不得拼成同一A/B；
- AI示意图必须标“示意”，不得冒充真实实验。

### 4.2 母版与字体

唯一母版：20261030V0.95机械臂验收模板。

保留BBMG、页眉、红线、页脚、页面比例和原生组件。

字体：
- 中文主字体黑体；
- 英文/数字主字体Arial；
- 中文辅助宋体；
- 英文辅助Times New Roman；
- 公式独立处理字体、上下标、希腊字母和单位。
同时检查OOXML中的East Asian和Latin字体设置。

### 4.3 页面可读性

- 10页正文，不另加封面；
- 每页一个主结论；
- 主图和关键数据区清晰；
- 正文不低于16pt为目标，图注不低于12pt；
- 不把整张4:3源PPT截图拉伸进16:9；
- 表格/图表优先PowerPoint原生对象；
- 讲者备注包含完整技术解释和来源，不把关键过程全藏在备注。

---

## 5. 双轮渲染QA

第一轮：
- 检查母版继承、Logo、页眉、页脚、字体、比例；
- 检查图像分辨率、裁切、数据标签、图例；
- 检查文字溢出、遮挡、表格行高和公式；
- 检查页面主结论是否直观显示研发工作过程。

修订后第二轮：
- 重新渲染全部10页；
- 逐页核对数字、数据集ID、验证等级、来源；
- 核对10/10 CAMERA、9/21 CLEAR、10/21 GRASP、P3.3、P3.4、P3.6、P3.7、10/19 Golden、P3.8E和P3.9没有互相混用；
- 检查speaker notes与source ledger一致；
- 由PowerPoint实际打开/渲染为优先，无法使用时用LibreOffice并记录环境。

## 6. 禁止事项

- 编造DBSCAN九组实验；
- 将18/3、20/4、统计16/2.5前置滤波对照说成DBSCAN参数扫描；
- 将10/17聊天审计摘要中的数字当原始运行日志；
- 把P3.3负结果删掉或包装成成功；
- 把planning-only写成实机；
- 把模型gap写成物理测距；
- 把10/19恢复写成不中断无人值守全链；
- 把P3.9的395s模型估计写成实测；
- 把P3.8E的400.25s写成完整取放周期；
- 把CPU模块倍数宣传成整任务倍数；
- 把cuRobo的PRM/图搜索说成每次规划必然执行；
- 把独立world核验说成独立自碰撞认证；
- 为了视觉完整填充未执行实验；
- 修改生产代码、部署配置、安全门限或连接机器人/相机/AMR。

## 7. 最终交付文件

本机输出目录建议：

~~~text
output/acceptance_v5/
  金隅项目_点云场景重建与机械臂规划控制_研发工作量汇报_V5.pptx
  金隅项目_点云场景重建与机械臂规划控制_研发工作量汇报_V5.pdf
  slide-01.png ... slide-10.png
  contact_sheet.png
  speaker_notes.md
  evidence_matrix.csv
  slide_sources.csv
  media_manifest.csv
  metric_source_ledger.json
  technical_qa.md
  visual_qa.md
  customer_requirement_check.md
  missing_assets.md
  DBSCAN_INPUT_STATUS.md
  experiment/dbscan_grid/  # 仅真实执行后
~~~

原始PPT、视频、私有点云和用户私人绝对路径不提交public GitHub。Repo只提交任务书、可公开的摘要和经过审查的无敏感索引。
