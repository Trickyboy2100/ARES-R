# V5 逐页文稿与版式合同：10页正文，不另加封面

**执行依据：** 20_V5_CUSTOMER_WORKLOAD_REDESIGN_AND_CODEX_ORDER.md。  
**重要：** 本文件是该任务书的逐页文稿补充，不改变V5的10页结构、事实修正和边界。Codex负责视觉设计、精细排版、母版继承、图表绘制和渲染QA。

本文件中的上屏文稿可为版面适当精简，但每页的研发动作、关键数据、验证等级和禁止推断必须保留。

---

# 第1页｜3.2 从真实点云场景到机械臂规划执行

**本页要让甲方理解：** 这一年在本模块实际做了哪两类研发工作，工作链如何闭合。

**建议上屏文稿：**

> 面向料盘、秤台、专机入口及双臂作业空间，围绕两项关键工作开展研发：  
> **① 点云场景重建与碰撞几何编译；② JAKA机械臂规划适配、轨迹核验与实机控制。**  
>   
> 形成从真实三维观测、场景建模、目标与工具约束、GPU规划、独立核验到受监督执行的工程链路。

**版式建议：**

- 使用真实工位全景作为主图，优先取20261028大PPT或9/24周报的原始媒体。
- 图片上以少量标注指出料盘、秤台、专机入口、双臂和障碍区域。
- 右侧/下方两块研发工作包：
  - A：点云空间转换、ROI/体素、自体过滤、支撑/凸起分解、多基元场景编译；
  - B：机器人/工具/TCP、运行时目标IK、cuRobo求解、独立核验、ServoJ执行与恢复。
- 底部一条横向工程链：真实观测 → RASC场景编译 → cuRobo规划 → 轨迹核验 → JAKA执行/反馈。

**讲者备注：**

本章只汇报点云场景重建与机械臂规划控制。相机本体选型、曝光、识别模板和视觉模型训练由其他工作包负责，不在此重复。cuRobo是成熟GPU求解引擎；本项目研发集中在现场输入、机器人/工具/场景约束、目标和关节接口、验证、原生执行及故障恢复。后续各页会区分冻结回放、规划级验证、受监督实机和恢复执行。

**素材：** 20261028大PPT slide02/04/42；9/24周报现场图；模板母版。

**禁止：** 不放通用AI机器人图；不将视觉算法团队的工作算作本模块研发；不声称项目从零开发cuRobo。

---

# 第2页｜点云场景重建：从230万观测点到规划碰撞世界

**本页要让甲方理解：** 点云不是直接扔给规划器，而是完成了坐标、状态、过滤、结构分解和几何编译。

**建议上屏文稿：**

> 针对原始点云数据量大、坐标不统一、机器人本体点混入环境以及支撑/凸起结构连通等问题，建立真实观测到规划碰撞世界的几何编译流程。  
>   
> 10月21日GRASP冻结观测：  
> **2,304,000原始点 → 2,056,200有效点 → 15,655 ROI体素点 → 15,014外部观测点 → 8,100净化点。**  
>   
> 在同帧双臂状态和工具几何约束下，移除641个可确认的机器人自体点；外部未知观测继续保留。

**建议数据区：**

| 处理阶段 | 点数 |
|---|---:|
| CAMERA原始点云 | 2,304,000 |
| BODY有效点 | 2,056,200 |
| ROI体素点 | 15,655 |
| 自体归属移除 | 641 |
| 外部观测点 | 15,014 |
| 后续净化点 | 8,100 |

**几何结果区：**

- 19个单AABB → 405个局部多基元；
- 8,100/8,100净化观测点覆盖；
- 膨胀基元体积和减少68.6%；
- 416个cuRobo编译障碍（若展示，明确它是编译输出，不是405的同一计数口径）。

**小型问题诊断图：212点误占据归因**

- 212个外部点到最近P2 OBB距离至少30.01mm；
- 到cuRobo规划球距离至少20.52mm；
- 旧膨胀AABB与规划球重叠27.40mm。
- 结论：外部点保留，拆分抽象包络跨越空隙造成的假占据。

**版式建议：**

- 左侧大图：GRASP V3六阶段中的raw、robot-owned、support decomposition、multi-primitive四张同源图，建议2×2或横向流程，图像不能缩得过小。
- 右侧上部：点数漏斗/原生表格。
- 右侧下部：19→405和覆盖数据。
- 212点归因作为底部小型诊断卡，图上明确标OBB、planner sphere、old AABB三种几何。

