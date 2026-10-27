# Codex 工作任务书｜ARES-R 真实点云—场景编译—避障—控制—技能系统的演示证据制作
## 2026-10-28 · OFFLINE UBUNTU · RASC Presentation Evidence Sprint

> **这是需要执行的研发素材生产任务，不是让你重写PPT、空做方案、列答辩问答，亦不是让你只画一张大拼图。**  
> 目标：读取 ARES-R 已有真实实验数据和真实代码，独立复现、测量和专业可视化关键研发成果，交付**可逐张插入PowerPoint的子图 / 对照图 / 曲线 / 代码出处 / 复现脚本**，并把合适且获准公开的产物提交到本分支。离线机器上能做到的尽可能做完；无法做的写清数据缺口和需要现场录制的具体分镜，不要把任务反推给项目负责人。  
> **技术名称仅保留一个核心方法名：RASC — Reachability-Aware Scene Compilation，机械臂可达空间约束下的自适应场景几何编译。** 其他部分使用清楚的中文名：“工业任务多约束规划”“并行候选求解与独立轨迹验证”“任务参数化与状态绑定执行”“分层实时性优化”。不使用上轮建议的GEM-6D、BCR、SSPD、MP-CWM、TCPMO、DAM、PVE/VTE、HLO等缩写；请勿创造更多凑数名称。

**工作分支**：`codex/rasc-presentation-evidence-20261028`，从已经核查的 ARES-R `codex/golden-offline-workbench-20261020` 提交 `6866106cee971b08d8abb92523d2cc2dc0e204ca` 建立。  
**作用域**：离线CPU/GPU、既有真实点云/状态/规划日志、现有代码、只读PPT/视频素材、纯离线可视化/复现实验。**严禁连接或驱动真实机器人、相机、底盘、夹爪；不改生产安全策略/运动限幅，不登录.32或其他现场IP。** 无需为了得到满意画面远程采集新数据。  
**不允许覆写**：现有Golden完成证据、用户目录、其他成员未提交代码、已提交旧报告、原始二进制/点云/视频。

---

# 0. 立即开始的动作、研发自主权和完成标准

1. 在离线Ubuntu先做`git status`、分支/commit、GPU/CPU和本地原始数据盘点。最好新建**独立worktree**，不修改现有现场/研发工作树。先检查本任务书与本地实际代码SHA，更新`INPUT_INDEX.md`。如果本地没有该分支，执行安全的fetch/switch或新worktree，不强制覆盖现有工作。所有命令默认只读；检查每个旧脚本是否可能调用硬件，禁止运行有副作用的入口。
2. 可充分利用Codex自己的探索与判断：不限于我列的构图方式；允许寻找更加能说明方法价值的真实场景、重新设计图面、写新的离线工具、做A/B实验、排查不一致、迭代多轮，直到得到有说服力且真实的素材。**不过只能更换画面/方法，不得更换事实、修改安全边界以制造“明显成功”，也不得把计划/历史/Mock冒充本轮实测。**
3. 以“能让工业技术评审看到工作量”为标准：每个重点题材必须含 **工程问题/根因—我们写的处理或适配—算法/几何原理—真实对照或实验—量化结果—适用边界**。每个算法分量必须能追溯到文件/类/函数与配置参数，不能仅靠几个术语。
4. 默认首先完成**P0四组**：①同一帧真实点云RASC六阶段图；②同一场景单AABB vs 多基元+同起终点规划对照；③规划/实机反馈曲线与来源审计；④分层实时性优化及代码位置的可解释对照。其后完成任务状态/持物归属、WebUI/技能图、已有视频提取、候选规划与新对象素材。
5. 必须进行至少一轮“初版→专业性/真实性自审→改版”迭代；图一眼看不出差异时先检查**有没有真正有意义的效应**，更换有源数据支持的案例或重新表达细节，不调整不同图的相机视角/轴范围来制造假的显著差异。
6. 不需要生成最终PPT。本任务只生产可复用子元素及可选整页预排版。不要修改北京工业大学PPT模板。后续PPT统一使用原模板的背景、Logo、中文黑体/英文Arial、原字号体系。

## 产物与证据状态编码（每张图都必须标识）
- `PHYSICAL_MEASURED`：真实机器人/相机事件与原始日志的测量，不等于离线重放；
- `FROZEN_REPLAY`：真实已采集场景离线重新运行实际算法得到的结果（注明CPU/GPU/软件版本）；
- `HISTORICAL_EXTRACT`：从已有可信历史报告/图片直接提取，**不叫本轮重测**；
- `OFFLINE_SYNTHETIC`：合成场景/对照/模拟数据，适用于演示原理但不可冒充现场；
- `SCHEMATIC`：代码导出的原理结构图，箭头/子模块来自真实源码但不是实测；
- `BLOCKED_MISSING_DATA`：缺日志/原始点云/完整场景/正反例，严禁填数或凭空绘图。
图注/manifest应准确披露上述等级；存在多个等级的拼图要逐panel标注。

