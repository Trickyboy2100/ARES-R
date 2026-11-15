# V5 甲方验收汇报根本重设计与 Codex 执行令

> **状态：V5 是本目录唯一有效的制作依据，取代 V4 的页序和事实判断。**
> 分支：docs/acceptance-workload-draft-20261113
> 交付：10 页正文，不另加封面；沿用 20261030V0.95 机械臂验收模板。
> 范围：点云场景重建、cuRobo 机械臂规划适配/调试、ARES-R 任务执行与真实运行验证。

---

## 0. 重新定义这次交付：不是“技术介绍”，也不是“结果拼图”

甲方11月13日录音的核心要求不是再听一次DBSCAN、cuRobo的原理，也不是多放几张机器人成功截图，而是要看清楚**这一年实际做了哪些研发工作**：

1. 具体遇到什么工程问题；
2. 针对问题，实际实现/修改/配置了哪些模块；
3. 哪些参数做过真实对照，比较了什么；
4. 如何证明模块能够工作，验证到了哪一级；
5. 当前结论的适用范围与未完成边界是什么。

录音同时接受两种真实研发过程，不要求每个模块都编成“先失败、再成功”：

- **参数试验型**：固定输入，改变参数/配置，记录不同结果，说明选择依据。例如P3.3、P3.4、点云体素与前置滤波对照。
- **模块实现型**：从无到有完成输入、接口、算法处理、输出、测试和集成。例如JAKA模型与工具适配、运行时目标IK、轨迹种子、场景版本绑定、独立核验、ServoJ执行接口。

因此，本版采用“**模块研发链 + 真实参数实验 + 物理验证**”三种证据，而不是强迫每页都出现失败/成功A/B。

### 甲方要求的实际讲述结构

- 10月28日讨论提出：点云方法/结果约2页，cuRobo约4页，ARES-R约3页，总体约10页。
- 11月13日最新录音进一步明确：当前汇报重点是**点云场景重建**与**cuRobo规划/控制调试**；ARES-R作为工程承载与执行证据，不另做三页泛泛的软件架构介绍。
- 方法公式只保留能够讲清楚且确实服务于项目研发的内容。B样条、L-BFGS、PRM等成熟算法不能包装成项目原创算法。
- “编过程”应理解为把真实的模块开发、调试和验证过程整理出来，不得编造实验、运行次数、耗时、失败率或物理运动。

---

## 1. 对V4必须纠正的事实

以下内容在V4中存在错误或需要进一步核实，Codex不得沿用。

### 1.1 10月19日230mm连续抬升是真实物理阶段，不是规划预览

ARES-R的docs/golden/2026-10-19/README.md明确记录：Golden任务已完成取料、连续抬升230mm、转场、放置、释放、返回。底盘单程转运约1.53m。

真实故障发生在原始全链的PLACE阶段。修订持物碰撞几何后，从PLACE检查点接续完成预放置、下降、释放和返回。

- 原始取料和230mm抬升没有在恢复阶段重做。
- recovery REPORT明确标记 recovery_not_uninterrupted_full_cycle=true。
- 恢复阶段事件约125.34s，不是整个取放任务总时长。
- 不得写成“一键无故障、无人干预的完整自主循环”。
- 不得把10月21日Center/GRASP离线研究中“230mm目标端点IK可行”误当作10月19日物理抬升证据。

权威来源：
- docs/golden/2026-10-19/README.md
- docs/golden/2026-10-19/evidence/v17-place-recovery-completed/REPORT.json
- docs/golden/2026-10-19/evidence/v17-place-recovery-completed/COMPLETED.md
- 20261028大稿slide-42（物理阶段图片；照片未逐帧绑定日志时间）
- 金隅项目-周进度-20261023.pptx slide-08（附着模型修正）

### 1.2 10月17日三次Demo审计不能直接写入

V3证据优先级文档包含10月17日172.0s、257.3s等审计数字，但当前可读取的公开仓库中未找到对应原始报告/事件日志。

