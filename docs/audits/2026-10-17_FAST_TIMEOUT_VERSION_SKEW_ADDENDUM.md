# FAST超时与版本分裂补充核查

日期：2026-10-17。补充于归档推送前，仅离线读取本机两份工作树；没有连接机器人或重新benchmark。

## 1 需要修正的根因表述

本次初始审计指出`ARES-R-offsets-20261016`中的`production_scene_worker.py`没有消费solver_policy，这个静态发现正确。

但随后发现`ARES-R-operations-20261015`的同名文件**有**FAST实现，包括：

- L22导入`validate_solver_policy/solve_single_pass/orientation_runtime_key`。
- L83解析solver_policy。
- L300附近按policy调用single-pass，不走普通多attempt入口。
- L336附近限制max_goal_candidates。
- 距离backend使用NATIVE_CPU_V1，FAST不计算joint-linear baseline诊断。

因此必须把结论分为两层：

1. **已证实：本地存在同名worker和不同功能实现的版本分裂。** 新Demo审计副本不是唯一来源，Git HEAD也不足以代表dirty文件。
2. **尚未证实：10月16日每次现场运行进程实际加载哪份worker、哪一版模块。** 要取现场源码SHA、进程启动时间和loaded module revision；不能仅凭两个本地文件就宣称现场必定漏接FAST。

主报告的R1应按此限定理解。先前将“本地副本未消费策略”直接表述成“现场没跑快速链路”的确定根因，证据强度不足；本补充明确纠正，不隐去原始发现。

## 2 两份本地文件的准确身份

| 本地工作树 | worker SHA256 | 功能 |
|---|---|---|
| ARES-R-offsets-20261016 | `6a706b15843f1211fa9117a339d03b4e8a1996567d36e813aecac78314978329` | 本审计冻结副本；未消费solver_policy |
| ARES-R-operations-20261015 | `3afcc99a04217a385cc6999f9065d2d4ac06eca7fe747b8644c3b6e2683d5012` | dirty副本；包含single-pass及FAST距离路径 |

operations副本的`latency_solver.py` SHA256：`e853aac0c60ac86595541ed84229f6d176c5d540746446ec77a93db9f73bae72`。

operations Git HEAD为`b3ab331`；offsets HEAD为`9ff4517`，两者都有未提交内容。本补充没有复制这些dirty改动到运行主线，也没有为了归档把它们合并。

## 3 为什么“这么简单”仍然慢

### 3.1 TCP看起来简单 不等于优化问题尺寸小

本次记录的active spheres曾为1727个；world有大量点云分解cuboid。每次优化要在多时刻、多seed、多关节上检查整臂/夹爪/持物与世界、自碰撞和姿态，不是只画一条TCP直线。

碰撞对量级近似随`spheres × world primitives × trajectory horizon × seeds × iterations`增长；GPU实现有并行和缓存，不能用此式精确预测秒数，但它能解释模型成本与肉眼动作长度不是一回事。

这也不证明35秒或112秒是合理必需，更不证明cuRobo本身只能这么慢。需要固定同scene/model/start/goal/profile做预算和热运行测量。

### 3.2 FAST第一次用时包含冷路径和可能的排队

已经读取的FAST late-result样本：planner初始化10.73秒、planning_samples35.09秒、postprocess/validation32.66秒，整个worker80.25秒。客户端只等4秒就报超时，但后端仍算。独立dense约10.87秒已经包含在后处理里，不能再加一次。

planning_samples也不一定是纯优化核时间；首次CUDA graph capture、缓存分配/编译、同步等可能位于该区间。**本轮没有足够kernel trace，不能精确分出这些各占几秒。**

### 3.3 QUALITY更重 而且无法修模型错误

QUALITY使用8/8、max_attempts5等重路径。第二次任务QUALITY实际solve112.08秒，整个worker159.53秒，但它规划成功了；随后失败的是接近IK。

另一次QUALITY是CUDA OOM，不是几何无解。最后130mm请求则反复报告起点碰撞，start gap−62.26mm、goal+45.98mm。**在模型认为起点非法时，增加seed/迭代并不能把它变成合法起点。** 必须先归因持物重复建模/真实结构/模型余量，不应机械跑更多QUALITY。

### 3.4 大量时间根本不是cuRobo求解

扫描、双臂完整audit、多进程启动、CPU全障碍距离、JSON/NPZ写盘、包校验、native重采样，以及现场编写恢复脚本与人工往返都在关键路径上。contact文件115.04秒与initial lift约72秒是物理发送时长，不是planner超时。

## 4 最快判明真实瓶颈所需的证据

每个现场请求必须记录：

```text
loaded_worker_source_sha / loaded_latency_solver_sha / planner pid+start time
requested_profile / effective_seed_counts / actual_solver_entrypoint
world cuboid count / active sphere count / horizon / iteration budget
cache key / cache hit / CUDA graph state / allocated+reserved VRAM
queue / init / graph-capture / warmup / solve / validation / serialization
job deadline / cancel acknowledged / late result discarded
```

在同一冻结scene做：已集成FAST副本、普通QUALITY、分别冷/热、空载/持物、相同正确性标准。不能用旧A/B或10mm JOG的热运行数字证明新抓取场景也一定≤2秒。

## 5 修复顺序

先确认并统一现场实际加载版本；再保证warm FAST真正single-pass、deadline可取消、显存有界；最后处理持物世界归属。遇到invalid start直接报告模型归因，不升级更贵profile。不要先用更大timeout掩盖问题，也不要直接删掉全部环境点。

该补充与原审计一起提交独立资料分支，**没有部署任何planner或机器人代码**。