---

# 1. 仓库内已有的重要入口（先验证，不要只读main）

| 目标 | 推荐代码/记录入口 | 现场事实/注意事项 |
|---|---|---|
| 真实点云与场景编译 | `scripts/build_p3_production_scene.py`, `scripts/process_static_pointcloud.py`, `src/ares_r/perception/obstacle_world.py`, `residual_cloud.py`, `robot_owned_filter.py`, `support_decomposition.py`, `src/ares_r/world/scene_compiler.py` | 部分脚本名虽含production但入口需要检查是否只读离线输入；不要触发采集 |
| 原大框错误与细分场景 | `docs/reports/2026-09-21_P3_PRODUCTION_POINTCLOUD_CUROBO_REPORT.md`; `2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md` | 真实“连通结构造成空腔误封闭”与处理变更的主要证据 |
| 9/21同起终点A/B | `worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/`，`comparison/comparison.json`，`current_base_clear/` | CLEAR/AVOID不同现场scan；若比较旧几何vs新几何必须从**同一scan**重构，不可混成一组 |
| 旧scan源线索 | `current_base_avoid/capture_pointer.json` | 指向`logs/body_cloud/artifacts/20260921_161451_830b7857/manifest.json`及capture manifest；Git中的pointer不等于Ubuntu必然拥有raw PLY/NPZ |
| 9/22规划对照 | `docs/reports/2026-09-22_P3_2_CUROBO_ONLY_AB_PLANNING_REPORT.md`，`scripts/compare_p31_ab_plans.py` | 规划预览是`PLANNING_ONLY`，不得写成实机走过 |
| 9/24真机绕障和不同目标 | `docs/reports/2026-09-24_P3_7_ARBITRARY_TARGET_SCENE_AWARE_MOTION_REPORT.md` | 有实机多个目标与箱体绕行，标清run/scene/q和ServoJ记录 |
| 多约束目标/规划 | `src/ares_r/motion/scene_aware_motion.py`, `scene_aware_planner.py`, `latency_solver.py`, `production_scene_worker.py`, `independent_path_validation.py`, `native_execution_package.py` | cuRobo原生GPU多种子/IK/轨迹优化与项目工程约束构建必须归属分明 |
| 平滑控制/实机反馈 | `src/ares_r/motion/{bounded_retiming,execution_feedback,feedback_audit,trajectory}.py`；`docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md` | 要从真实target + readback中画跟踪，而不是对单条规划q(t)伪造“实测” |
| 持物与完整Demo | `src/ares_r/manipulation/{physical_payload,attached_world,grasp_verification,roundtrip_demo,roundtrip_job,observation_transaction_v2}.py`; `docs/golden/2026-10-19/README.md` | 2026-10-19真实取放各物理阶段完成，包含PLACE故障及修正后接续；不是未经干预一镜到底 |
| 技能库/任务编排 | `src/ares_r/skills/`, `src/ares_r/webui/{operations.html,workbench.html,server.py}`, `docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md` | 编排/并行准备多数为代码+离线回放验证，不能用真实WebUI截图冒称实际成功交付 |
| 规划加速报告 | `docs/reports/2026-10-21_CENTER_GRASP_PLANNER_STUDY.md`, `docs/golden/2026-10-19/UBUNTU_REPLAY_ORDER.md` | 真实冻结输入优化；预抓取/观测/完整任务耗时相互区分 |
| 9/28全链耗时审计 | `docs/reports/2026-09-28_P3_8E_FULL_CYCLE_THROUGHPUT_AUDIT_REPORT.md` | native-ready→HOLD400.25s中147.74s是机械臂运动，252.52s是其他等待/准备；全任务606/395/255/205s均为当时估算 |
| 现场数据完整性 | `docs/golden/2026-10-19/{SITE_COLLECTION.md,private-data-manifest.json,prepared-artifact-gaps.json}` | 原始现场内容可能缺失；从目录与hash审查，不要从指针编造文件 |

如有旧周报PPT或项目素材盘，请Codex**只读**搜索指定素材目录并建立`EXISTING_MEDIA_INDEX.md`；可以从PPT的`ppt/media/*`解出已嵌入图片/视频作为溯源引用，但需审核许可，不要未经授权把原现场视频直接提交到public Git。

---

# 2. P0-A｜RASC“同一真实点云六阶段”：必须做出可复现的专业算法图

**目标：用一份真实传感源点云，逐层展示真实代码所做的几何运算；不是把一幅点云图手工上色六次。**

### 选取数据
- 优先搜索有完整manifest+SHA、相机点云、BODY变换、两臂capture关节、tool revision、自体过滤几何、scene报告的9/21代表帧；优先`CLEAR`或`AVOID`中完整度高、包含支撑/空腔的扫描。
- 必须记录输入源SHA、capture timestamp/坐标系、数据点数、机器人q、外参版本和代码commit。可以选9/21历史“7框 vs167基元”对应源数据，但要证明它与六阶段输入一致；若无完整数据，继续找其他已经存在的场景。
- 若只有`pointcloud.ply`而没有同帧关节/外参：只能完成真实点云几何分解的子集，**禁止猜关节状态做“已验证自体剔除”**；必要时以`PARTIAL`输出，注明阶段3缺状态。

