# V3 必须优先补齐的离线研发过程实验：执行与图件合同

原则：**不接任何实机、不自动SSH、不下载新私有相机数据**。仅使用本机已有且用户授权访问的静态BODY点云或原始相机快照＋冻结标定，将运行日期、代码版本、输入SHA、全部成功和失败记录落盘。不得通过画示意图伪装跑过实验。

## 0. 先找回输入，不能对着旧PPT截图做聚类

已从repo记录核实可尝试的历史静态指针（只有指针在Git，**原始大NPY不一定在公开仓库**）：

- S21-CLEAN: `worklog/evidence/2026-09-21-p3-production-demo/avoid_final/capture_pointer.json` → local artifacts `/home/yikun/ARES-R/logs/body_cloud/artifacts/20260921_110615_8576001f/manifest.json`、capture `20260921_110610_60662091`；
- S21-CBASE: `worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/capture_pointer.json` → `/home/yikun/ARES-R/logs/body_cloud/artifacts/20260921_161451_830b7857/manifest.json`；
- Oct10 CAMERA: `docs/presentations/assets/20261028_rasc_curobo/INPUT_INDEX.md` → CAMERA NPY SHA`a9031515...`与BODY NPZ SHA`ec20097e...`，公开仓库只有受审结果图和索引；
- Oct21 GRASP: `docs/presentations/assets/20261028_rasc_curobo/grasp_v3/README.md`、`MANIFEST.json`；浏览器可视化数据**不等于未经裁剪的原始点云**。

在Codex实际运行机器核对**path存在、hash、point_count、单位与BODY坐标、ROI、标定、动作状态**。如果找不到原始可用点云，就输出`INPUT_MISSING.md`及查过的受控目录，**禁止凭图恢复3D数据然后称现场重测**。不能强迫用户/远程服务器承担新设备操作。

## 1. DBSCAN ε×min_points（甲方明确点名，优先级P0）

源码已经有可用入口：`src/ares_r/perception/residual_cloud.py`中`CleanupProfile`和`clean_and_cluster(points_body_m, roi, profile, table_z_m, table_half_band_m, box_bounds)`，当前参数`cluster_tolerance_m=0.012`, `cluster_min_points=8`, `minimum_cluster_voxels=12`。前置default`radius_4_20mm`，体素`0.005m`。

### 冻结合同

- 选择一帧真实难例，尽可能包含薄壁、支撑、箱体或抓取耳部，固定points SHA、BODY/ROI、5mm voxel、radius20mm/min_neighbors4、min cluster12、table crop参数。
- ε=8/12/16mm × min_points=5/8/12，共9组，按源代码API分别执行；保留`eps12,min8`作为历史固定配置参考，**不是在历史上已经证明最优**。
- 每组：至少完成1次确定性输出重放，再做多次计时（首个初始化warmup单列、不用冷启动与warm混比）。如可稳定重复，报告P50与范围，含输入、体素、滤波、DBSCAN和总wall计时。
- 除`kept_clusters`、`cluster_noise_points`、`small_cluster_removed`、`clean_points`，还要检查参考ROI的`box_holdout`、薄壁/耳部可见结构、是否错误合并支撑和箱体；**不能只选簇数最多或最少作为“最好”**。

### 图必须清晰

每组将固定三维相机视角/坐标/scale/点大小画成9个**独立PNG**（不要只导出一张大拼图），色彩按簇ID/语义，可另外生成对齐9宫格。每小图角落标eps,minpts,簇数,保留点,耗时，不打印冗长终端。针对关键薄壁再提供2×2裁切放大，重点标“过分裂/误合并/局部结构保留”。颜色映射需要可复现，不同组合的随机簇ID不要强行当同一实例语义。

### 交付JSON/CSV schema

`input_sha256,source_manifest,code_commit,parameter_json,roi,voxel_m,pre_filter,cluster_min_points,eps_m,clean_points,cluster_noise_points,small_cluster_removed,kept_clusters,holdout_kept,holdout_total,box_change_mm,run_repeat,clock_kind,wall_s,stage_s,warning,error,visual_path`。

