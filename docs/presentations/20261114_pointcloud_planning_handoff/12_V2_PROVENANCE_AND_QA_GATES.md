# V2 证据与数值隔离表：每页必须知道“是哪一次、哪种验证”

本文件服务于Codex制作前和最终自审。Source: 原始repo报告+实测JSON+已有方法PPT；未执行任何新测试。路径均从仓库根目录开始。

## 1. 项目数据组（绝对不能互换）

| dataset_id | 输入/时间/性质 | 准许展示 | 不能推导 | 仓库原始入口 |
|---|---|---|---|---|
| S21-CLEAN | 9/21 点云净化固定输入（不是GRASP V3） | 输入self-filter前1,990,052→后1,895,624；workspace_non_table 625,288；5mm体素12,791；3组净化对照 | ε=12mm/m=8优于其他参数；首组总耗时可直接与热缓存组等价比较 | worklog/evidence/2026-09-21-p3-production-demo/avoid_final/cleanup/cleanup_benchmark.json |
| S21-ATTR | 9/21 residual_009 212点归因，planning-only | 212点距OBB≥30.01mm/距球≥20.52mm/旧膨胀AABB重叠27.40mm；拆桥接而不删真点 | 物理接触完全不存在；全部unknown为空闲；错误自体过滤已经修复所有问题 | worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/；docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md |
| S21-SUPPORT | 9/21观测箱体/泊位连通诊断（不是CLEAR 7→167那张帧） | 箱体独立约209×89×206mm，原大盒209×586×274mm | 全部箱体物理几何已完整可见 | docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md |
| S21-CLEAR7 | 9/21去箱CLEAR同帧净化点 | 7→167；体积和0.010413→0.004288m³ (−58.8%)；9,992/9,992 | 空闲空间+58.8%，箱体观测与本CLEAR同一帧 | worklog/evidence/2026-09-21-p3-1-residual-support/clear_ab/comparison/ |
| S21-CBASE | 9/21底盘重新就位后重新采集，CLEAR/AVOID/BLOCK均不同snapshot，规划级 | CLEAR 0.430276096m / AVOID 0.452617223m；箱体限制间隙+9.63mm，关节线性路径−21.78mm；BLOCK合成封闭无路径 | 真实运动已执行；BLOCK是实体箱；+9.63mm为物理实测安全净空 | docs/reports/2026-09-21_CURRENT_BASE_AB_TCP_EXPERIMENT.md；worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/ |
| S22-P32 | 9/22 P3.2 cuRobo-only A/B新的计划帧、假定A/B起点，非9/21的A/B | CLEAR约0.480m；AVOID约0.642/0.645m；AVOID 35.4/34.6mm规划间隙；重复一次9.3mm暴露解的变异 | 与S21-CBASE的430.3/452.6mm直接画在同表；9/22有实际ServoJ执行 | docs/reports/2026-09-22_P3_2_CUROBO_ONLY_AB_PLANNING_REPORT.md |
| S23-D1 | 9/23 P3.6任意障碍实机单次链路 | 198基元；起点/终点模型间隙8.09/103.40mm；路径216.36mm；solve3.08s；fresh scan8.08s；打包10.88s；执行11.41s；跟踪max 0.882°；到位0fault | P3.7 28.72mm的净空属于本次；这是多轮统计通过率 | docs/reports/2026-09-23_P3_6_SCENE_AWARE_MOTION_REPORT.md |
| S24-P37 | 9/24运行目标实机五段，fresh场景每段重新提交 | 五段均到位；绕真实箱right→left最小模型净空28.72mm，BODY最高z1.196m，规划11.31s，执行27.24s；反向27.74mm，规划10.99s执行25.64s | 它证明抓取/持物/放置任务完整；任意运动都能通用通过 | docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md |
| S28-P38E | 9/28真实Pick时间审计 | native-ready→HOLD 400.25s，其中147.74s运动、252.52s非运动；观测→HOLD 1266.92s包含人工/脚本调试间隙 | 全是视觉/规划耗时；已有完整循环时长统计 | docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md |
| S10-CAMERA | 10/10 CAMERA原图集同一帧 | 32→235，3,747/3,747点，−40.9%；OLD/NEW均cuRobo规划成功、独立world通过 | 这是S21-CLEAR7或者21日GRASP V3；旧失败/新成功 | docs/presentations/assets/20261028_rasc_curobo/{README.md,INPUT_INDEX.md,panels/geometry_ab/,panels/planning/} |
| S21-GRASP-V3 | 10/21归档GRASP源真实冻结重放 | 2,304,000→2,056,200→15,655→15,014→8,100；641自体点；19→405，8,100覆盖；膨胀体积和−68.6% | 与S10-CAMERA拼成同帧；严格几何A/B中NEW进入GPU并成功；已成功执行新实机抓放 | docs/presentations/assets/20261028_rasc_curobo/grasp_v3/README.md |
| S19-PLACE | 10/19历史PLACE故障及恢复 | 旧附着尺寸220×217×113mm；约100mm料盘、主体160×100mm+夹持后段20mm；后续检查点恢复完成 | 新尺寸有完整三维数值；不间断、无人介入、无失败一次成功 | 旧大PPT持物案例；docs/presentations/assets/20261028_rasc_curobo/panels/attachments/ |
| S21-PERF | 10/21历史CPU阶段优化，不是CUDA性能 | 稠密核验17.023→1.125s（15.1×）；接触几何15.176→0.830s（18.3×）；预抓取15.866→1.437s（11.0×） | 三个模块时间可相加、倍数可相乘、总任务加速11× | docs/presentations/assets/20261028_rasc_curobo/grasp_v3/runlogs/historical_performance.json |