Codex必须在用户当前授权的本机工作目录和历史实验归档中查找：
- 原始run ID；
- 事件日志/报告；
- 失败阶段与执行阶段；
- FAST timeout、QUALITY OOM、IK失败、VERIFY_GRASP、人工干预的原始记录。

只有当原始文件、SHA、事件顺序和统计口径均可复核时，才可作为历史故障案例。找不到就**从PPT正文删除**，不得仅引用V3汇总表作为原始证据。

### 1.3 DBSCAN的ε与最少邻点数没有历史敏感性实验

现有S21-CLEAN实验比较的是前置密度滤波：
- 半径18mm/3邻点；
- 半径20mm/4邻点；
- 统计16邻域/2.5σ。

三组均固定DBSCAN半径12mm、最少8点。因此它不能证明12mm/8点是通过ε×m对照选出来的唯一最优参数。

正确表述：
- 12mm/8点是当前代码/历史实验使用的配置；
- 20mm/4邻点是已有前置滤波对照中采用的默认方案；
- 若要回答甲方对DBSCAN两个参数的追问，必须补真实离线参数矩阵，或者明确说明原始数据不可用、该项历史上没有做过。

### 1.4 cuRobo的PRM/图搜索不是所有生产路径都会执行

当前代码实际存在不同入口：
- solver_policy启用时，FAST单次路径调用solve_single_pass，底层为trajopt_solver.solve_cspace；
- 有种子轨迹时，可直接调用trajopt_solver.solve_cspace；
- 无solver_policy的常规路径才可能调用planner.plan_cspace，并由enable_graph_attempt决定是否启用图搜索尝试。

因此：
- 不得笼统写“每次规划失败都会PRM回退”；
- 必须核对P3.4和当前运行配置实际启用的入口；
- PRM/图搜索只能在确实启用的实验中展示；
- B样条/L-BFGS属于cuRobo底层成熟求解实现，不是本项目原创。

### 1.5 独立核验范围必须说清楚

src/ares_r/motion/independent_path_validation.py有独立的密集轨迹环境/工具几何核验，但源码字段self_collision_independently_checked=false。

允许表述：
- 独立核验环境障碍和工具几何；
- 对规划轨迹进行稠密采样；
- 核验场景、工具、姿态和路径约束。

禁止表述：
- “独立自碰撞认证全部通过”；
- “完成了完整双臂联合碰撞认证”。

### 1.6 不同数据集、不同验证等级不得混合

| 数据集/实验 | 正确含义 | 禁止混用 |
|---|---|---|
| S21-GRASP-V3，10/21 | 230万点级输入、冻结回放、19→405几何编译 | 严格几何A/B端点碰撞；不能说严格A/B GPU规划成功 |
| S21-CLEAN，9/21 | 5mm体素、三组前置滤波；DBSCAN固定12mm/8 | 不能说比较了DBSCAN ε/m |
| S21-SUPPORT / ATTR，9/21 | 箱体/泊位分离与212点局部包络归因 | 不等同S21-CLEAR同帧体积统计 |
| S21-CLEAR7，9/21 | 7→167、9,992/9,992、体积和减少58.8% | planning-only，不是实机规划成功 |
| 10/10 CAMERA | 32→235、3,747/3,747、体积和减少40.9%；OLD/NEW GPU规划及独立world均通过 | 不能与10/21 GRASP或9/21 CLEAR拼成同一实验 |
| 9/22 P3.3 | 4档激活距离×3次，12/12未过30mm门槛 | planning-only负结果，不是硬件运动 |
| 9/23 P3.6 D1 | 近障起点退出，真实右臂执行 | 不与P3.3拼成同场景前后成功率 |
| 9/24 P3.7 | 五段运行时目标真实自由空间运动 | 不是抓取/放置闭环 |
| 10/19 Golden | 230mm物理抬升、1.53m转运，PLACE故障后恢复 | 不是不中断、无人工介入的完整自主运行 |
| 9/28 P3.8E | AUDIT_ONLY关键路径审计 | 不是完整Tray→Groove周期实测 |