### 六个分别独立导出的panel
1. `01_raw_cloud` — 原始真实点云（原有观察范围与数据缺口）；旁边简短展示专机、底盘/臂、料盘/夹具位置。无RGB不要伪造彩色。
2. `02_roi` — 操作区域/机械臂相关工作区ROI；标注实际边界、裁剪前后数量、采样分辨率。注意现有代码的ROI并不等于完整解析IK得到的精确可达集，严禁伪称已计算逐点可达性场。
3. `03_robot_owned_filter` — 基于同帧q及机器人几何、夹爪/底盘已被归属部分进行自体剔除；展示被移除点与保留外部点，注明`filter completeness`和是否有未建模机器人部件；不许把邻近真实障碍当噪声删除。
4. `04_support_decomposition` — 使用源代码实际的支撑层识别、法向/高度/空间连通分组，分别着色SUPPORT、PROTRUDING、STRUCTURE、UNKNOWN_OBSERVED，图注明确这些是几何分层而不是神经网络识别；不以“RANSAC”命名不曾运行RANSAC的阶段。
5. `05_multi_primitive` — 实际从分层点云输出多基元，重点给出镂空/L形/U形结构局部放大，让观众看到被原单框占据的自由空间；标注几何膨胀与总基元数。
6. `06_curobo_world` — 使用`SceneCompiler`原代码将同源SceneSnapshot从BODY编译到cuRobo目标手臂frame，叠加工具/非活动臂/底盘及碰撞基元；不是只复制P5换个颜色。若只有离线geometry、缺有效snapshot/TF，不许称完整cuRobo正式场景。

### 数据统计必须严谨
- 六阶段面板下均有`N_in`、`N_out`、`T_compute_ms`；第4、5阶段属于**分组/表示变换**不是丢点，`N_out`取“保留并有归属的观测点数”，另给`K_primitives`；第6阶段输入输出不是点云缩小，沿用点证据数，另给`K_curobo_obstacles`及坐标编译耗时；未直接处理点的字段明确写`N/A (geometry compile)`，禁止填伪造的数量变化。
- 计时范围不包括加载原始文件/画图/截图；对CPU阶段做冷/热多次记录，至少提供中位数、P95、环境CPU、OMP线程/分辨率/配置；原`camera capture`耗时可以从历史manifest引用，不能在Ubuntu离线“重新测相机采集”。
- 六张图固定同一个虚拟相机视角、相同BODY轴标尺、比例/上下限，保留可比较的场景主体；导出至少`TOP / FRONT或REAR / ISOMETRIC`三种视角下可选择的一整套panel，其中**首页推荐ISOMETRIC六格**。
- 所有点/基元来自可复现的数据。不要用虚构的3D模型填补扫描空洞；可以用淡灰已知CAD/机器人骨架作参考，但图例必须注明`MODEL REFERENCE`，不能写成OBSERVED。
- 导出`panels/rasc6/{01..06}_*.png`与可行的SVG、可选`composites/RASC_six_stages_16x9.png`、`tables/rasc_stage_counts.csv`、`runlogs/rasc_stage_metrics.json`、`scripts`复现命令。

**必审点：** 逐阶段处理代码实际调用，参数、点数、变换方向、drop/keep类别在脚本+表中对应；如果N显著变化，需解释到底是下采样、ROI、自体过滤、还是去噪。

---

# 3. P0-B｜几何A/B：单AABB“误封闭” vs RASC多基元“保留空隙”，连接cuRobo规划

**目标：把“点云做了更多处理”提升为“改变了实际规划可行空间”的强对照证据。**

### B1. 同一帧物理几何表示对照（必须）
- 相同`raw cloud SHA + calibration revision + BODY frame + robot state`，保留同一目标、原始观测、相同膨胀逻辑（需要说明不同role的合规差异）、同样机器人碰撞几何；
- 旧方法`connected cluster→single inflated AABB`，新方法`support/object decomposition→multi-primitive`，另可加`direct voxel/ESDF`或局部原始点occupancy参考（仅在有可执行代码、结果可复核时）。
- 输出至少3张分离子图：`old_boxes.png`、`new_primitives.png`、`error_occupied_space_slice.png`。第三张必须能明显看到旧框虚假占据了哪一块**有证据的空隙**，不要用隐藏原始点的单独立体模型渲染。
- 指标：原始点数、观测保留点归属率、基元数、几何体积（如为盒体积之和注明`sum of volumes`；若求并集，明确union计算实现与精度）、建模计算时间、粗碰撞查询时间、模型/点云一致性以及空隙/安全裕量。
- 历史报告的一帧：`7→167`基元、累计几何体积`0.010413→0.004288m³`、`9992/9992`点归属；属于**候选核对锚点**。重跑若不一致，先比较源数据/配置/版本，不可悄悄写成这些数。