**讲者备注：**

该组数据属于S21-GRASP-V3，10/21 right_pick冻结回放；不是9/21 S21-CLEAN，也不是10/10 CAMERA。CAMERA单位mm，BODY单位m；BODY数据已由固定外参转换，不得重复转换。机器人自体过滤只移除模型可归属的点，不证明所有未建模部件均被覆盖。8,100点全部被多基元覆盖，不等于遮挡空间或未观测空间已被证明安全。19→405只证明几何表示更细，不代表严格规划A/B通过：该GRASP严格几何A/B的起终点均碰撞，没有进入GPU求解。体积和不是并集体积，也不是自由空间增加68.6%。

**素材：**
- repo：docs/presentations/assets/20261028_rasc_curobo/grasp_v3/panels/rasc6/
- repo：grasp_v3/geometry_ab/、details/、metrics/
- repo：worklog/evidence/2026-09-21-p3-1-residual-support/attribution/result_v2/robot_adjacent_overlay.png（单独标S21-ATTR，不与GRASP同帧拼接）

**禁止：** 不将212点归因和GRASP V3的19→405说成同一次采集；不说严格GRASP几何A/B规划成功；不把68.6%写成自由空间增加。

---

# 第3页｜参数选择与几何保真：体素分辨率和前置净化的真实对照

**本页要让甲方理解：** 参数不是直接写一个默认值，而是做过真实比较；哪些参数有对照，哪些仍只是固定配置。

**建议上屏文稿：**

> 围绕点云空间分辨率和离群点净化，开展不同参数组合的处理对照，综合考虑处理时间、几何结构保留和规划障碍表达规模。  
>   
> **体素分辨率：** 7.5mm在P3.4测试工况下兼顾处理时间和箱体观测保留；10mm虽更快，但已出现箱体观测碎裂/丢失。  
> **前置净化：** 比较半径滤波和统计滤波，在53/53参考点均保留的条件下，形成当前默认净化配置。

**实验A：P3.4体素分辨率**

| 体素 | 场景构建耗时 | 基元数 | 结构表现 |
|---|---:|---:|---|
| 5mm | 4.039s | 243 | 细节较多、耗时较长 |
| 7.5mm | 3.191s | 171 | 保留已知箱体观测 |
| 10mm | 2.672s | 未报告 | 箱体观测碎裂/丢失，拒绝 |

**实验B：S21-CLEAN前置滤波**

| 方案 | 滤波剔除 | 净化点 | 簇数 | 参考点保留 |
|---|---:|---:|---:|---:|
| 半径18mm/3邻点 | 14 | 12,744 | 13 | 53/53 |
| 半径20mm/4邻点 | 16 | 12,744 | 13 | 53/53 |
| 统计16邻域/2.5σ | 79 | 12,705 | 11 | 53/53 |

**DBSCAN参数边界：**

> 历史净化对照中DBSCAN固定ε=12mm、最少8点；现有历史证据没有证明这两个参数经过完整敏感性矩阵筛选。

如果Codex成功执行新9组离线实验，可在该页右下角增加九宫格和真实结果；否则不得出现模拟九宫格或“最优参数”表述。

**版式建议：**

- 上半页：5/7.5/10mm体素对照，左边同工况箱体局部图，右边原生耗时柱图与基元数表。
- 下半页：三种前置滤波表格，配一张同源点云局部对照。
- DBSCAN状态放一个明确的说明条：已验证/待补证。
- 不把不同实验数据混成同一张柱图；分别标P3.4与S21-CLEAN。

**讲者备注：**

P3.4的4.039/3.191/2.672秒是采集后的场景构建时间，不是扫描到执行全链路。10mm的基元数量在报告中未给出，不可推算。S21-CLEAN三种滤波方案都保留53/53参考点，18/3和20/4净化后点数与簇数相同，不能说20/4全面显著优于18/3。首组冷启动/体素首次执行时间不能与后两组热缓存时间比较。DBSCAN的12mm/8点是固定配置，不是历史ε×m扫描结果。

**素材：** P3.4报告与summary.json；S21-CLEAN cleanup_benchmark.json；大PPT中的点云/箱体原始媒体；repo RASC六阶段图。

---

# 第4页｜cuRobo工业适配：把JAKA机器人、工具和现场场景转成完整规划请求

