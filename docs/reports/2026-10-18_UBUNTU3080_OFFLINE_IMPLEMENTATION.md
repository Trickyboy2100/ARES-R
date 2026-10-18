# Ubuntu RTX3080 首轮实现与真实 GPU 验证

日期：2026-10-18（Asia/Shanghai）。本轮完成环境、硬件隔离、P0/P1实现和分层验证，**尚未完成 P2–P5 或 GPU 串联的19阶段验收，不可现场部署**。

## 源码与环境

实际仓库是 `repos/ARES-R`。接手时本机位于旧研究分支 `research/skill-handoff-smoke-20261012`，清洁工作树；已 fetch 指定交付分支，核对基线 `63887dddee15d8e58f4da24821d0c0a9e1a19864`，从该提交创建 `codex/ubuntu3080-roundtrip-replay-20261018`。交付 `SHA256SUMS` 初始全通过；审计快照及 operations variant 原样保留，仅选择性合并运行源码。

已阅读交付文件、五份指定报告/审计，以及 GitHub `planning/20261018-roundtrip-delivery-dash` 两份 work order。当前用户的单张本地3080要求优先于旧工作单的远程GPU建议；没有使用其他GPU机器。

- Ubuntu 22.04.5，内核 `6.8.0-138-generic`；PCI识别 RTX3080，CUDA可见显存 `10,331,226,112` bytes，单卡。
- 已加载 NVIDIA 内核模块 `580.173.02`，NVML/已安装用户态及磁盘上的 DKMS 模块 `580.178.04`。宿主 `nvidia-smi` 报 `Driver/library version mismatch`。**NVML故障不等于CUDA不可用**：真实CUDA初始化、规划、graph capture和OOM测试均已运行。
- 最小运维修复可在维护窗口重启，以加载已经安装的 `580.178.04` 模块；或由管理员恢复与当前已加载模块一致的用户态库。本轮没有重装驱动、卸载模块或重启。
- 初始 RAM约29/31GiB，swap 2/2GiB，磁盘可用约91GiB；宿主主要内存占用来自既有编辑器进程。只读检查，没有清理/终止任何同事进程。后续 shell 禁用登录初始化，避免额外启动开销。
- 独立 `.venv` 复用现有 foundationpose 环境的 Torch `2.5.1+cu121`（原环境只读），Python `3.11.15`；追加依赖仅装入该 venv。实际版本见伴随 JSON。Torch CUDA runtime 12.1；cuda-core/NVRTC来自独立 venv 的12.9依赖，Warp 1.18.0；这是实测相容的 smoke 环境，不声称复制了现场依赖锁。
- cuRobo `8e734f3ced1df898990bcd92de40abce475907db`：444个源文件逐个 Git blob 验证。editable安装因缺少setuptools-scm Git元数据失败，改用 venv `.pth` 指向已校验源码，不修改cuRobo文件。不是从pip安装其他cuRobo版本。
- 在旁边的 ARES 源码中找到16个 pinned URDF/YAML/STL文件，全部匹配 `robot_collision_model.json` 的SHA256。模型来源字节已具备；**现场commissioning证据未具备**。GPU smoke使用 `prepare_curobo_model.py` 明确标记 `commissioned=false` 的preview配置，不能把源文件哈希正确写成现场几何通过。

## 已实现的变更

### 硬件隔离

`scripts/offline_sandbox.sh` 使用 bubblewrap 建立独立 network/IPC 和私有 `/tmp`、最小 `/dev`。默认无GPU；`--gpu`只显式暴露GPU0所需设备。没有真实串口节点；到JAKA网段连接由内核返回 `ENETUNREACH`。进程及SDK/子进程继承此隔离，不能通过 `system.json mode` 绕开。生产服务和真实运动入口未启动。