---

## 2. 资源审查结论与素材使用规则

### 2.1 必须使用的用户原件

| 文件 | 本次用途 |
|---|---|
| 生料和水泥的水分细度检验操作目标识别与控制算法研发内部验收20261030V0.95 - 机械臂.pptx | 唯一母版，保留BBMG、页眉红条、页脚、字体、分隔线和原生组件 |
| 20261028-水分细度目标识别与场景自适应规划控制.pptx（60页） | 主要原始素材库；重点提取slide11–19、27–32、37、40–42、45–60的单个媒体对象 |
| 20261028-水分细度目标识别与场景自适应规划控制-2.pptx（12页） | 技术流程/算法原理参考，提取可复用方法图和讲者备注；不要照搬为理论课 |
| 参考用 智能机器人实验员技术开发及应用-阶段汇报-朱翔2025.12.10 copy.pptx | 学习“数据/处理/模型/对照/结果”的过程表达，不使用其数据 |
| 25下半年考核汇报--生料和水泥的水分细度检验操作目标识别与控制算法研发（视觉）.pptx | 学习一页方法、一页实验结果、前后对照的组织方式，不使用其视觉训练数据 |
| 金隅项目-周进度-20260911.pptx | cuRobo→轨迹门禁→JAKA ServoJ早期集成证据 |
| 金隅项目-周进度-20260924.pptx | TCP、点云几何、A/B预览和五段实机运行素材 |
| 金隅项目-周进度-20261016.pptx、20261023.pptx、20261030.pptx | ARES-R、任务状态、附着模型、实机Demo及现场配置素材 |
| 当前失败的16页PPTX/PDF、speaker_notes.md、slide_sources.csv、metric_source_ledger.json、qa_report.md | 只用于继承已核实的数据和发现旧稿问题，不作为新稿母版 |

所有原PPT图片应从pptx媒体关系中提取单图原像素，不能把4:3整页截图强行拉伸为16:9。

### 2.2 ARES-R核心仓库资源

点云：
- src/ares_r/perception/residual_cloud.py
- src/ares_r/perception/robot_owned_filter.py
- src/ares_r/perception/support_decomposition.py
- docs/presentations/assets/20261028_rasc_curobo/
- docs/presentations/assets/20261028_rasc_curobo/grasp_v3/
- docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md

规划与执行：
- src/ares_r/motion/runtime_goal_ik.py
- src/ares_r/motion/constrained_manifold_seed.py
- src/ares_r/motion/latency_solver.py
- src/ares_r/motion/production_scene_worker.py
- src/ares_r/motion/independent_path_validation.py
- src/ares_r/motion/planner_joint_mapping.py
- src/ares_r/motion/native_execution_package.py
- scripts/jaka_right_demo.cpp
- tests/test_planner_joint_mapping.py

实验报告：
- docs/reports/2026-09-22_P3_3_EXECUTION_HARDENING_REPORT.md
- docs/reports/2026-09-23_P3_4_DEPLOYMENT_ACCELERATION_REPORT.md
- docs/reports/2026-09-23_P3_6_SCENE_AWARE_MOTION_REPORT.md
- docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md
- docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md
- docs/reports/2026-10-21_CENTER_GRASP_PLANNER_STUDY.md
- docs/golden/2026-10-19/

### 2.3 媒体提取优先级

从60页大稿优先提取：
- slide11–14：同源点云各阶段、机器人自体过滤、支撑层/结构分解；
- slide17–19：旧/新几何、覆盖与规划场景；
- slide27–32：求解配置、A/B规划、轨迹与执行；
- slide37：持物几何错误与修正；
- slide40–41：性能优化和回放；
- slide42：Golden真实取放照片；
- slide45–60：尾部独立素材库，必须全部建contact sheet后再挑图，不能漏掉。