### B2. 同一起终点 + 同一安全距离的规划对照（高优先级；如GPU/原始场景可用）
- 使用**同一个抓取机/关节起点q0、目标T_goal/qgoal、机器人+夹爪模型、工具偏移、轨迹动态限幅、场景来源与planner版本/seed预算**。只切换OLD vs NEW碰撞几何表示，严禁顺带修改膨胀、安全裕量、目标姿态、速度/关节限位。
- 先检查`start/goal`本身可行/是否处于场景碰撞；明确规划的`SUCCESS + independent validator PASS`与`planner says success but validation FAIL`是不同结果。
- 记录`OLD fail / NEW success`是**要寻找的真实有力案例，不是必须制造的结果**。先检查9/21或历史FAIL几何根因中是否能合法复现；如果所有匹配场景二者均成功，可比较规划路径、净空、假占据、时间；若均失败则保留失败，提供结构原因。
- 如当前Ubuntu无真实CUDA/cuRobo或缺完整request，退化为`same-frame geometric feasibility / independent collision diagnostic`，同时交付`NEEDS_INPUT`，不要用手工画绕障曲线冒充cuRobo结果。
- 另外一组真实场景CLEAR/AVOID/BLOCK用于论证现场改变引起的规划行为，这个组需要各自真实scan，不是“同一源帧几何A/B”。必须将两个实验系列分别编号，不能混用。
- 输出独立面板`planning_old.{png,svg}`、`planning_new.{png,svg}`、`route_overlay.{png,svg}`、`gap_vs_path.csv/png`、`failure_reason.csv`；附`compare_planning.json`、源代码SHA和安全约束快照。
- 若存在真实物理执行录像，单独链接/抽帧并标注PHYSICAL；9/21的preview绝不加“实机验证”。

### B3. 画面质量
- 两个面板相同世界轴、同相机、同尺度；目标和机器人当前姿态有明显标记；真实点云淡灰，OLD与NEW几何易区分；“误封闭空腔”局部同时保留原始点作为参考。规划与障碍可半透明但不遮掩碰撞。
- 图不要只为“看起来厉害”而堆200个盒子；提供`zoom region`+ legend：观测、已知CAD、机器人、被抓物、规划障碍、路径以及目标各是什么。

---

# 4. P0-C｜机器人多约束规划、cuRobo候选及ServoJ反馈：必须可区分算法和真实执行

**领导需要听懂的核心：这不是“JAKA从A到B”。** 使用cuRobo GPU多种子IK/轨迹优化（上游能力），ARES-R自研工作是把**当前两臂关节/软限位、实际link6/TCP、左臂/底盘/夹爪/附着几何、真实点云障碍、水平/夹爪抓取姿态、不同任务阶段动态限幅**转成规划请求、筛选并独立验证轨迹，然后使用JAKA受保护ServoJ执行。

### C1. 两张独立的算法结构图
- `curobo_native_principle.svg/png`：以学术方式展示cuRobo的IK候选、trajectory seeds、GPU并行优化、碰撞代价、平滑代价、终点误差与轨迹选择；明确标出“cuRobo原生”，不得称自主发明并行优化内核。
- `aresr_constraint_integration.svg/png`：显示BODY/双臂TF、姿态策略(`LEVEL_YAW_FREE/LEVEL_YAW_TARGET`等)、软限位、真实障碍+持物、任务阶段、独立密集验证、JAKA原生控制回读；标记“ARES-R构造、适配、验证”。
- 公式用标准LaTeX并附`math/*.tex`源；例如解释性`min_q E_goal + E_collision + E_smooth + E_task`及`q_min≤q≤q_max, |qdot|≤v_max`。要说明哪些是cuRobo内部优化、哪些是我们在请求生成或后置验证实现的外部约束，不要把示意总目标误称真实CUDA kernel源码。

### C2. 多候选“有结果才画结果”
- 优先寻找已有GPU运行日志中`IK candidates`、不同末端yaw、轨迹seeds、失败原因、有效轨迹等。若数据完整，在**同一冻结场景与相同安全核验**下可离线跑小矩阵，例如`1/2/4 seeds`、`25/50 iters`、FAST/QUALITY，记录planner solve/whole request/P50/P95、成功率和不同终端姿态。
- 必须注意不同种子数改变计算预算；区分`GPU内部多种子并行`、`ARES-R候选配置`、`5700||5000/next-stage服务流水线并发`。不能将这些统称为“自研并行优化”。
- 输出`candidate_paths.png`、`candidate_result_matrix.svg/png`、`constraint_failures.svg/png`；不能获取每个轨迹种子中间轨迹时只画原理箭头，标SCHEMATIC，不要生成假的候选轨迹。