**本页要让甲方理解：** 项目做的不只是调用一个Python接口，而是完成真实机器人、工具、坐标和场景约束适配。

**建议上屏文稿：**

> 为使GPU规划结果能够对应真实JAKA机械臂，完成机器人模型、左右臂状态、工具/TCP、BODY目标和现场碰撞世界的统一适配。  
>   
> 规划请求绑定当前关节状态、活动臂、非活动臂/机身环境几何、工具模型、目标姿态、SceneSnapshot及其版本；规划轨迹经验证后才进入JAKA原生执行接口。

**主要工程接口：**

1. JAKA Mini2 URDF、关节顺序和限位；
2. BODY → arm base → link6/flange → TCP变换；
3. 夹爪实体碰撞几何与控制器TCP语义分开；
4. 真实当前q0、目标位姿与姿态约束；
5. 点云/多基元 → SceneSnapshot → cuRobo collision world；
6. scene/tool/geometry revision、trajectory hash和过期状态绑定。

**真实工具/TCP核对：**

- 现场装配粗测约145mm；
- 工具网格远端约149mm；
- 控制器TCP z=184.380mm。

这三者是不同语义测量，不得相加。9/22 P3.2发现物理语义尚未关闭，因此该阶段仅规划预览，禁止实机动作。

**版式建议：**

- 左侧：真实JAKA夹爪、料盘耳部、控制器TCP设置的高清原图；
- 中间：BODY→arm base→link6→TCP变换链；
- 右侧：Planning Request结构卡片（q0、goal、robot/tool、scene、constraints、hash）；
- 底部小条：9/22物理语义未关闭→后续完成独立适配与门禁。

**讲者备注：**

代码主要涉及runtime_goal_ik.py、production_scene_worker.py、runtime_goal_ik、robot collision/URDF/YAML和SceneSnapshot。cuRobo只负责求解，不自动知道现场工具、底盘、目标、采集时状态和执行许可。项目研发在把这些真实信息正确编译到规划请求，并让规划输出与执行输入保持一致。145/149/184.380mm分别是现场粗测、网格远端和控制器TCP z，不应直接补成碰撞柱。

**素材：** 9/22 P3.2报告；9/24周报slide04/05；大PPT slide26、夹爪和工具原始媒体；ARES URDF/YAML。

---

# 第5页｜从运行时目标到可执行关节轨迹：IK、候选分支、核验与关节映射

**本页要让甲方理解：** 规划请求如何从任务目标转为可被JAKA控制器消费的六轴轨迹，项目实际实现了哪些接口和测试。

**建议上屏文稿：**

> 针对现场目标位置、姿态和当前关节状态，建立运行时目标IK与候选关节解处理；随后调用cuRobo求解轨迹，并完成关节映射、稠密环境核验和原生轨迹打包。  
>   
> 规划成功不等于可执行；只有目标、起点、工具、场景和轨迹版本一致，且验证/打包通过，才进入受监督执行。

**画面流程：**

当前RobotState/SceneSnapshot  
→ RuntimeGoalIK（目标/姿态/当前q0）  
→ 候选IK/关节限位/可选姿态manifold seeds  
→ cuRobo trajectory optimization  
→ 稠密轨迹插值与独立环境/工具核验  
→ 按joint_names提取六轴  
→ native execution package  
→ JAKA ServoJ。

**工程修复实例：**

- 求解器输出201个采样×7个关节（包含锁定指轴）；
- 按joint_names提取joint1–joint6；
- 输出201×6；
- 回归覆盖锁定轴、乱序/批次、纯六轴等价、异常名称/维度、非有限值。

**必须正确解释的实现边界：**

- manifold seeds是候选初值，不是执行waypoint；
- FAST_SINGLE_PASS调用solve_single_pass/solve_cspace；普通路径可能调用plan_cspace；
- PRM/graph attempt是条件开关，不是每次规划必然执行；
- B样条/L-BFGS是cuRobo底层成熟实现，不是项目原创；
- independent_path_validation覆盖环境/工具几何，但源码明确self_collision_independently_checked=false；
- joint mapping修复是接口正确性，不得说提高了整机成功率。

**版式建议：**

- 主体采用一条横向流程图；
- 左下放201×7→按joint_names选列→201×6的原生小示意；
- 右下放真实代码差异/测试报告小卡片；
- 用小字区分“规划输出”“独立核验”“原生执行包”。