仓库原图优先：
- 10/21 GRASP：docs/presentations/assets/20261028_rasc_curobo/grasp_v3/panels/rasc6/
- 几何A/B：docs/presentations/assets/20261028_rasc_curobo/panels/geometry_ab/
- 规划：docs/presentations/assets/20261028_rasc_curobo/panels/planning/
- 附着对象：docs/presentations/assets/20261028_rasc_curobo/panels/attachments/
- 性能：docs/presentations/assets/20261028_rasc_curobo/panels/performance/
- P3.3：worklog/evidence/2026-09-22-p3-3-execution-hardening/visualization_final/p33_clearance_profile_sweep.png
- 212点归因：worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png
- 10/10 CAMERA与10/21 GRASP必须用各自INPUT_INDEX和README核对数据ID。

---

## 3. 最终10页结构（严格按此制作）

总原则：**1页总览 + 2页点云 + 4页cuRobo + 3页ARES-R/实机与性能**。每页都有清晰研发行为；不做额外封面。

### 第1页：3.2 从真实点云场景到机械臂规划执行

目的：让评委一眼看懂项目研发范围和工作链，不是放一张抽象架构图。

画面：
- 现场工位大图；
- 两条工作包：A. 点云场景重建/碰撞几何编译；B. JAKA模型适配/cuRobo规划/轨迹核验/ServoJ执行；
- 研发过程简线：真实观测→场景编译→目标与工具约束→轨迹求解→独立核验→实机执行/恢复。

用语：
- cuRobo是成熟求解引擎；
- 项目研发集中于真实场景输入、机器人与工具约束、运行时目标、验证门禁、原生执行和故障恢复。

### 第2页：点云场景重建：从230万观测点到规划碰撞世界

主要数据：10/21 S21-GRASP-V3冻结回放。

真实处理链：
1. Camera→BODY，单位/标定/双臂采集状态对齐；
2. ROI工作区裁剪；
3. 依据同帧机器人状态与版本化几何进行robot-owned过滤；
4. 7.5mm体素；
5. 前置净化、DBSCAN；
6. 支撑层/凸起/结构分解与局部多基元；
7. 编译到cuRobo碰撞世界。

显示数据：
- 原始2,304,000；
- 有效2,056,200；
- ROI体素15,655；
- 移除641个模型可归属自体点；
- 外部观测15,014；
- 净化后8,100。
- 该GRASP V3编译结果为19→405个局部基元，8,100/8,100净化观测点覆盖，基元体积和减少68.6%；但严格几何A/B端点碰撞、未进入GPU，因此这里只能证明场景几何编译结果，不能说规划通过。

补充参数：
- 支撑高度分箱5mm；
- 峰值上下±10mm核查水平性/法向/连通性；
- 高出支撑25mm进入凸起候选；
- 局部网格40×40×30mm；邻近精化参数按源码和报告核对。

可视化：
- 使用GRASP V3六阶段真实原图，不要只放两张点云小图；
- 以同视角展示raw、robot-owned、support/protrusion、multi-primitive；
- 212个外部点的归因作为小型“问题诊断”图：点→OBB +30.01mm，点→规划球 +20.52mm，旧膨胀盒→球 −27.40mm。必须说明212个真实外部点未被删除，是局部包络被拆分。

### 第3页：参数选择与几何保真：真实对照而不是直接给默认值

分成两组独立实验卡，禁止混成同一数据集。

**A. 体素分辨率（9/23 P3.4）**
- 5mm：4.039s、243基元；
- 7.5mm：3.191s、171基元，保留已知箱体观测；
- 10mm：2.672s，但箱体观测破碎/丢失；
- 选择7.5mm是速度与几何保真的折中，不是绝对最优。