**筛选纪律**：只有真实结果构成非退化取舍，才能写“最终选12/8的实验依据”；若其他方案不明显更差，就写“已有12/8满足时间与结构条件，实验未显示唯一最优”，照样能体现真实研发分析。

## 2. 支撑层与细分解耦2×2（P1）

源码`src/ares_r/perception/support_decomposition.py`：
`DecompositionProfile(support_bin_m=.005,support_band_m=.010,support_min_points=120,support_min_span_m=.10,protrusion_min_height_m=.025,component_tolerance_m=.018,tile_xy_m=.04,slice_z_m=.03,inflation_m=.007,...)`；
`detect_support_levels`；`decompose_support_objects`；`refine_robot_adjacent_primitives`。
**现有源码没有原生可直接切换“仅支撑/仅细分”的独立flag**。必须在`scripts/analysis`下写**独立离线比较适配器**，不得修改生产系统默认/碰撞策略来凑表。

- G0=传统整簇AABB；
- G1=只按支持归属分组后每组一个AABB；
- G2=不按支撑语义，只有同输入局部网格；
- G3=原RASC支撑层+局部网格/微小结构/邻臂精化；
- 四组都固定相同的“有效净化点集”，并明确共有膨胀、点覆盖判据和同一机器人q0/tool/revision；**如果G1/G2不能公平定义，就写NO-COMPARABLE，不强行产出“两个因素独立贡献率”。**

每组输出：role-colored point layer、AABB整体图、相同问题ROI局部图、源点覆盖分子/分母、基元数、体积和及实际并集体积（若可靠可算）、点级误碰撞数量、CPU耗时。若可用真实planning-only snapshot，按同起终点/相同solver预算再重跑并严格记录SUCCESS、minimum gap、wall，不得从历史不同日的结果填入四格。

## 3. 规划参数与GPU计算的**已做实验优先复现/呈现**（P0，不必从零重新发明）

- P3.3真实`12/12`失败激活距离扫值已有`worklog/evidence/2026-09-22-p3-3-execution-hardening/sweep_v2/sweep_summary.json`和`visualization_final/p33_clearance_profile_sweep.png`，直接用原source制高可读图。解释optimizer activation不是保证净空，hard gate30mm全部失败。本次不再产生凭空“3cm变5cm就没碰”的故事。
- P3.4 seed/CUDA/常驻planner与体素5/7.5/10实测`docs/reports/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION_REPORT.md`，已经足够成为两页重要研发工作量主证据。真实图缺失时用**原生PPT条形图**根据报告数值重绘，完整写清统计口径，不需要现场重新跑GPU。
- P3.4实机速度阶梯0.12→0.20rad/s与跟踪回执：必须明确仅RIGHT_ARM_AB_DEMO_ONLY；历史报告中没有每档全部误差值时不能编五条完整误差曲线。
- 10/21 GPU profile数据`docs/reports/2026-10-21_CENTER_GRASP_PLANNER_STUDY.md`是**不同冻结场景**，与P3.4可展示“后续独立优化记录”但不可排成同一场景前/后同表。

## 4. 图件清晰度和物理信息保证

所有针对点云的图：固定相机矩阵、三轴单位m、1:1几何尺度、同一ROI、显示原始点数与输出，正文字体≥14pt，不能依赖白底0.5px浅灰点。不同语义：SUPPORT青、PROTRUSION橙、STRUCTURE蓝、UNKNOWN紫；颜色仅用于当前画图，不改变代码中的角色枚举。

所有轨迹：同时画起点、终点、主要障碍、活动臂/另一臂（如可用）、轨迹标签、是否执行；规划级结果显著标“未上机”。**只有现场日志匹配的录像**可标“实机”。

## 5. 误导性补证红线

- ε/m没有9格来源，一格也不能填写AI猜测值；
- 9/21、10/10、10/21三个RASC数据集绝不混成同一帧；
- 9/22 P3.3全部拒绝不是9/23 D1或P3.7的“旧值 vs 新值”严格同工况；
- 9/28预测模型606→395并非实际完成；
- 10/17故障与10/19恢复必须保留故障阶段和人工干预信息；
- 原始点云在公网Git未找到，不表示原私有实验被删除；离线获取失败就准确报告缺口。
