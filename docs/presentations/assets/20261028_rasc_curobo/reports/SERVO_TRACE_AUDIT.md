# ServoJ真实成对日志审计

有真实成对target_rad、actual_rad与monotonic；没有本轮硬件动作。两个来源位于仓库9/7 cuRobo supervised micro目录，SHA见runlogs/servo_trace_metrics.json。字段/来源与当前jaka_micro_servo的telemetry语义交叉核对，未用FK代替实测。

两例均计划41个点，但实际只记录14/17个sample，随后abort_accepted、servo_disabled；没有target_reached，不是正常完成段。不能把截断曲线说成稳定成功或速度优化效果。中止根因在这两份日志中未完整记录，不能仅凭当前源码推断唯一原因。

关键对齐：current adapter在读取actual之后才发本条target，因此同一记录target/actual并不同步。target-vs-actual原样显示；跟随误差图使用actual[k]−target[k−1]，第0点以初始command参照。不移动时间轴来人为重合。实际反馈是dedicated telemetry joint_actual_position_rad，不是SDK FK或controller_reported_rad；某些历史字段不能据名称简单当同一种feedback。

| 例 | 成对样本 | 已记录span s | previous-command max° | RMS° | P95° | 完成状态 |
|---|---:|---:|---:|---:|---:|---|
| 1 | 14 | 0.7288 | 0.089334 | 0.015516 | 0.030225 | ABORTED |
| 2 | 17 | 1.2639 | 0.012055 | 0.002514 | 0.006070 | ABORTED |

每例独立六关节目标/回读、六关节误差、J6速度/加速度图，保留全部样本。差分用np.gradient实际不规则monotonic，无滤波；记录稀疏且噪声显著，不报告jerk或动态安全认证。日志span不等于计划duration，也不等于完成运动耗时。

9/24正常pregrasp/contact/lift跟踪汇总仅历史报告可引用（0.591/0.036/0.045° max等），对应完整成对sender日志未在本地取得，故不重建正常完整任务波形，不把9/7微运动代替9/24抓取。需要原native_supervised.jsonl、原native文件、单调时间字段、样本周期、错误与settling/arrived读回。