**B. 前置密度滤波（9/21 S21-CLEAN）**
- 18mm/3邻点：剔除14，净化12,744，13簇，参考53/53；
- 20mm/4邻点：剔除16，净化12,744，13簇，参考53/53；
- 统计16邻域/2.5σ：剔除79，净化12,705，11簇，参考53/53。
- DBSCAN半径12mm、最少8点在这组三方案中固定。
- 20mm/4邻点是已有默认配置；两组半径滤波的最终计数相同，不能说它显著优于18mm/3。

**C. DBSCAN ε×m补证（P0，条件执行）**
- 当前公开repo只有历史默认ε=12mm、m=8和前置滤波对照；没有ε×m敏感性实验。
- Codex先在用户授权的本机数据目录检查S21-CLEAN、S21-CBASE、Oct10 CAMERA、Oct21 GRASP的原始点云是否真实存在，检查SHA、点数、单位、BODY坐标、标定、ROI。
- 若有同源原始点云，冻结5mm voxel、20mm/4邻点、ROI、表面/桌面处理、最小簇12，执行ε={8,12,16}mm × m={5,8,12}共9组；保存每组原始JSON、CSV、独立PNG、同视角九宫格、失败记录和输入SHA。
- 评价簇数、噪点、薄壁/耳部参考区保留、支撑误合并、局部包络和耗时；不能只按簇数选优。
- 若原始点云不存在：不从截图恢复点云；不编造9组结果。页面只展示已有两类真实参数实验，并明确ε/m未做敏感性扫描。

**几何结果只选可复核的真实数据**
- 10/10 CAMERA：32→235基元，3,747/3,747覆盖，体积和减少40.9%，OLD/NEW GPU规划和独立world均通过。
- 9/21 CLEAR：7→167基元，9,992/9,992覆盖，体积和减少58.8%，planning-only。
- 10/21 GRASP V3：19→405、8,100/8,100、体积和减少68.6%，但严格几何A/B端点碰撞、未进入GPU；只能说明几何编译结果，不能说规划成功。
页面空间不足时，10/21结果放第2页，10/10和9/21放本页，清晰标记不同数据ID。

### 第4页：JAKA模型、工具和目标约束接入cuRobo

展示项目实际适配工作，而不是复述cuRobo产品说明。

必须说明：
- JAKA Mini2机器人模型/URDF与关节命名；
- 左右臂BODY→arm base→link6/flange→TCP变换；
- 夹爪实体碰撞几何与控制TCP分开；
- 双臂状态与非活动臂环境约束；
- 场景、工具、几何、起点状态版本绑定；
- 目标位姿进入运行时IK，而不是把TCP坐标直接发送给控制器。

可用的真实过程：
- 9/11早期两段式cuRobo→轨迹门禁→JAKA ServoJ集成：513轨迹点、80ms周期、最大跟踪约0.051°、最终最大关节误差约0.0014°；障碍为虚拟障碍，不能写成真实点云避障。
- 9/22 P3.2工具校核：装配粗测约145mm、工具网格远端约149mm、控制器TCP z=184.380mm。该阶段发现物理语义未关闭，因此只允许规划预览、禁止实机动作。用来说明为什么必须把控制TCP和碰撞实体边界分开。
- 9/23 P3.6和9/24 P3.7的实机运行证据放第8页，不在此提前写成已完成。

### 第5页：从运行时目标到可校验关节轨迹

用一张简洁工程流程图，配真实代码文件与测试证据：

当前RobotState/SceneSnapshot
→ RuntimeGoalIK：根据BODY目标、工具变换和当前关节状态求候选关节目标
→ 候选排序/关节限位
→ 可选LEVEL_YAW manifold seeds（只有实际请求启用时才写）
→ cuRobo trajectory optimization
→ 稠密插值、环境/工具核验、姿态/中央禁区核验
→ 按joint_names提取六轴轨迹
→ native trajectory package
→ JAKA ServoJ sender。

项目实际代码：
- runtime_goal_ik.py；
- constrained_manifold_seed.py；
- latency_solver.py；
- production_scene_worker.py；
- independent_path_validation.py；
- planner_joint_mapping.py；
- native_execution_package.py。

