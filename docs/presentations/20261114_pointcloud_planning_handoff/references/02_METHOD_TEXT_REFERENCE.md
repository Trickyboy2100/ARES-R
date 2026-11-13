# 20261028方法PPT：内容与讲述依据摘存

Source: reconstructed

原件：`20261028-水分细度目标识别与场景自适应规划控制-2(1).pptx`，对应无`(1)`旧上传版。

本文件是已有文本及备注的结构化摘存，不含二进制媒体。原件显示01/09至09/09编号，同时存在重复的07/09、08/09布局页；显示编号不等同实际slide索引。

## 01/09 点云建模

BODY统一空间；机器人OBB/sphere自滤；5mm体素；半径20mm至少4邻点；DBSCAN ε=12mm、m=8。然后支撑层检测、局部网格分解，避免一个整体AABB包住非凸空区。

支撑层：5mm高度直方图、±10mm带、局部法向与水平连通性；高于支撑25mm形成凸起候选；40×40×30mm主体网格；机器人邻近误包络位置15mm细化。

原图输入示例来自9月11日周报；参数为核查版本默认值，不构成参数寻优实验。

源码定位（ARES-R@8da63a6）：
- src/ares_r/perception/residual_cloud.py：CleanupProfile、clean_and_cluster。
- src/ares_r/perception/support_decomposition.py：detect_support_levels、decompose_support_objects、refine_robot_adjacent_primitives。
- src/ares_r/perception/robot_owned_filter.py：build_robot_owned_filter、filter_robot_owned。

## 02/09 包络精化

上图为10/23模型示例，下表为9/21 CLEAR同帧统计。7→167；9,992点前后全覆盖；0.010413→0.004288m³；减少58.8%。体积和不等于几何并集，也不代表通道空间增长率。

报告：docs/reports/2026-09-21_P3_1_RESIDUAL_SUPPORT_DECOMPOSITION_REPORT.md。
数据：worklog/evidence/2026-09-21-p3-1-residual-support/clear_ab/comparison/。

## 03/09 目标关节、种子和PRM

ARES用有界非线性最小二乘求目标关节，再进入cuRobo plan_cspace。直接插值/任务种子启动轨迹优化；允许重试时PRM提供连通绕障初值。FAST单次配置可关闭该层重试。PRM不是每次都触发，也不是项目训练所得模型。

src/ares_r/motion/runtime_goal_ik.py；production_scene_worker.py的runtime_goal_candidates/solve_segment；cuRobo@8e734f3的motion_planner.py、node_sampling_strategy.py、path_finder_networkx.py。

## 04/09与05/09 原理页

B样条控制点→关节轨迹→FK球心→球盒距离→代价梯度；L-BFGS有限历史与并行步长评价。锁定配置BSPLINE_3、n_knots=16；说明中提到0/0.1/0.5/1.0步长、默认100次迭代与27步历史，运行配置可变。

这些仅是来源内容和可能追问的理论支持，不应原封不动替代研发过程页。优化代价与最终核验作用不同，是否保持水平要看实际请求和独立姿态输出。不同种子个数也不必然代表不同随机轨迹。

## 06/09 CURRENT_BASE A/B

9/21，相同A/B关节目标，改变箱体条件。CLEAR TCP长度0.430276096m；AVOID 0.452617223m；增程22.341127mm。直接关节插值与箱体相交，而优化轨迹通过相应模型碰撞检查。

BLOCK为合成目标封闭回归，不是现场实物封闭。数据是规划结果，不是实机里程/三场景成功率。路径增程、两条曲线分离量和距障净空三者不得混用。

docs/reports/2026-09-21_CURRENT_BASE_AB_TCP_EXPERIMENT.md；worklog/evidence/2026-09-21-p3-1-residual-support/current_base_avoid/comparison/comparison.json；原对照图来自0924周报P8，image10.png对应clear_vs_avoid_three_views.png。

## 07/09 任务参数和依赖

参数模式校验、前序输出绑定、执行依赖与预准备依赖、资源声明。接近参数50mm改45mm、插入验证节点，18→19节点方案通过离线回放。不是大模型自主理解，也不是新增实机任务成功。

src/ares_r/skills/contracts.py、registry.py、src/ares_r/task_runtime.py、schemes/commissioned/tray_to_groove_v1.json、docs/reports/2026-09-28_P3_9_REALTIME_SKILL_RUNTIME_IMPLEMENTATION_REPORT.md。

## 08/09 状态绑定与资源互斥

准备阶段保存场景/起点/工具/持物/有效期/资源。PLAN_EXPIRED和BINDING_MISMATCH会拒绝执行，上层重新准备。归属更新依据明确对象ID；不会自动分割任意对象。已有离线故障注入不等同现场全部安全风险验证。

src/ares_r/skills/runtime.py、locks.py、real_provider.py、world/scene_compiler.py。

## 09/09 性能

cKDTree一次建树→外接球邻域候选→原包围盒逐坐标精确筛选→按原索引顺序返回；原生CPU距离核批量核验。

| 10/21历史模块 | 前/s | 后/s | 比值 |
|---|---:|---:|---:|
| 稠密碰撞核验 | 17.023 | 1.125 | 15.1× |
| 接触几何构建 | 15.176 | 0.830 | 18.3× |
| 预抓取准备 | 15.866 | 1.437 | 11.0× |

235次查询和301轨迹采样属于其他等价回放记录，不能移作这张历史表的样本口径。模块有包含关系，不可相加；完整任务还包含感知、设备运动和调度。

src/ares_r/manipulation/observed_contact_geometry.py；docs/presentations/assets/20261028_rasc_curobo/grasp_v3/runlogs/historical_performance.json；同目录根runlogs/contact_query_comparison.json和cpu_backend_comparison.json。
