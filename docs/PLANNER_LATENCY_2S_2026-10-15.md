# cuRobo ≤2s 快规划实现与验收

日期：2026-10-15。范围：仅规划、GPU/CPU基准、网页预览；未运动机械臂/夹爪/底盘，未修改控制器保护、运动速度、碰撞间隙或姿态容差。

## 结果

正式在线后端，fresh scan 后的10mm BODY JOG预览 `PLAN_c148550c78284276802858055bdc9f17`：

- cuRobo solve：0.524697s。
- 已验证规划总时间：0.695804s（world update、IK、cuRobo、独立碰撞和姿态验证）。
- fresh camera + scene/state + plan/package 整次请求：9.693448s。
- hard_valid=true，modeled minimum clearance=15.1413mm，生成预览包；没有执行。

**规划目标已在当前在线用例达到；拍照到轨迹的整个流程并未达到2秒。** 剩余约9秒链路不能冒充cuRobo耗时，也不能靠复用旧场景隐去。

冻结请求回归，每配置5次：首次冷启动、后4次热运行，seed=123；不是5个独立随机场景。

| 用例 | 原记录规划总时间 s | 新热请求中位数 s | 热请求范围 s | 结果 |
|---|---:|---:|---:|---|
| 同一10mm JOG | 29.953（上轮受控基准） | 1.196（单轮25迭代/2 seeds，尚未叠加原生CPU优化） | 1.186–1.215 | 5/5 |
| center约36cm | 16.569（历史原始记录） | 1.863 | 1.858–1.869 | 5/5 |
| 约45cm真实避障 | 21.002（历史原始记录） | 1.906 | 1.904–1.916 | 5/5 |
| 水平yaw自由约36cm | 19.845（历史原始记录） | 1.655 | 1.651–1.657 | 5/5 |
| 显式派生合成BLOCK | — | 0.665 | 0.663–0.667 | 3/3正确拒绝 |

历史记录用于对照，不是同进程交错随机A/B试验。center、避障、yaw自由的minimum modeled clearance分别约20.471、20.130、18.872mm，现有姿态验证均通过。合成BLOCK明确标记为派生测试，不宣称真实现场实采阻塞。

## 为什么原来慢

1. 当前长驻runtime已存在，warmup=0，旧JOG仍约28.6s solve。因此不能再把主要问题解释成进程冷启动。
2. pinned cuRobo `MotionPlanner.plan_cspace` 内部固定 `finetune_attempts=3`：初始优化加3轮时间最优精修，默认每轮100次迭代。一次cProfile记录：4次optimizer共31.994s；GPU同步累计26.692s。不是仅仅调用了一次solve就只有一轮优化。
3. CUDA Graph单独开启没有解决主问题：8/8仍约23–30s，4/4约15.77s；GPU利用率曾100%，不是单纯Python调度等待。
4. 低迭代把45cm路径solve降至约0.728s后，原逐障碍NumPy验证仍拖到7.46s，其中独立检查约3.13s、全部postprocess约6.43s。
5. 每请求存在两次相同world update；固定TCP目标矩阵进入runtime cache key，也会把目标变化误当作重新初始化条件。

## 实现

- `config/planner_latency_profiles.json`：独立版本化FAST策略，2 trajopt seeds / 4 IK seeds、CUDA Graph、一次优化，不做额外时间最优精修。EXPLICIT/CURRENT/LEVEL_YAW_FREE为25迭代，其余50；本版本优化器inner_iters=25，只接受其倍数。
- `latency_solver.py`：仍调用正式cuRobo `trajopt_solver.solve_cspace`，由cuRobo生成种子/平滑路径。不是直接插值，不是MoveJ，不添加人工waypoint。
- `sphere_cuboid_cpu.cpp` / `cpu_distance.py`：双精度CPU距离循环，保持原球体、OBB、所有样本和SDF公式；利用严格距离下界避免无用sqrt。没有fast-math，没有删障碍、扩大self-filter或降低采样密度。与NumPy参考逐物体最小值、逐样本最小值比对至1e-12。
- 独立验证仍使用CPU/URDF自行计算FK，不接受planner给出的距离；复用的是解析距离原语，不是planner判定。self-collision仍由cuRobo检查；独立报告继续明确 `self_collision_independently_checked=false`，不冒充新增认证。
- 仅更新一次fresh world；同一几何和约束构建参数复用runtime，目标姿态仍进入每次goal buffer与hard orientation检查，但不再无理由重建planner。
- 删除重复计算的dense clearance；FAST不计算只用于诊断的101点joint-linear baseline。**实际候选路径的dense碰撞、独立检查、姿态、中央禁区、动力学和native gate全部保留。**
- 结果超过2秒标记FAILURE；FAST客户端2秒timeout，不自动降到慢QUALITY。超时客户端关闭后，worker可完成后台计算，但迟到artifact不会进入该次执行候选；服务不会因BrokenPipe退出。
- 缺少长驻worker时FAST立即报NOT_READY，不在用户请求中偷偷花几十秒启动。GPU/编译冷预热与在线预算分离。