### C3. 真实ServoJ目标vs回读曲线（特别重视）
- 找到**同一次真实执行**的时间戳、`q_commanded(t)`、`q_measured(t)`、ServoJ控制周期、阶段、控制器错误/停止读回；校核units rad/deg、每关节索引、绝对/单调时钟及延迟。不能将正逆运动学预测替代真实JAKA读取值。
- 至少导出这些**独立面板**：`joint_target_vs_actual_Jn.png`、`tracking_error_6joints.png`、`joint_velocity_acceleration.png`；如果jerk需数值求导，则注明采样周期、差分方式/滤波与噪声不确定性；如采样过稀，则不要声称jerk级安全平滑。
- 选具体运动段（`pregrasp/contact/lift/real obstacle crossing`）应有实际日志。建议一个最快但真实正常段+一个速度较慢的受限段，以展示“轨迹约束对运动的影响”；两例的条件、时长和关节曲线不能当同一个案例。
- 记录真实`max/RMS/P95 tracking error`、峰值速度/加速度（来源可靠才写）、到位确认、执行时间。不要人为剪掉超调或报错区间。
- 输出审计`SERVO_TRACE_AUDIT.md`：有无真正成对命令与读回？能否时间对齐？哪个关节差异较明显？有没有实际改善对照？**如果仅画出一条几乎重合的曲线不代表“优化明显”；如果两条确实不明显，诚实给出高精度跟踪的误差放大图，或另选有真实差异的不同profile对照。**
- 若无完整feedback，仅提供真实日志的已有最大误差和独立规划轨迹图，明确`ACTUAL_FEEDBACK_TRACE_MISSING`；绝对不得模拟“actual q”。

---

# 5. P1-D｜持物与场景归属更新：给出可迁移任务的物理依据

- 从真实状态/代码画`object_ownership_transition.svg`：`WORLD→HOLD_CANDIDATE→GRASP_CONFIRMED/ATTACHED→RELEASE_VERIFIED→WORLD`；每一步的触发条件和证据绑定`ObservationEpoch/SceneSnapshot`，注意闭爪≠抓稳确认。
- 三张分图`before_grasp_scene.png`、`attached_during_transfer.png`、`after_release_scene.png`：分别标可见工作环境、目标、机器人碰撞部件、附着物体及其相对TCP；如果没有三阶段真实几何，就用审计过的代码契约作SCHEMATIC并提供状态日志，禁止合成宣称现场截图。
- 强制做一次**真实10/19故障对照**：旧历史持物包络与实际工件100mm宽尺寸、新修正主段160×100mm+后部20mm夹持区对照；单独导出`payload_wrong_footprint.png`、`payload_corrected.png`、`place_clearance_case.png`，带物体尺寸/坐标框架与原始日志引用。
- 不要把`physical_payload.demo_exposed_payload_override`的现场一次特定几何修正称作通用自动识别已完成；若有新的自动对象尺寸抽取算法再另做证明。

---

# 6. P1-E｜ARES-R框架：技能—任务—世界状态—设备控制解耦，以及WebUI/Task Studio

### E1. 不画一张“所有模块堆成塔”就结束
请从真实代码导出**四套独立的小框图**，可自行组合为一页三栏但必须保留子图：
1. `skills_hierarchy.svg`：Detect / BuildScene / Plan / Approach / Grasp / Verify / Lift / Transport / Place / Recover，区分原子技能、复合技能和任务阶段；哪些接口已完成、哪些依赖真实现场commissioning；
2. `scene_state_contract.svg`：SceneSnapshot、T_BODY_CAMERA、两臂joint state、target、tool/TCP revision、attached object、base pose revision、run_id/epoch，显示谁消费、变化会让什么计划失效；
3. `adapters_and_devices.svg`：SkillRuntime/TaskRunner → canonical Services → Epic/EpicEye/cuRobo/JAKA/Gripper/AMR，不要画不存在的ROS Driver或未实现设备功能；
4. `scene_and_execution_lifecycle.svg`：Observe→Compile→Plan→Independent Validate→Native Execute→Readback→Commit/Invalidate→Next Stage、Stop/Recovery分支（具体到运行时真的有的动作）。

### E2. 真WebUI画面
- 优先使用Codex所在Ubuntu的**离线、不可连接设备的静态fixture或隔离mock服务**启动Task Studio/WebUI；安全审计`server.py`/配置与网络前缀，禁止后台自动发现并连接现场设备；否则直接提取经许可的历史真实网页截图/已有PPT内视频帧。
- 产出**若干独立原图**而不是一张长截图：`webui_scene3d.png`、`webui_skill_palette.png`、`webui_scheme_builder.png`、`webui_task_state.png`、`webui_stop_fault_log.png`、`webui_object_envelope_inspector.png`（如果本地真实版本确实有该界面）。将窗口/版本/fixture状态/真实设备连接状态印在图注，不得用Photoshop绘制不存在的按钮/状态。
- **特殊素材**：用户指出过去某份周进度PPT含“3D点云及碰撞包络框拖拽演示”。Codex检查本地合法可读PPT素材目录，搜索`ppt/media`、视频/截图索引，提取原视频以及3–5张高清关键帧；记录原PPT路径、media条目、SHA和版权/授权。若未挂载，仅写`LOCAL_PPT_WITH_DRAGGING_DEMO_NOT_FOUND`，并指定所需PPT文件，不凭空创建模拟“真实拖拽录像”。
- 可额外创建`webui_showcase_storyboard.md`：8～12秒控制台操作序列，从加载快照→修改对象/泊位参数→场景更新→规划→轨迹预览→结果/日志（真实界面所能提供的步骤）。