**素材：** src/ares_r/motion/runtime_goal_ik.py、latency_solver.py、production_scene_worker.py、independent_path_validation.py、planner_joint_mapping.py；8fbd669提交及tests/test_planner_joint_mapping.py。

---

# 第6页｜碰撞代价参数调试：四档×三次，12次规划全部未过30mm门槛

**本页要让甲方理解：** 项目做过真实规划参数对照，也保留了失败结论，而不是只挑成功结果。

**建议上屏文稿：**

> 在同一冻结AVOID场景、相同A/B目标和保守工具包络下，对10/20/30/40mm四档碰撞代价激活距离进行三次重复求解。  
>   
> 四档最小模型间隙分别为9.326、14.787、14.787和14.787mm，12次结果均低于30mm工程验收门槛，全部拒绝放行。  
>   
> 该结果说明单纯增大优化器碰撞激活距离不能保证轨迹达到工程净空要求，后续仍需处理限制几何、工具包络和硬约束/偏好约束。

**原生数据表：**

| 激活距离 | 独立核验模型间隙 | 路径长度 | 平均规划时间 | 判定 |
|---|---:|---:|---:|---|
| 10mm | 9.326mm | 612mm | 21.2s | Reject |
| 20mm | 14.787mm | 635mm | 21.3s | Reject |
| 30mm | 14.787mm | 668mm | 16.0s | Reject |
| 40mm | 14.787mm | 701mm | 21.3s | Reject |

**版式建议：**
- 左侧净空柱图，30mm工程门槛用水平线；
- 右侧路径长度/规划耗时小表；
- 底部突出“12/12重复求解未通过｜planning-only｜未生成执行候选｜无硬件运动”。

**讲者备注：**

每档3次重复调用，组内产生相同轨迹哈希，表示该配置下结果可复现，不是12个独立随机样本。该轮只完成冻结AVOID A→B的12次调用，因全部失败而早停，不是60次全方向扫值。collision activation distance是优化器代价激活距离，不是所得轨迹的最小净空保证。P3.3没有生成执行包，没有任何机械臂物理运动。后续P3.6近障退出是不同场景、不同实验，不能拼成同场景参数优化前后成功率。

**来源：** docs/reports/2026-09-22_P3_3_EXECUTION_HARDENING_REPORT.md；sweep_v2/sweep_summary.json；visualization_final/p33_clearance_profile_sweep.png。

---

# 第7页｜求解配置与GPU部署优化：从重复初始化到常驻规划器

**本页要让甲方理解：** 规划速度提升来自真实配置比较和运行架构优化，不是简单说“GPU加速”。

**建议上屏文稿：**

> 针对每次请求重复初始化、重复求解和场景更新开销，比较IK/轨迹种子数与CUDA Graph配置，建立常驻cuRobo运行时。  
>   
> 选用4 IK seeds / 2 trajectory seeds、关闭CUDA Graph；planner初始化和warm-up由服务生命周期承担，后续通过update_world载入新场景并执行一次正式求解。

**配置表：**

| 配置 | 代表性warm solve | 决策 |
|---|---:|---|
| 8/8，无Graph | 约9.7–19.5s | 不选 |
| 4/4，无Graph | P50 12.00s | 不选 |
| 4/2，无Graph | P50 5.06s | 选用 |
| 4/2，有Graph | P50 5.04s | 无明显额外收益 |

**最终五次冻结请求：**

- CLEAR正式solve P50：5.095s；
- AVOID正式solve P50：6.822s；
- CLEAR warm request wall P50：14.780s；
- AVOID warm request wall P50：17.759s；
- CLEAR→AVOID→CLEAR场景切换通过，返回CLEAR轨迹哈希与原冻结请求一致。

**独立的右臂A/B执行commission小卡：**

- 速度阶梯0.12/0.14/0.16/0.18/0.20rad/s；
- 最终0.20rad/s仅限RIGHT_ARM_AB_DEMO_ONLY；
- B→A→B往返约9.49s；
- 跟踪峰值约0.77°/1.07°；
- 到位且ServoJ正常关闭。

**版式建议：**
- 左侧配置条形图；
- 右侧常驻planner流程：初始化/warmup一次→update_world(fresh scene)→formal solve→independent validation；
- 底部单独speed commissioning卡片，明显标注RIGHT_ARM_AB_DEMO_ONLY。
- 不能把solve和request wall放在同一轴上不加解释。

**讲者备注：**

