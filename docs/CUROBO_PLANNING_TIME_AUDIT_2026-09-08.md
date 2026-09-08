# cuRobo 规划耗时与时间戳审计（2026-09-08）

## 结论

ARES-R 已同时记录带时区墙钟和单调时钟。墙钟用于对齐 Terminal、规划子进程和 ServoJ 日志；阶段耗时只使用单调时钟，避免系统校时造成负耗时或跳变。cuRobo 的 `result.total_time`、`result.solve_time` 与 ARES-R 实测墙钟并列保存，不再用一个笼统的 `planning_time_s` 混合导入、初始化、求解和验证。

固定历史请求的热态测试中，默认 8/8 seeds 与 4/4 seeds 的 `plan_cspace` 分别为 2.157 s 和 2.160 s，单次样本没有可见收益；启用 CUDA Graph 后两次为 1.718 s、1.722 s，相对热态默认约减少 20%。端到端墙钟从 4.694 s 降至 4.261 s，约减少 9%。样本量不足以直接修改现场默认值，推荐先在不少于 30 个代表性场景上比较成功率、最小净空和耗时分位数。

当前固定开销约为：Python/CUDA 导入 1.47–1.55 s、配置创建 0.25 s、Planner 初始化 0.05–0.08 s、基线碰撞验证 0.18–0.21 s。持续运行的 Planner 服务与同一请求内复用 Planner，预期比继续压缩 JSON 写入更值得优先验证。

## 时间戳覆盖

每条 Python 事件包含：

- `wall_time_iso`：带本地时区、毫秒精度，可直接阅读；
- `wall_unix_ns`：跨进程关联使用的 Unix 纳秒；
- `monotonic_ns`：进程内单调时钟；
- `elapsed_ms`：指定阶段或会话起点到当前事件的耗时；
- `run_id`、`phase`、`status`：一次规划及其阶段标识。

cuRobo 阶段覆盖导入、源码 SHA 校验、模型读取、配置创建、Planner 初始化、基线碰撞检查、`plan_cspace`、稠密轨迹检查、ServoJ 时间重采样、最终几何检查和文件写入。`planner.log` 保留完整的 `ARES_R_TIMING` JSON，Terminal 同步显示简化后的实时行。

原生 JAKA 发送器的 `snapshot/sample/failed/abort/servo_disabled/logout/target_reached` 事件增加 `wall_unix_ns` 和 `steady_elapsed_ms`；每个采样还记录 `planned_time_s`、`deadline_lag_ms`、`read_send_ms`。Dashboard 显示控制器反馈墙钟、原生进程耗时、发送截止延迟和 SDK 读取加发送耗时。

## 已暴露参数

参数位于 `config/system.json` 的 `curobo.planning`，每次请求会完整固化到 `request.json` 和 `trajectory.json`。代码设置了保守范围，`self_collision_check` 不允许关闭。

| 参数 | 当前值 | 对规划耗时的影响 | 主要代价或约束 |
|---|---:|---|---|
| `num_ik_seeds` | 8 | 增加 IK 并行候选和 GPU 工作量；`plan_cspace` 纯关节目标路径通常不经过 IK，因此本 Demo 基本不受影响 | 位姿目标规划的成功率可能提高，显存增加 |
| `num_trajopt_seeds` | 8 | 增加并行 TrajOpt 轨迹；GPU 上不保证与数量线性增长 | 可能提高复杂场景成功率和解质量，显存增加 |
| `max_attempts` | 5 | 失败或不稳定场景的耗时上限近似随实际尝试次数增长；成功后提前退出 | 降低后会更快失败，也可能损失可解场景 |
| `enable_graph_attempt` | 1 | 从指定 attempt 开始执行 PRM 图搜索并以结果播种 TrajOpt | 图搜索有额外成本，但障碍绕行常依赖该路径；不能只为提速关闭 |
| `use_cuda_graph` | false | 锁定源码建议常规运行启用；本机固定请求中求解约快 20% | 首次捕获、形状变化和调试较复杂；需多场景回归后切换默认值 |
| `interpolation_dt` | 0.008 s | 主要改变返回稠密轨迹点数和后续验证/序列化量，不等同于减少优化器迭代 | 增大后轨迹离散更稀，必须继续做分段稠密碰撞验证 |
| `interpolation_buffer_size` | 5000 | 只要容量充足，通常不是求解加速旋钮 | 越大显存预分配越多；过小会无法容纳长轨迹 |
| `optimizer_collision_activation_distance` | 0.01 m | 更早激活障碍代价，可能改变收敛时间和成功率 | 增大提升提前避障倾向但窄通道更难；减小会削弱净空裕度 |
| `validation_subsamples` | 4 | 近似线性增加 ARES-R 分段稠密碰撞检查点数 | 降低会增加漏检段间碰撞的风险，不建议用于首轮提速 |
| `validation_batch_size` | 128 | 调节碰撞 FK/球体检查的 GPU 批量；过小增加批次数，过大增加峰值显存 | 需要按轨迹长度和显存基准，不保证越大越快 |
| `tool_proxy_spheres` | 12 | 工具球越多，每个验证点的碰撞计算越多 | 降低会粗化工具/TCP 延伸体，不应在实物模型未完善时减小 |
| `demo_candidate_tcp_m` | 0.16/0.14/0.18 m | 每个失败候选当前都会重新创建 Planner，最坏耗时接近候选数倍增 | 候选用于满足长度、净空与右侧工作区门禁，不宜盲删 |
| `random_seed` | 123 | 不直接决定计算量，但会改变候选、收敛和成功 attempt | 基准必须固定；生产可保留请求内可复现性 |