### E3. 证明“可泛化”而不是复读架构
绘制小表`task_parameterization_matrix.csv/svg`，列“旧料盘抓取/新筛网/新专机泊位”的需要变更字段：对象模板、抓取参考位姿、站位/相机profile、持物模型、技能输入和安全约束；区别已实测/已有配置/仍待现场测试。不要预填泛化成功率。
---

# 7. P0-F｜分层实时性优化：必须逐项说明“原来为什么慢、修改了什么、保持什么不变”

这部分不能只写一个“速度提升15倍”。Codex需查源码、测试、历史报告，生成**问题/优化机制/代码位置/可比输入/前后耗时/正确性一致性**的证据表。特别调查：

- **稠密碰撞独立校验**：从高开销Python/SciPy原路径转向受验证的`NATIVE_CPU_V1`等实现，保持相同431采样、最小间距对象、是否触碰判决一致；10/21文档约`17.023→1.125s`。核验`src/ares_r/motion/{independent_path_validation,cpu_distance}.py`，找到真正对照路径，避免误称为cuRobo GPU求解提升。
- **接触几何提取**：`observed_contact_geometry.py`中`cKDTree`加速局部候选查询，再做相同inclusive边界过滤；文档约`15.176→0.830s`；校验输出artifact/revision是否等价而不只比较耗时。
- **预抓取计算准备**：文档`15.866→1.437s`；定位哪些依赖步骤受上述优化影响，避免将组成环节的多次速度收益重复计算。
- **点云处理/存储**：voxel/ROI、N×N SVD风险、缓存/源SHA、读取/序列化/几何拆分时间，若有码可复现实验提供变化与内存峰值。
- **cuRobo规划服务**：Planner初始化/预热/scene update/IK seeds/trajectory seeds/FAST QUALITY迭代/GPU CUDA Graph/密集核验分时；热请求P50约`3.561s`只属于10/21指定冻结派生55mm case，不能说全场景实时达到该延迟。
- **任务编排**：9/28记录`native-ready→HOLD400.25s`，其中实测运动`147.74s`、非运动`252.52s`，包括操作等待、进程启动、阻塞式设备调用、证据写盘等。`5700||5000`并发、持久worker、异步证据、next-stage预准备是已有架构/模拟验证与建议；必须明确`IMPLEMENTED / REPLAY_ONLY / MEASURED_SITE / PROPOSED`。

### 必须独立交付图
1. `latency_module_before_after.png/svg`：三项同条件模块改进，原秒数和新秒数、对应技术点；不是简单"15×"大字。
2. `latency_critical_path_waterfall.png/svg`：按已有可信历史任务run构建scan→scene→plan→validate→package→native motion→wait，分开相机、CPU、GPU、设备、编排/unknown；并行时用DAG max-path，不重复叠加。
3. `fast_vs_quality_profiles.png/svg`：只有有可核对配置与冻结性能记录才绘制真实P50/P95和成功率；FAST配置和QUALITY的实验预算不同需注明。
4. `pipeline_architecture.svg`：多线程并发部分标现有代码级支持/离线测试/未来实机部署，不把计划当真实运行时节省。
5. `optimization_code_map.md`：真实函数/行范围、commit/配置、输入输出哈希、指标出处，回答“你们到底优化什么”。

**优先进行离线再测**（相同硬件/相同输入，跑前/后代码），不能再测则将历史结果清楚标`HISTORICAL_EXTRACT`并只做可追溯视觉再加工。每幅图给源报告与实验条件。**关键质量门槛**：不能为了让优化对比“更明显”裁掉失败例、调整时钟定义、使用相同数据的部分片段替代全段、降低安全裕量/碰撞保护或改变显卡负载条件却不披露。

---

# 8. P1-G｜其它能让PPT更专业的素材，能离线做就做

1. **RASC几何复杂度–规划时间Pareto图**：同一scene不同tile尺寸/膨胀参数对应`K`、点覆盖率、误占据量、CPU时间、GPU planner latency；在安全门限内比较，不能把unsafe candidate计成优良Pareto。
2. **完整硬约束清单示意**：双臂link/夹爪、机身、桌面、专机外壳、附件、水平持物、关节软限位、起终点IK、速度加速度/独立验证，在现场设备图片或建模图上逐一定位；另产独立`robot_constraints_labels.svg`和`planner_problem_formula.tex`。
3. **场景版本与重新规划图**：把`SceneSnapshot ID`、pointcloud SHA、calibration/tool/attached revision与计划hash生命周期画成时间线；旧场景被撤销必须显示明确的作废或Replan触发条件。
4. **真实完整取放任务filmstrip**：如已拥有获准使用的现场视频，拆为独立静帧`01 detect...08 return`及简易16:9 overview，标明现场曾在PLACE发生故障、修正后接续。视频来源及合法使用许可独立记录。无原视频则按`onsite_only`记录。
5. **新对象与新专机**：盘、筛网及专机模板的真实截图/掩码/6D位姿匹配若存在则整理成子图；如没有完整新任务物理视频，不能自己把模板匹配加旧动作视频拼作“泛化成功”。
6. **如果WebUI页面无法安全运行**：只画真实代码生成的模块/任务图，并提供后续现场画面分镜；不能“伪造”一个完成的控制页面。