CUDA Graph开启后的5.04s与关闭后的5.06s差异很小，不应宣传Graph显著提速。常驻planner复用和去掉每请求丢弃的warm-up solve才是重要工程变化。P3.4的AVOID fast roundtrip当时延期至P3.5，不得说该轮已完成AVOID实机往返。0.20rad/s不是所有任务/所有模式的通用速度。

**来源：** P3.4报告、summary.json、config/ab_demo_deployment_profile.json。

---

# 第8页｜从规划到实机：近障起步退出与运行时目标执行

**本页要让甲方理解：** 规划适配最终落到了真实机器人运动，而且不是只有固定A/B演示。

**A. P3.6 D1任意障碍物真实执行**

上屏：
> 操作人员任意放置可见障碍物，系统重新扫描、编译场景并更新cuRobo碰撞世界；不输入障碍物坐标、不使用针对箱体的固定运行规则，完成真实右臂受监督执行。

指标：
- 场景198基元；
- 起点/终点模型间隙8.09/103.40mm；
- TCP直线/规划路径200/216.36mm；
- 最大偏离32.62mm；
- cuRobo求解3.08s；
- fresh scan pipeline8.08s；
- 实机执行11.41s；
- 最大关节跟踪0.882°；
- 无fault/abort，到位。

**B. P3.7运行时目标五段实机**

| 运动段 | 模型最小间隙 | 规划时间 | 执行时间 | 最大跟踪 |
|---|---:|---:|---:|---:|
| current→P | 25.03mm | 12.48s | 11.97s | 0.273° |
| P→Q | 33.20mm | 5.93s | 15.65s | 0.634° |
| Q→R | 33.64mm | 7.01s | 14.37s | 0.406° |
| 箱体右→左 | 28.72mm | 11.31s | 27.24s | 0.369° |
| 箱体左→右 | 27.74mm | 10.99s | 25.64s | 0.277° |

五段全部到位，无abort/fault；每段新点云SHA、SceneSnapshot和trajectory hash。

**版式建议：**
- 左侧D1真实工位/点云障碍/轨迹叠加主图；
- 右侧五段P3.7原生数据表；
- 底部流程：fresh scan→SceneSnapshot→cuRobo→independent world validation→ServoJ→arrival feedback。

**讲者备注：**

D1为单次受监督实机记录，不是成功率统计。模型gap不是物理测距保证。独立world validator检查环境/工具几何，但没有独立self-collision认证。P3.7五段是运行时目标自由空间/绕箱运动，不是抓取/接触/放置。P→Q第一次状态拒绝未发生运动，重新观测和规划后成功；可作为“旧计划失效—fresh scene—新计划”的工程过程补充。

**来源：** P3.6/P3.7报告、对应execution evidence、9/24周报真实图片/视频。

---

# 第9页｜跨工位取放：230mm物理抬升、PLACE持物几何修正与检查点恢复

**本页要让甲方理解：** 长程物理任务真实完成过关键阶段，PLACE故障不是抹掉，而是保留并展示如何修正和接续恢复。

**建议上屏文稿：**

> 10月19日Golden任务已完成取料、连续230mm抬升和约1.53m底盘转运；原全链在PLACE阶段受持物碰撞几何影响发生故障。  
>   
> 通过修订Demo持物包络、刷新场景与规划，从PLACE检查点接续完成预放置、50mm下降、释放确认和底盘返回。

**左侧：真实物理任务阶段**

- GRASP检测与预抓取；
- 接近、夹取、闭爪验证；
- 连续抬升230mm；
- 底盘单程转运约1.53m；
- PLACE检测和泊位定位。

这些阶段来自Golden任务记录，是真实物理阶段。

**右侧：PLACE故障与修复**

- 旧持物模型取了整个protruding cluster，约220×217×113mm；
- 实际料盘宽度约100mm；
- 修订主体160×100mm、原厚度沿用，另保留夹持后段20mm；
- 未删除周围真实障碍；
- 旧计划失效，刷新SceneSnapshot和cuRobo候选，从PLACE检查点接续。

**恢复阶段时间表：**

| 恢复阶段 | 结果/耗时 |
|---|---:|
| fresh scene + cuRobo候选刷新 | 15.03s |
| current→preland | 22.04s |
| 连续BODY Z−50mm下降 | 26.85s |
| 夹爪释放读回 | 1.26s |
| detach payload | 0.10s |
| base back320mm | 16.77s |
| base left810mm | 23.28s |
| base forward400mm | 18.27s |
| 恢复事件跨度 | 125.34s |