`speed_scale`、80 ms ServoJ 周期和执行轨迹点数影响规划后的重采样与实际执行时长，不是 cuRobo 求解速度参数。`timeout_s` 只是失败上限，也不会让求解本身更快。

## 源码接口审计

锁定版本为 `8e734f3ced1df898990bcd92de40abce475907db`，服务器源码位于 `/home/yikun/ares-r-curobo-assets/source-8e734f3`，完整 Git blob SHA 清单仍由每次 worker 校验。

- `MotionPlannerCfg.create` 默认单问题 IK seeds 为 32、TrajOpt seeds 为 4；ARES-R 显式覆盖，避免升级或批大小改变默认行为。源码说明关闭 CUDA Graph 时稳态调用可能约慢 5 倍，且 `store_debug=True` 会自动关闭 CUDA Graph。
- `plan_cspace(goal_state, current_state, max_attempts=5, enable_graph_attempt=1)` 按 attempt 循环，达到 graph attempt 后调用图搜索播种，并在首个成功结果后退出；返回的 `total_time`、`solve_time` 是已执行 attempts 的累计值。
- `MotionPlanner.update_world(scene_cfg)` 可更新碰撞世界，并会重置 graph planner buffer。该接口为持久 Planner 架构提供基础，但需要预先固定 collision cache 容量，并在工具碰撞模型或 tensor shape 改变时重建。
- 默认 IK/TrajOpt LBFGS YAML 均为 `fixed_iters: true`、`num_iters: 100`；TrajOpt 另含 `inner_iters: 25`、LBFGS history 27。图搜索配置包含 `max_nodes: 20000`、`max_path_finding_iterations: 10` 等。此类参数直接影响计算量和解质量，暂不暴露给现场配置；任何调整都应建立版本化 YAML profile，并回归成功率、净空、平滑性和显存。
- `position_tolerance`、`orientation_tolerance` 会影响位姿目标收敛判定；当前关节空间 Demo 不应把放宽容差作为性能优化手段。

源码入口：[`MotionPlannerCfg.create`](https://github.com/NVlabs/curobo/blob/8e734f3ced1df898990bcd92de40abce475907db/curobo/_src/motion/motion_planner_cfg.py)、[`plan_cspace` 与 `update_world`](https://github.com/NVlabs/curobo/blob/8e734f3ced1df898990bcd92de40abce475907db/curobo/_src/motion/motion_planner.py)。

## 优化优先级

1. 建立 30 个以上固定请求的基准集，记录成功率、P50/P95 墙钟、cuRobo solve time、最小净空、点数和显存峰值。
2. 在相同场景集上验证 `use_cuda_graph=true`；通过后再修改默认值。
3. 将独立 worker 演进为常驻 GPU Planner 服务，缓存导入、机器人模型和 CUDA Graph；所有请求仍保存模型、场景、工具和参数 digest。
4. 在单次 Demo 的多个长度候选间复用同一 Planner，通过 `update_world` 更新虚拟障碍；场景缓存溢出或形状变化时明确失败并重建，不静默退化。
5. seeds 与 attempts 采用分层策略：低成本首试，失败后按记录的 profile 升级；每一层都保持相同碰撞与轨迹验收门禁。
6. 最后才考虑稠密验证批大小、插值周期和高级优化器 YAML；不得以减少碰撞球、关闭自碰撞或跳过分段验证换取耗时。

## 固定请求基准

输入：`logs/curobo_obstacle_20260907_154635_1eb10b95/request.json`，仅历史数据重放，`simulation_only=true`，未导入 JAKA SDK。

| profile | 热态端到端 | worker | `plan_cspace` 墙钟 | cuRobo solve | 结果 |
|---|---:|---:|---:|---:|---|
| current 8/8, graph off | 4.694 s | 4.240 s | 2.157 s | 1.901 s | 成功 |
| seeds4 4/4, graph off | 4.740 s | 4.269 s | 2.160 s | 1.901 s | 成功 |
| 8/8, CUDA Graph on | 4.261 s | 3.796 s | 1.722 s | 1.230 s | 成功 |

首次冷态 current 为 8.198 s，其中导入 2.985 s、配置创建 1.152 s；冷态结果不参与参数收益比较。基准脚本为 `scripts/benchmark_curobo_planning.py`，只允许重放已有 JSON 规划请求，不包含任何机械臂 SDK 路径。