必须正确解释：
- manifold seeds是候选初值，不是直接执行的笛卡尔waypoint；
- FAST_SINGLE_PASS路径与普通plan_cspace路径不同；
- PRM/graph attempt是条件开关，不是每次规划必然执行；
- B样条/L-BFGS是cuRobo底层成熟优化器；
- 201×7输出按joint_names映射为201×6，是工程接口修复，不是整机成功率；
- independent validation没有独立自碰撞认证；
- production_scene_worker产出planning-only结果，不直接控制JAKA。

### 第6页：碰撞代价参数调试：4档×3次，12次真实对照

使用9/22 P3.3原始图和sweep_summary.json。

固定冻结AVOID场景、A/B、机器人几何和求解预算；只改变碰撞代价激活距离：
- 10mm；
- 20mm；
- 30mm；
- 40mm；
每档3次，共12次。

真实结果：
- 最小模型间隙：9.326 / 14.787 / 14.787 / 14.787mm；
- 路径长度：612 / 635 / 668 / 701mm；
- 平均规划耗时：21.2 / 21.3 / 16.0 / 21.3s；
- 12/12均未通过当时30mm验收门槛。

结论：
- collision activation distance是代价开始起作用的距离，不是最小净空硬保证；
- 单纯增大激活距离没有解决该冻结场景的净空门槛；
- 这是planning-only负结果，没有实机运动；
- 后续D1近障退出属于不同实验阶段和不同场景，不得伪装成同场景前后成功率。

### 第7页：求解器配置与GPU部署优化

使用9/23 P3.4真实记录，先核对每组参数字段，确认“8/8、4/4、4/2”分别代表什么，再制作图表。

可核对的历史记录：
- 8/8无CUDA Graph：约9.7–19.5s历史范围；
- 4/4无Graph：P50 12.00s；
- 4/2无Graph：P50 5.06s；
- 4/2有Graph：P50 5.04s，提升很小。
- 常驻planner、初始化/warmup/world update/formal solve/独立核验/request wall分开计时。

同页可以展示独立的RIGHT_ARM_AB_DEMO_ONLY速度阶梯：
- 0.12→0.20rad/s五档；
- B→A→B往返约9.49s；
- 跟踪峰值约0.77°/1.07°；
- 只适用于该右臂A/B Demo，不得外推为全任务速度。

不把GPU solve、请求wall、场景处理和实机运动时间相加成一个“规划耗时”。CUDA Graph若只带来5.06→5.04s的小差异，应如实说明不是主要收益。

### 第8页：从规划结果到实机：近障退出与运行时目标执行

两组独立实机证据：

**P3.6 D1（9/23）**
- 真实右臂起点，198个基元；
- 起点模型间隙8.09mm，终点103.40mm；
- TCP端点直线约200mm，规划路径216.36mm；
- 求解3.08s，实机执行11.41s；
- 最大关节跟踪误差0.882°；
- 到位无fault/abort。
- 说明固定30mm偏好间隙不应被当作起点硬门槛；独立核验要求不穿透、退出后间距不减并恢复。

**P3.7（9/24）**
- 五段运行时目标真实运动，每段重新观测、生成SceneSnapshot和trajectory hash；
- 五段全部到位，无abort/fault；
- 两个可见箱体穿越方向：右→左模型净空28.72mm，规划11.31s、执行27.24s；左→右27.74mm，规划10.99s、执行25.64s。
- 是自由空间运行时目标和障碍规避，不是抓取/放置任务。

画面以P3.6轨迹为主，P3.7五段回执做表格/时间线；明确标注实机执行。

### 第9页：跨工位取放：持物几何故障与检查点恢复

主案例：10/19 Golden。