**版式建议：**
- 上半部分以大PPT slide42的真实操作照片串成5–6帧物理任务过程；
- 下半部分用“旧包络→修订包络→PLACE重新规划→下降/释放→底盘返回”的流程；
- 右侧恢复表；
- 视觉上必须区分“原始任务已完成的230mm/1.53m”和“PLACE故障后的125.34s恢复”。

**讲者备注：**

Golden README明确标记GOLDEN_TASK_COMPLETED_WITH_RECOVERY。230mm连续抬升和1.53m转运是真实物理阶段，不是规划预览；PLACE阶段故障后，修订持物模型并从检查点接续完成。125.34s是恢复事件跨度，不是整个取放任务总时长。恢复后没有重新执行pick/lift，也没有执行arm stow。释放读回确认，但没有额外视觉证据证明精确落座，也没有精密SLAM站位认证。持物模型修正是明确物体尺寸下的Demo限定override，不代表通用自动持物估计已经完成。

**来源：** docs/golden/2026-10-19/README.md；evidence/v17-place-recovery-completed/COMPLETED.md、REPORT.json；大PPTslide42；10/23周报slide08；repo panels/attachments。

---

# 第10页｜性能审计与运行时工程化：从单次求解到任务关键路径

**本页要让甲方理解：** 已对CPU几何模块、GPU规划、任务编排和完整Pick阶段的时间做分层审计；必须区分实测、回放和估计。

**A. P3.8E任务关键路径审计（AUDIT_ONLY，无硬件运动）**

- native-ready→HOLD：400.25s；
- 其中实际机械臂运动147.74s；
- 非运动252.52s；
- observation→HOLD：1266.92s，包含交互调试/人工交接；
- 完整Tray→Groove周期没有作为单个native run实测。

**B. 10/21 CPU几何模块优化**

| 模块 | 优化前 | 优化后 | 模块加速 |
|---|---:|---:|---:|
| 稠密环境核验 | 17.023s | 1.125s | 15.1× |
| 接触几何查询 | 15.176s | 0.830s | 18.3× |
| 预抓取准备 | 15.866s | 1.437s | 11.0× |

三项是不同CPU模块定义，可能存在依赖，不能相加、相乘或外推成整任务11倍提速。

**C. P3.9任务运行时软件实现（冻结回放/故障注入，不是物理执行）**

- SkillRuntime、SkillRegistry和资源锁；
- ObservationTransactionV2并行接口/确定性测试；
- FAST/FALLBACK planner policy；
- Declarative Scheme和Native Pipelined SchemeRunner；
- 18节点Tray→Groove参考Scheme回放通过；
- stale scene/start mismatch/base revision/attachment revision/grasp verification/Stop等故障注入通过；
- 全套531 tests OK，1 skipped；
- 395s为Phase-1工程模型估计，不是完整实机周期实测。

**版式建议：**
- 左侧P3.8E时间瀑布/堆叠条，显示147.74s motion与252.52s non-motion；
- 右上S21-PERF三组原生before/after条形图；
- 右下P3.9运行时流程和“Replay/Injection PASS；Physical full cycle NOT RUN”标签；
- 底部总结：已实现模块化运行时和故障边界，完整物理全链仍需单独授权与实机commission。

**讲者备注：**

P3.8E的400.25s只覆盖native-ready到HOLD，1266.92s观察到HOLD含开发/人工交接，不能全算作算法时间。S21-PERF是10/21离线CPU模块计时，不是GPU或端到端。P3.9只完成软件实现、冻结回放和故障注入，没有真实机械臂/底盘/夹爪物理运动。395s是工程模型，不能写成已实测任务周期。

**来源：** P3.8E报告；S21-PERF historical_performance.json；P3.9 report、replay_acceptance.json、low_code_acceptance.json。

---

## 统一页脚

每页使用小字脚注：
数据集/实验ID｜日期｜验证等级｜来源报告/运行记录。

验证等级统一用：
- FROZEN REPLAY；
- PLANNING ONLY；
- CPU BENCHMARK；
- SUPERVISED PHYSICAL EXECUTION；
- PHYSICAL RECOVERY；
- AUDIT ONLY / ESTIMATE。

正文不塞完整路径；speaker notes保留精确路径、commit、SHA、指标定义和限制。