## 2. 强制纠偏点

1. S21-CLEAN中半径18mm/3邻点与20mm/4邻点均输出12,744清洁点、13簇，核查53/53；统计滤波输出12,705、11簇。记录selected_default=radius_4_20mm不等于“后者全面最佳”。首组总时间1.187s因体素首次处理1.093s，而另两组体素为约0.017s，不能视为公平的计时收益。
2. S21-SUPPORT是带箱诊断、S21-CLEAR7是去箱量化；同页必须分别标注“诊断”与“定量A/B”。
3. S21-CBASE A/B是9/21底盘重定位后的全新3次capture；S22-P32用了另一组目标关节和规划合同。两者路径长度和规划时间不能合并画折线。
4. S10-CAMERA OLD/NEW GPU都成功；S21-GRASP-V3严格几何A/B两边端点均碰撞所以没有进入GPU，另一“真实GPU成功”是不同保留contact豁免的world。绝不能筛选其中有利半边拼成“OLD失败NEW成功”。
5. S21-GRASP-V3 camera是10/21归档数据；S10-CAMERA camera SHA a9031515...；S21-GRASP-V3 SHA 62d45bd3...；若图或数字不带数据组ID，直接退回重做。
6. 独立world FK距离核验不代表独立self-collision；源码src/ares_r/motion/independent_path_validation.py明确返回self_collision_independently_checked=false。不能写“独立双臂自碰认证”。
7. S23-D1的start gap 8.09mm与S24-P37的绕箱gap 28.72mm是不同试验。两者均是建模最小间隙，非实测物理距离保证。
8. S21-PERF的GPU规划时间、CPU密集核验和硬件运动不可混成同一个“规划用时”，因有重复读盘、进程与编排等待。
9. 录音中重试5次/100秒、间隙3→5cm是叙事例子；无对应runlog不准放在“实测结果”列。
10. 参考PPT中旧图标题或备注可能带错误数据集名称；以同源报告+runlog和冻结Git SHA为准。

## 3. 评价量的精确定义（PPT页脚只写短定义，备注写完整）

- 点云保留率：保留的同源观测点数/候选输入点数；先确认是否体素、ROI还是clean points的分母。
- 观测覆盖：净化观测点中落入至少一个碰撞基元表示的点数/净化观测总数。100%覆盖不等于遮挡区安全。
- 基元体积和：sum_k volume(AABB_k)，可能重叠，不等于union volume、实物体积或free-space收益。
- 误占据归因：独立比较原始点到机器人模型的距离与包围盒到机器人碰撞球的距离；不能把宽包络重叠当作实际碰撞证据。
- 模型间隙：给定URDF/FK/碰撞代理下的最小距离，不是物理夹爪到真实障碍的测距仪数值。
- TCP路径长：沿规划输出TCP样本的相邻欧氏距离求和，不是关节总角路程/时长。
- 模块加速：同测试定义下T_old/T_new；如输出不等价则不能称“等价加速”。
- 成功/通过：分别区分planning SUCCESS、independent world PASS、hard validation PASS、physical reached和full-cycle completed/recovered。

## 4. 每条新图/表必须具备的最小凭据

CSV列：slide_no, figure_id, source_path, source_kind, dataset_id, git_commit, run_id_or_scene_id, acquired_at, camera_sha, q0_sha_or_revision, parameter_hash, result_json, metric_definition, units, validation_level, is_replay, notes。

图号除非明确相同dataset_id和input SHA，不能在同一个对照中使用不同实验的数据。跨实验演进图必须标“不同工况/不同日期”，不能标为控制变量实验。

## 5. 未完成的补证矩阵

A. ε={8,12,16}mm × m={5,8,12}：目前未找到同源真实扫值；先验证输入源与其他参数固定，再运行并记录全部9单元。成功指标包括聚类留存、thin-feature/关键边界、覆盖、碰撞误判、分层输出与规划可行性；不能单指标挑最优。

B. 支撑层开关 × 网格细分开关 2×2：当前旧/新联合对照不能反推两个因素各自独立贡献。输出候选、观测覆盖、形状/体积、碰撞核验、规划、耗时，并分析失效/交互；未运行保持待测。

## 6. 证据审查门禁

G0 找到原始图/JSON及冻结代码；G1识别dataset并统一输入/设置；G2计算指标与原收据逐字段核对；G3标题和图注写可支持的结论；G4讲者备注写限制；G5渲染后检查图文不误导。任一失败，放入补证/附页，正文不能冒称已实测。

本包不包含新的现场或GPU测试，也没有原PPTX二进制验证。