`ARES_R_OFFLINE_REPLAY=1` 下，RealCapabilityProvider.execute 和 Live transport 构造明确拒绝物理I/O。测试证明拒绝发生在设备dispatch之前。Mock/Replay provider单独运行。隔离仅对经该wrapper启动的进程生效，不声称全宿主已断网。wrapper在Codex受限沙箱内不能创建network namespace，需要经宿主权限工具运行；创建隔离失败即退出，不自动降级。

### P0 FAST、deadline和资源

- 合并 operations 的 single-pass／native CPU distance路径，保留canonical cuboid容量分桶与容量进入cache key的修复，没有整文件替换。
- FAST强制一次正式solve、一个候选、不运行请求内warmup/benchmark重复；输出实际4/2 seeds、50 initial iterations、finetune=0、graph启用和实际捕获数、solve调用数及worker SHA。
- 独立CPU supervisor持有至多一个CUDA子进程。profile、模型/附件、solver参数或容量桶变化，先回收旧进程，再建新context，避免FAST/QUALITY/持物缓存叠加。Torch allocator限额75%；这不是所有Warp/CUDA分配的全局硬显存上限，完整大场景仍待验证。
- job_id、绝对monotonic deadline、no-queue BUSY、独立cancel请求/ack、客户端断连检测、晚到结果丢弃。只有期限内结果才从job私有pending文件发布。超时/取消/OOM均join本任务子进程；父进程退出也有PDEATHSIG保护。取消ack不能用吞BrokenPipe代替。
- 请求端点碰撞提前返回 `INVALID_START_COLLISION`/`INVALID_GOAL_COLLISION`；OOM归类 `RESOURCE_EXHAUSTED`。terminal错误不进入QUALITY重试。输入错误不锁死GPU owner。
- 独立CPU/URDF世界碰撞验证现在对没有tool-envelope的历史规划请求也执行。它独立校验world；self collision仍由cuRobo检查，不能把报告中的 `self_collision_independently_checked=false` 隐去。

### P1 抓取前置检查

当前完整Demo调用prepare时显式启用precheck；golden文件与旧调用默认不变。先于cuRobo检查完整26点55mm contact及51点100mm lift、NORMAL/FLIPPED两种姿态，每种至多两个seed，总预算15秒；每次数值IK最多90 nfev。检查URDF及site soft limits、1.5mm/0.6°残差和3°水平合同。失败仍记录后续所有采样残差；预算耗尽标记曲线不完整，不伪造完整不可达证据。

无分支可行时写 `contact_lift_precheck.json` 并终止，不请求昂贵自由空间规划或QUALITY。数值无解不是数学不可达证明。独立碰撞与最终package校验保留；该precheck不构成接触段执行许可。

## 实测证据分层

### 真实cuRobo合成smoke：通过

最终worker对应 `gpu-smoke-03`：单GPU、pinned solver、preview模型、明确的合成远障碍世界；未修改历史fixture来伪称历史成功。

- 冷请求5.091秒，包含import/init/首次graph capture；不能承诺冷启动4秒。
- 10次warm请求连续成功：p50 **0.2831秒**，范围 **0.2800–0.2932秒**，包含独立world验证。
- 每次实际solve=1、warmup solve=0、trajopt seeds=2、IK seeds=4、initial_iters=50，启用graph并捕获1个optimizer graph。
- Torch peak allocated **546,581,504 bytes**，reserved **614,465,536 bytes**；10次reserved完全一致，runtime cache=1。只代表该smoke负载，不外推现场1727 spheres/大量cuboid的延迟或VRAM。
- 41点路径；独立CPU/URDF验证43个dense samples通过。合成障碍很远，这不是现场安全净空认证。

### 历史场景PROXY_REPLAY：保留失败

9月21日已有CLEAR/AVOID/BLOCK输入真实调用GPU。CLEAR和AVOID均失败，start gap分别约−24.64mm/−24.17mm；BLOCK拒绝符合预期。历史CLEAR保存的原始planning.json本身也是FAILURE。这些不能写成CLEAR/AVOID验收通过，更不能写成10月16日复现。新端点门会在这些非法start/goal上拒绝进入优化。