---

# 9. 视觉产物纪律：专业、强对照、但不造假

- **所有子图独立保存**；每张至少1920px长边，建议PNG 2560×1440或更高清；流程图、算法图、二维曲线优先SVG+PNG双格式；三维几何大规模点云用高分辨率PNG；组合`composites/`仅作为帮助后续排PPT的可选品。
- 导出无水印、保留坐标轴/单位/图例；用中性学术绘图风格、白或透明底适配旧模板，不要大量装饰色块。中文文本优先黑体、英文Arial，若离线Ubuntu无对应字体使用系统可用替代并记录`font_fallback`，不得捆绑/分享字体文件。
- 实物对照用相同相机位姿、世界范围、轴比例、目标和安全裕量；明确图例区分`observed measured cloud`、`modeled geometry`、`hypothetical preview`和`physically executed`。禁止通过不同坐标上下限、截取局部失败段等故意制造视觉夸大。
- **标题必须是有含义的结论**（例如“多基元建模保持镂空结构并减少虚假占据”），副标题写实验条件；一张图不能同时使用另一个实验的数值。
- 图中数值、文件名、注释、公式统一能被`ASSET_MANIFEST.json`追溯；为每个panel独立建索引、数据hash、脚本名、旧新方法配置、运行时长、采样范围、证明级别。
- **专业可读性验收**：输出总览缩略图，将图缩至一张标准16:9 PPT页的约1/3宽后检查轴标题、图例、数值是否还能读；重叠、裁切、灰度对比不足需自动检查并改版。
- **“效果明显”验收**：若希望展示旧几何无法规划/新几何成功，必须有同条件真实规划结果；如果结果差异很小，提供局部几何剖面和定量指标而非增强路径偏移。跟踪曲线若重叠，应提供真实单位的误差子图而非制造波形。

---

# 10. 推荐目录结构 / 可交付结果

在本分支新建代码`tools/presentation_evidence/`和输出根`docs/presentations/assets/20261028_rasc_curobo/`。小体积、允许公开的PNG/SVG/CSV/JSON/MD可以提交到Git；真实大量现场点云、未授权图像/视频、控制器IP、敏感工艺、设备账号、绝对用户名路径只能在离线本地`runs/presentation_evidence_20261028/`保留，并在`INPUT_INDEX.md`以可匿名化摘要/校验哈希引用。

建议落盘形态：

```text
docs/presentations/assets/20261028_rasc_curobo/
  README.md                   # 一眼看到已完成、缺口与复现指令
  STATUS.md                   # 各工作包DONE/PARTIAL/BLOCKED及证据等级
  INPUT_INDEX.md              # 真实点云、run、config、SHA、来源审计（不泄漏路径）
  ASSET_MANIFEST.json         # 每一个panel的来源、类型、参数、证明级别
  panels/
    rasc6/                   # 01到06，每张独立PNG，可选SVG
    geometry_ab/             # OLD/NEW/剖面
    planning/                # 候选轨迹/同点A/B/失败原因
    servo/                   # 目标与真实、速度/加速度、误差
    attachments/             # 抓前/持物/释放和旧包络修正
    performance/             # 模块耗时/瀑布/配置矩阵
    runtime/                 # Skill DAG/SceneSnapshot/Provider/WebUI
  composites/                # 可选16:9合集，但绝不能替代panels
  math/                      # LaTeX公式片段及变量定义
  tables/                    # CSV、Markdown、参数/效果表
  reports/
    RASC_REPRODUCIBILITY.md
    AABB_VS_RASC_AB_EXPERIMENT.md
    SERVO_TRACE_AUDIT.md
    LATENCY_METHOD_AUDIT.md
    UI_AND_SKILL_EVIDENCE.md
    REVIEW_AND_LIMITATIONS.md
    ONSITE_ONLY_BACKLOG.md
  contact_sheet.png          # 生成“素材总览”用于快速审
tools/presentation_evidence/
  README.md                  # 最小环境/重放、单组重跑命令
  ...                       # 实际独立可重复运行的Python工具或配置
```

不要凭空创建空文件充数；`BLOCKED`的图位仅在manifest里标缺口即可。`RAW_POINTCLOUD`应保持受控、只读、绝不提交public仓库。图与代码更新按逻辑分批提交，禁止`git add .`将大文件和其它成员文件误收进来。