## 兼容与使用

ART/WebUI手动运动入口默认FAST。WebUI `/operations` → 手动操作/规划 →「规划模式」；QUALITY显式保留。ART示例：

```text
motion plan right --xyz 0.60 -0.20 1.20 --orientation LEVEL_YAW_FREE --planner FAST
motion plan right --xyz 0.60 -0.20 1.20 --orientation LEVEL_YAW_FREE --planner QUALITY
```

这里只规划，不执行。JOG仍是方向预览→查看→现场确认执行。页面分别显示cuRobo solve、已验证规划、总等待时间。

直接构造的历史Task/Skill `MotionRequest` 默认仍为QUALITY；没有迁移/替换golden first-pick脚本，没有改 `config/scene_aware_motion.json` 或任何物理速度profile。新请求字段 `planning_mode` 与latency contract保存在artifact中。

当前固定姿态、水平目标、yaw自由三类已经在正式planner完成预热。重启整机/更换模型工具后需要重新预热；入口：`scripts/prewarm_fast_planner.py`，只读取明确给出的冻结请求用于初始化，输出 `warmup_only=true / no_execution_candidate=true`。初始化世界绝不能当成新现场scene；真实请求始终fresh scan并update_world。示例：

```bash
cd /home/yikun/ARES-R
python3 scripts/prewarm_fast_planner.py \
  --request worklog/evidence/scene-aware-motion/PLAN_3ded5c936c7b427fa7ae89de1bf9b322/planner_request.json \
  --request worklog/evidence/scene-aware-motion/PLAN_cf288b2eae2240afa6f8e1351f567c02/planner_request.json \
  --request worklog/evidence/scene-aware-motion/PLAN_74e28dba5bf140e39ee3a61a5c3533cc/planner_request.json \
  --output worklog/evidence/fast-planner-prewarm-NEW-UNIQUE-ID
```

## 未隐藏的限制与失败

- 不是任意场景2秒必定找到轨迹，更不是硬实时系统认证。FAST可能返回不收敛/超时；不能用失败轨迹执行。当前只证明少量真实冻结场景与一次在线preview，尚无大样本p95或实机新轨迹验收。
- center用例25迭代的热运行会失败，保留证据；50迭代修复。没有因此降低碰撞/姿态阈值。
- 最初16/32迭代被pinned optimizer拒绝（inner_iters=25），保留失败原始记录，不算速度成功。
- 冷初始化约6–10s以上，不包含在热请求SLO；生产首次编译曾因极简worker环境缺PATH找不到ld，已显式补编译PATH，正式v2三类预热均成功。
- 2秒预算目前只控制planner请求，不控制fresh camera/scene/SDK读取和native包装。整次操作约9.69s的下一瓶颈应另行优化，不能承诺点击后2秒就开始运动。

## 证据、测试与保全

全部现场证据在 `/home/yikun/ARES-R/worklog/evidence/`：

- `2026-10-15-cuda-graph-benchmark/`：CUDA对照、`solver_cpu.pstats`。
- `2026-10-15-single-pass-benchmark/`：16/32迭代拒绝证据。
- `2026-10-15-single-pass-v2/`：25/50迭代JOG对照。
- `2026-10-15-fast-center36/`、`2026-10-15-native-center36/`：低迭代失败与CPU加速。
- `2026-10-15-balanced-center36/`、`2026-10-15-balanced-avoid47/`、`2026-10-15-native-yawfree/`：最终profile回归。
- `2026-10-15-fast-block/`：合成BLOCK，无fallback。
- `2026-10-15-fast-production-prewarm-v2/`：正式三类预热。
- `scene-aware-motion/PLAN_c148550c78284276802858055bdc9f17/`：在线fresh preview，全链binding、原始request/result/native audit，未执行。

基准脚本：`scripts/benchmark_frozen_planner_profiles.py`。最后全量测试：605项，OK，1 skipped。现场保全：`worklog/preservation/2026-10-15-fast-planner/`；部署前逐文件SHA256对齐上轮基线、保存dirty patch和旧源文件，不覆盖同事无关改动。网页build：`2026.10.15-operations-v3-fast-planner`。未push。