原始物理阶段：
- 取料、连续抬升230mm、底盘单程转运约1.53m；
- 原PLACE阶段因持物碰撞包络错误受阻；
- 旧附着盒约220×217×113mm，包含料盘下方支撑；
- 实际料盘宽约100mm；
- 修订为主体160×100mm，保留20mm夹持后段；周边真实环境障碍保留；
- 旧计划失效，从PLACE检查点重新规划。

恢复记录：
- fresh scene/cuRobo候选刷新15.03s；
- current→preland 22.04s；
- 连续BODY Z−50mm下降26.85s；
- 松爪读回确认1.26s；
- detach0.10s；
- 底盘返回三段16.77/23.28/18.27s；
- recovery事件跨度约125.34s。

必须写清：
- 230mm抬升和1.53m转运属于原始物理任务；
- 125.34s属于PLACE故障后的恢复段，不是整个取放总时长；
- recovery不是不中断的全链无人值守成功；
- 没有独立视觉认证最终精确落座，没有完成force-controlled insertion/arm stow，不得写成通用自动持物估计已经解决。

### 第10页：性能瓶颈审计与工程交付边界

用两张分开的数据卡，不把不同实验相加。

**9/28 P3.8E审计（AUDIT_ONLY，无硬件运动）**
- native-ready→HOLD：400.25s；
- 其中运动147.74s；
- 非运动252.52s；
- observation→HOLD 1266.92s包含现场调试/人工交接；
- 完整Tray→Groove周期没有作为一个native run完成；
- 606s、395s等是估算模型，不是实测。

**10/21 CPU几何模块优化（离线/CPU benchmark）**
- 稠密环境核验17.023→1.125s，约15.1×；
- 接触几何查询15.176→0.830s，约18.3×；
- 预抓取准备15.866→1.437s，约11.0×；
- 三项模块定义不同且可能有依赖，不能相加，也不能外推为整任务提速。

本页收束：
- 已交付：点云场景编译、机器人/工具约束适配、cuRobo规划接口、独立环境/工具核验、ServoJ受监督执行、检查点恢复、运行日志与回归；
- 边界：完整任务周期、通用持物估计、独立自碰撞认证、双臂12DoF同步联合规划、专机业务协议/ROS集成，均按实际状态表述，不提前写完成。

---

## 4. 原始图像和图表的制作要求

1. 从60页大稿的媒体对象提取原始图片，不用整页截图。
2. 先生成所有媒体的contact sheet和manifest，记录source deck、slide、shape ID、media name、SHA256、尺寸、拟用页面、dataset ID。
3. 每张主图必须有足够分辨率，旧/新图采用同视角、同尺度、同ROI；如果原图角度不同，必须标“不同视角”，不能伪装同帧A/B。
4. 点云图使用清晰深色/高对比背景，支持/结构/凸起/未知对象颜色语义一致，三轴单位明确。
5. 轨迹图同时标起点、终点、障碍、活动臂、场景ID、轨迹ID和是否实机执行。
6. 规划级、冻结回放、CPU benchmark、实机执行、实机恢复、AUDIT_ONLY必须有明显不同的证据等级标签。
7. 2025/2026参考PPT只学习过程组织和版式，不复制其数据、训练曲线或视觉模型结果。
8. 禁止AI生成点云、碰撞模型或轨迹图冒充真实实验；示意图必须明确写“流程示意/几何示意”。

---

## 5. Codex执行顺序

### Phase 0：只读审计，禁止立即排版

- 同步并记录本分支HEAD、工作区状态、V5任务书SHA；
- 读取README、19_V4、所有历史实验报告、P3.3/P3.4/P3.6/P3.7/P3.8E、Golden README/COMPLETED；
- 读取上述所有源码和对应测试；
- 解析用户本机的原始PPT、PDF、视频、zip、周报和媒体对象；
- 对10/17日志做本地受控搜索，找不到就登记缺失；
- 对DBSCAN原始点云做存在性/hash/单位/坐标/ROI核查；
- 输出evidence_inventory.csv、media_manifest.csv、factual_conflicts.md、missing_assets.md。