### 真实CUDA故障：通过已测试范围

`gpu-faults-02`（无实机、合成规划输入）：

| 案例 | 结果 |
|---|---|
| cuRobo进入SOLVE_START后取消 | cancel ack，子进程join，未发布结果；整个冷请求约2.841秒结束 |
| 冷cuRobo四秒deadline | 4.000秒触发回收，约4.069秒完成join，未发布迟到结果 |
| 限额CUDA allocator OOM | 实际Torch OutOfMemoryError，RESOURCE_EXHAUSTED，context回收，约0.978秒 |
| 故障后真实cuRobo恢复求解 | 成功，独立world验证通过，约4.825秒冷请求 |

OOM通过1% allocator限额触发512MiB申请失败，不是伪造异常，也**不是完整cuRobo大场景OOM复现**。全部context最终回收，清理后CUDA free约9.698GB，与初始接近；没有操作其他GPU进程。4秒是触发deadline而非硬实时零延迟回收，实测清理尾部约69ms。

CPU进程及真实Unix socket测试另覆盖10次复用、profile切换、BUSY、超时ack、完成/取消竞态撤销产物、OOM错误和无效job恢复。

### P1真实数值IK：合成目标通过，Oct16待补

使用pinned preview URDF、真实SciPy优化，构造独立合成BODY frame/目标：可行case两类姿态完整contact+lift均通过，约0.894秒；远目标两类姿态完整曲线均失败，约1.150秒。没有把模板关节冒充新鲜实机观测。旧GRASP失败／新GRASP成功这对10月16日输入尚缺，因此总gate为PARTIAL。

### 19阶段：Mock状态回放通过，GPU串联未完成

同一个CycleRunner通过继承ReplayCapabilityProvider的有状态transport完成10个连续19阶段循环，核对100+130=230mm、0.85m审核路线及逆路线、lower_middle+40mm释放、不收臂。5个阶段故障注入均停止，不继续执行后续命令。逐stage START/PASS/FAULT和monotonic耗时保存在本地runtime。

这些耗时是Python替身调用时间，不能作为物理运动／GPU全周期耗时；没有把一条smoke GPU轨迹冒充19个真实阶段的规划输入。100mm后正式checkpoint/resume **未实现**，不能据Mock循环通过声称不会重发物理动作。

### 全量测试与golden

最终 **656 passed, 3 skipped, 13 subtests passed**。初始正式tests为635通过、2失败、3跳过；两项旧测试期待registered-relative，而交付scheme实际早已使用autoalignment，本轮修正测试对已有scheme的断言，没有改变任务路线/策略。显式注入假服务的delegation测试局部mock拒绝guard；另有独立测试验证真实provider离线execute拒绝。

pytest默认只收集正式`tests/`，不执行audit source_snapshot、operations备份测试或旧硬件prototype。golden两个文件SHA256与交付完全一致：

- `scripts/run_first_pick_demo.py`: `e158482004601bbb1e562ee842fb590f27805813b7d7ee029ce5e59e41ea2bb0`
- `demos/right_arm_epic_pick_lift_v1/demo.json`: `25b78297558e755895d3a0202f0afe43147ac5625539c70bd7e790343b246056`

## 验收旗标