**`ASSET_MANIFEST.json`至少字段**：
`asset_id`、`path`、`source_kind`、`experiment_id`、`source_artifact_sha256`、`scene_snapshot_id`（如有）、`robot_state_hash`（如有）、`tool_calibration_revision`（如有）、`repo_commit`、`generation_script`、`generation_params`、`input_count`、`output_count`、`runtime_ms`、`safety_constraints_digest`（如有）、`interpretation_limit`、`public_release_approved`。不存在的值填null并解释，绝不造假。

---

# 11. 逐组验收（Codex必须自我审计，不只是说PASS）

| 组 | 最低可接受交付 | 高质量目标 |
|---|---|---|
| 六阶段真实点云 | 同一个真实scan，≥3阶段实际代码运行可复现；任何缺失明示 | 六阶段均完整、有真实N和T、相同相机坐标视图、高清子图及合集 |
| AABB→多基元 | 同源几何真正做了OLD/NEW两套，点保留+基元数可复核 | 含空腔剖面、相同A/B请求、真实OLD fail/NEW pass或明确真实改善 |
| cuRobo规划 | 原理图准确，至少一个真实规划请求/轨迹证据 | 同场景种子/姿态配置对照+真实失败原因与独立安全检查 |
| ServoJ曲线 | 如有真实成对反馈：真实目标/实测与误差，真实来源时间；无则BLOCKED | 六关节多指标、至少两个真实工况、真实动态对照 |
| ARES-R架构 | 四个独立代码来源图/状态机，至少已有WebUI合法截图 | 真实TaskStudio现场/离线录屏片段与状态绑定示范 |
| 运行时间优化 | 历史三项数字来源透明，优化机制和代码位置有据 | 相同冻结输入再跑旧新实现，输出CPU/GPU分层耗时与任务关键路径 |
| 持物归属 | 真实或源码状态变迁+10/19旧/新模型 | 三种任务状态独立空间画面、故障恢复证明及尺寸差异 |
| 素材总包 | 各panel可独立用、产物索引、无私密文件 | 可以由本仓库脚本一键再生、QA报告、界面截图、视频关键帧 |

最后必须写`reports/REVIEW_AND_LIMITATIONS.md`，列：
1. 已经有证据支撑、可对甲方汇报的成果；
2. 仅软件实现或离线GPU重放、不能称实机成果的内容；
3. 现有实验没有验证或结论不显著的内容；
4. 哪些仅有历史图无法完整重跑，缺的究竟是哪个文件/SHA；
5. 有没有“看起来明显但实际不成立”的对照并予以撤回；
6. 素材还能怎样再优化一轮。
把真实负结果保留，不让所有报告都只剩SUCCESS。

---

# 12. 最终交付给项目负责人的内容（先提供成果，最后才列真正现场缺口）

提交本分支后，在`README.md`首屏给以下结论：
- **可直接放PPT的素材清单**：按视觉RASC、几何A/B、cuRobo算法、ServoJ、任务框架、性能优化分组，每项独立文件与简短“最适合讲什么”；
- **推荐6～10张优先使用的图**：每张1句可防守技术结论及最重要限制；不是PPT页码；
- **验证情况**：具体运行了哪些脚本、原始SHA和测试条件，是否有CPU/GPU重放，能否重跑，是否与旧报告一致；
- **尚无或无法离线产生**：现场固定底盘避障演示、筛网/新专机跨对象任务、完整实机执行录像等，单独放`ONSITE_ONLY_BACKLOG.md`，给出可拍摄分镜和采集字段，但**不以这些缺失阻塞已有离线素材产出**。

**完成后把分支、提交SHA和交付路径给项目负责人。无需先征求每张图的排版确认，自主完成几轮有证据的闭环。**

---

# 13. 最简启动说明（供离线Codex）

用户交给你的任务：**基于本仓库真实算法和已有历史真实数据，制作可复现、可拆分、画面专业、对比明显但真实的技术汇报素材。** 本任务不涉及硬件和现场联网，先从已存在的真实点云与日志起步。

建议操作顺序：
1. 审计branch、工作树、真实点云/manifest与运行环境；
2. 确认一组有配套数据的真实点云与几何对照；
3. 快速交付RASC六阶段的第一版独立子图和数据表；
4. 同源OLD/NEW RASC几何对照并检验规划是否有合法差异；
5. 同步从真实执行日志建立ServoJ曲线、性能方法与历史数字审计；
6. 生成带出处的cuRobo/约束图、SceneSnapshot/Skill/WebUI小图；
7. 对比、校验、改版，提交干净的素材/脚本/manifest/README。
8. 真实数据不齐全时，不要停止全部工作：给缺失组标BLOCKED继续完成其余；只在最后提最小必要缺口。

**注意最后一遍科学诚信核对：**这批素材将用于正式甲方预验收汇报，漂亮但不可追溯的图一律不交付；正确呈现历史失败、复杂实验条件和安全边界，比“PPT全是成功”更能体现项目专业性。