不得修改生产代码、设备配置，不连接相机、机械臂、夹爪或AMR，不自动SSH，不下载新私有数据。

### Phase 1：只补甲方明确点名的P0实验

DBSCAN 9组矩阵只有在原始点云存在时才运行：
- 输入SHA和manifest固定；
- 同一BODY坐标、ROI、标定、5mm voxel、20mm/4邻点前置滤波；
- ε={8,12,16}mm × min_points={5,8,12}；
- 每组记录clean/noise/small cluster/kept cluster/holdout/box change/stage time/wall time；
- 保留全部成功、失败、报错、超时；
- 所有结果按新运行日期归档，绝不冒充历史实验。

如果原始点云不存在，输出INPUT_MISSING.md并继续制作10页PPT，不等待、不编造。

### Phase 2：原始媒体提取与页级素材映射

- 提取60页大稿全部媒体，特别是45–60页；
- 提取9/11、9/24、10/23周报视频/图片；
- 生成contact sheet供人工选择；
- 每页至少有一张主证据图和一个明确的研发行为；
- 生成slide_asset_map.csv，禁止同一图跨数据集错配。

### Phase 3：制作10页PPTX

- 使用20261030V0.95机械臂验收模板；
- 保留BBMG标识、页眉、红色线条、页脚和原字体系统；
- 正文可编辑，表格/图表尽量原生PowerPoint对象；
- 讲者备注包含详细技术解释、数据来源、实验条件、证据等级和限制；
- 不把完整实验过程只放备注，关键研发行为必须在页面上可见。

### Phase 4：逐页内容验收与视觉QA

每页逐项回答：
- 这页展示的具体研发任务是什么？
- 输入/实验条件是什么？
- 修改/实现了什么？
- 哪个原始工件证明做过？
- 结果和选择依据是什么？
- 哪些结论不能从本页推出？

检查：
- 数值与原始JSON/报告一致；
- 不同数据集不混用；
- planning-only不标实机；
- 物理恢复不标不中断全链；
- 页面不出现占位符、待测矩阵冒充结果；
- 图片不拉伸、不模糊、不遮挡；
- 字号、页眉、页脚、页码与母版一致；
- LibreOffice导出PDF后逐页渲染复查，再由PowerPoint解析器重开PPTX。

### Phase 5：交付

本机交付：
- 最终PPTX；
- PDF；
- 10页PNG及contact sheet；
- speaker_notes.md；
- slide_sources.csv；
- metric_source_ledger.json；
- media_manifest.csv；
- QA_report.md；
- 新增离线实验原始JSON/CSV/图件（如确实执行）；
- missing_assets.md和evidence_boundary.md。

公开repo只提交任务书、无敏感的索引和可公开摘要，不上传原始私有点云、商业现场图片、用户私人绝对路径或未经审查的视频。

---

## 6. 最终验收标准

**甲方能看见研发过程，而不是只看见结论。**

至少能清楚回答：
1. 点云如何从原始观测变成可规划的场景几何？
2. 体素、滤波、DBSCAN、支撑层和局部几何参数分别怎样处理，哪些有真实对照，哪些仍是当前配置？
3. 为什么单一大AABB会制造虚假占据，局部多基元如何保留观测覆盖？
4. 项目围绕JAKA和cuRobo实际开发了哪些适配模块，而不是简单调用？
5. 目标IK、轨迹种子、GPU求解、独立核验、关节映射和ServoJ之间如何衔接？
6. 规划参数怎样经过真实对照，哪些实验失败，失败说明了什么？
7. 哪些结果是规划预览，哪些是真实机械臂运动？
8. 10月19日PLACE故障怎样被定位、修订和接续恢复？
9. 系统时间究竟花在规划、运动、观测还是编排，哪些时间是实测，哪些只是估算？

**如果评委只看PPT正文、不听讲者备注，也应能看出具体研发动作、实验对照、修改对象和验证结果。**