| 指标 | 状态 | 边界 |
|---|---|---|
| RTX3080_CUDA_READY | PASS | CUDA与真实规划可用；NVML仍故障 |
| PINNED_CUROBO_READY | PASS | 444源文件verified，实际GPU求解成功；不是现场模型commissioning |
| OFFLINE_HARDWARE_ISOLATED | PASS | wrapper内network/serial隔离和物理execute拒绝均验证 |
| OCT16_RAW_FIXTURES_AVAILABLE | BLOCKED | 未取得完整实机冻结输入 |
| FAST_EFFECTIVE_SINGLE_PASS | PASS | 实际GPU seeds/graph/次数已验证；现场规模性能未验收 |
| FAST_CANCEL_NO_ORPHAN | PASS | 实际cuRobo取消/deadline与Unix协议回收均验证 |
| EARLY_CONTACT_LIFT_PRECHECK | PARTIAL | 代码及真实模型合成IK通过，缺Oct16 fail/pass对 |
| ATTACHED_WORLD_IDENTITY_READY | FAIL | P2尚未修复，仍有重复环境点云风险 |
| 19_STAGE_OFFLINE_REPLAY | PARTIAL | 10次Mock状态闭环通过；GPU与真实冻结场景串联未完成 |
| READY_FOR_SITE_DEPLOYMENT | FAIL | P2–P5和完整故障恢复验收未完成 |

## 必须继续的工作与缺口

本轮没有完成以下代码与验证，不把它们归因于“只差现场验收”：

1. P2 attachment → LocalScene → self-filter → planner/validator归属贯通，保护table/dock/隔板；尚未验证持物重复点云故障。
2. P3 HOLD_CANDIDATE/抬升后GRASP_CONFIRMED、原始夹爪时间戳；尚未验证不确定抓取的正式恢复。
3. P4 contact/lift原始与native路径、速度/加速度及stretch审计、同限制retimer；不能宣称115s/72s已修复。
4. P5统一start/SETTLING/ARRIVED、左臂最小只读失败恢复、资源互斥、TaskRuntime与WebUI/ART正式checkpoint/resume；100mm后恢复未验收。
5. 代表性场景CLEAR/AVOID成功、持物场景与19阶段GPU串联、各stage峰值GPU/RAM/耗时，以及完整故障矩阵。

10月16日缺失项仍包括三个web run（1792140369955017446、1792141460049419632、1792142393480633163）、pick/post-close/post-LIFT100 CAMERA/BODY原始点云及manifest、实际native contact/lift source+native轨迹和反馈/夹爪原始时间戳、confirmed_lift/finish_hold目录、最后130mm三个PLAN完整世界/请求/结果、AMR完成反馈及现场loaded模块/二进制/SDK实际证据。Ubuntu本地未找到这些运行包；没有为了找数据访问真实JAKA/AMR/Epic或其他GPU机器。

现场绝对路径Python、SDK/native sender和site commissioning仍需显式配置。不得把preview模型或9月proxy输入标成这些缺口已关闭。原始本机运行日志/轨迹留在gitignored `worklog/runtime/`；本报告与伴随JSON仅保存脱敏结果及源码哈希。

## 无硬件重跑入口

从仓库根目录、在可创建network namespace的宿主权限上下文运行。每次选择新的output目录：

```bash
scripts/offline_sandbox.sh python -m pytest -q
scripts/offline_sandbox.sh .venv/bin/python scripts/run_offline_contact_precheck.py
scripts/offline_sandbox.sh --gpu .venv/bin/python scripts/run_offline_gpu_replay.py \
  --synthetic-smoke --output worklog/runtime/NEW_GPU_SMOKE
scripts/offline_sandbox.sh --gpu .venv/bin/python scripts/run_offline_gpu_faults.py \
  --request worklog/runtime/NEW_GPU_SMOKE/CLEAR_00.request.json \
  --output worklog/runtime/NEW_GPU_FAULTS
scripts/offline_sandbox.sh python scripts/run_offline_cycle_replay.py \
  --output worklog/runtime/NEW_STATE_REPLAY
```

依赖版本、code commit、关键源码哈希、GPU统计及明确分层见 `2026-10-18_UBUNTU3080_REPLAY_RESULTS.json`。`--synthetic-smoke`不带时读9月历史场景；当前CLEAR/AVOID失败，脚本应以非零退出码保留失败，而非只检查“产生了JSON”。
