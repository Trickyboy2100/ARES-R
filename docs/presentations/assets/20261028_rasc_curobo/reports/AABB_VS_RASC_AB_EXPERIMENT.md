# 同源几何/规划A/B

状态：DONE，FROZEN_REPLAY；没有得到OLD fail/NEW pass，不制造成功差异。

OLD：同一清理点云连通簇→32个AABB。NEW：同一3747点→235个多基元。两者逐点覆盖3747/3747；观测盒全部统一每侧7mm膨胀。已知桌面、非活动臂、机身保持相同。此处统一膨胀为因果消融，区别生产SUPPORT role最多4mm padding。

未膨胀体积之和 0.008861522→0.001939863m³；膨胀后 0.014947602→0.008830445m³。都是sum，不是union。剖面2mm网格显示OLD-only表示面积，并公开选择最大差异Z层的规则；不把没有点/遮挡区域称为传感器已证明空闲。

同一request来源、q0、目标T、link6/TCP、持物、夹爪/arm盒、安全限幅、random_seed=123、2轨迹/4IK、50 iterations、CUDA graph、single pass。安全摘要两行必须一致。runtime_motion_goal会对输入qgoal做微小目标投影，两种输出终点相同；不是手工绕障线。cuRobo原理图表示上游能力；本次solve_cspace的目标由ARES-R RuntimeGoalIK解析，配置4个IK seeds并不证明本次调用了上游GPU IK。A/B仅证明两表示使用相同派生运行限制，不证明与缺失的原site runtime YAML动态限幅等价。

| 表示 | 结果 | start gap mm | goal gap mm | independent path gap mm | 单次solve wall s |
|---|---|---:|---:|---:|---|
| OLD | SUCCESS | 65.204 | 80.843 | 56.942 | [5.3284958680014824] |
| NEW | SUCCESS | 65.637 | 80.843 | 54.982 | [6.994138030990143] |

两次都是冷worker请求，非P50/P95。OLD路径236.140mm，NEW231.706mm；OLD最小净空56.942mm，NEW54.982mm。几何更细并没有保证本例更大净空或更快求解；仅一组输入无法得出全局鲁棒性结论。

实际GPU均RTX3080，峰值allocator allocated852749312B / reserved989855744B；不代表整卡占用或10GB视觉共驻认证。独立world validator PASS；independent self collision=false，cuRobo内自碰撞仍启用。未把两者混为全套独立验证通过。

运行适配：原现场YAML缺失。由pinned ARES YAML保留六臂轴cspace参数，锁定非规划夹爪DOF为0、导出link6；URDF字节不改，夹爪/payload碰撞来自冻结request。导出原生finger frame、7DOF cspace不匹配、locked DOF七列输出的失败均在本地日志与runtime_adapter*摘要保留。最后一项暴露正式worker固定reshape缺陷，独立修复8fbd669，5项回归。不是偷偷换成preview模型并宣称现场几何通过。

原历史request缺attached revision字段，但exact attached object ID已不在旧world中。本轮仅补元数据；新多基元未删除任何障碍来通过。capture q与规划q0不一致见INPUT_INDEX，这是静态冻结世界表示实验，不是fresh epoch执行审批。

worker未导出中间seed轨迹，因此只画最终选中真实轨迹。candidate_paths不造假；图位记录BLOCKED_SEED_INTERMEDIATES_NOT_EXPORTED。没有有认证标签的真实CLEAR/AVOID/BLOCK三组scan，故该独立系列待补。
