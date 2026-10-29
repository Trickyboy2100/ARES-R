# 新对象→新专机：阶段1准备与干涉修复

日期：2026-10-29。范围仅限新对象抓起、原路放回和返回起始center，不执行底盘或新专机放置。

## 结论

| 项目 | 状态 |
|---|---|
| 第二个Golden的完整取放结构作为后续流程蓝本 | 已保留，不在本轮执行 |
| branch的并行准备、滚动验证、Native缓存/反向复用 | 已进入新候选任务 |
| 新任务ID6贯穿采集及执行前确认 | 已实现并测试 |
| 原Golden四个固定核心及五份配置 | 保持不变 |
| 同事两个tmp副本 | 已保全，不修改 |
| 冻结ID6观测的接触IK、cuRobo、230mm与反向几何 | 通过 |
| 六段Native离线校验 | 通过；诊断副本不可执行 |
| SDK读批次/Native互斥与被动监控 | 已实现；占用探针返回409且不进入SDK |
| 当前Python与C++只读状态 | 正常，右臂工具1，队列空、已到位，Servo未激活 |
| center入口fresh环境/ID6诊断 | 5700启动后通过；非抓取epoch，抓取需回center后重采 |
| 本任务center语义 | 已明确选择全局named center；尚未执行回位 |
| 首次真实运动授权 | 尚未请求；未执行任何运动 |
| 新Golden | 尚未commission，仍为候选 |

## 交付位置

现场隔离根目录：`/home/yikun/ARES-R-RC1-20261019`。

- `demos/right_arm_shaiwang_pick_reset_v1/`：版本化参数、独立观测/准备入口、独立native源码、说明。
- `scripts/run_shaiwang_stage1.py`：inspect / prepare / preflight / execute / stop。
- `scripts/run_task_pick_reset_timing.py`：源自branch的任务编排adapter；不修改原golden入口。
- `src/ares_r/manipulation/task_live.py`：只初始化任务状态，其余I/O/验证/停止继承既有实现，不依赖旧完整取放构造器的固定ID1/ID3门。
- `src/ares_r/manipulation/task_contract.py`：同一ID6任务的参数、源码、原偏置、epoch、scene、点云与Native绑定。
- `src/ares_r/motion/controller_read_lease.py`：控制器会话串行互斥。
- `scripts/build_shaiwang_sender.py`：新二进制独立构建、库/源码/二进制哈希；不替换旧sender。
- `scripts/validate_task_native_offline.py`：只做离线格式/动态校验，不连接控制器。

## 真实发现与针对性修复

### 1. 隐式监控确有干涉风险

原ConsoleMonitor被状态GET懒启动，空闲时每约1.5秒调用robot_telemetry；tmp直接运行的native不一定属于canonical任务，监控可能继续登录同一控制器。
检查时确实看到RC1后台PID24129持有右臂10001连接，并有10000 SYN-SENT。
同事的check_no_console_polling只看monitor.samples/started_at_unix，而实际monitor字段不包含这两个键；它不能可靠证明没有监控，且GET本身会启动monitor。

修复：状态页只显示缓存/执行证据，不再隐式SDK登录。显式只读刷新、完整观测和native通过同一个既有右臂servo锁串行；SDK读批次之间也不能并发。
新task sender等候已有只读批次退出，超时则不开始，所有controller fault/estop/collision/limit检查保留。
只重载空闲8775/8776；8765/8766、ROS和相机共享进程未停止。
PID manifest原先与实际服务不符，已依据UID/cwd/argv/port核对并保全后更新，不按陈旧PID盲杀。

这些证据支持并发会话是实际风险，但不能据此声称昨天所有SDK -3/错误码都是假故障；还需新的受监督运动验证。

### 2. 只改采集ID不足以生成新任务

昨天一次ID6准备后，执行前又报ID1 target confirmation failed。新任务使用任务内config副本，把ID6贯穿采集、epoch绑定和执行前复核；生产system.json仍保持原ID1。
任务状态adapter不再在启动时依赖旧完整流程固定的pick1/place3校验，新专机放置暂不参与阶段1。

### 3. 微小起点差与原Native阈值不一致

昨天LIFT230被拒绝时J4最大差约0.022619°，旧sender阈值0.02°，并非cuRobo无解。
旧二进制、旧mode和阈值保留。新任务独立mode的上限为0.1°，同时检查首个采样的速度/加速度，仍保留工具/用户帧、排队、Servo残留、限位、控制器碰撞、deadline和1.5°跟踪停止。
不是把首点直接改成实际关节，也不做MoveJ跳转或重新插入临时路点。

### 4. 补偿与水平策略不再丢失或全局污染

新准备显式传入已有−10°补偿并生成compensation-proof。任务六维偏置只读。
现场曾把LEVEL环境变量改为无条件覆盖所有validate_level_path调用，可能污染其他任务。本轮改为只在新候选task scope生效，其他Golden继续使用显式/默认阈值。
新候选暂保留昨天副本的4.5°水平策略，记录实测值，不作为新的物理水平验收结论。

## 偏置核对（未写入修改）

- 原参数版本：`RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_19_V17_ROUTE810_ANCHORED_FIXTURE`。
- BODY任务六维偏置：`[0,0,0,0,0,0]`。
- 临时姿态补偿：TCP_LOCAL_Z，−10°；controller tool未修改。
- 旧烘干机下层中间泊位：DETECTION坐标系 `[0.315,-0.238,0.060,0,0,0]`，状态CANDIDATE，不可直接当成BODY偏置。
- 其余五泊位没有已保存的有效偏置。
- RC1 operations revision12；旧生产目录revision5，已有同一lower_middle数值。
- 新专机偏置本阶段尚未验收；未使用旧ID3/旧槽偏置自动放置。
- ID6筛网暂用旧持物模型，来源是2026-10-29明确确认；没有自动从点云重新膨胀成整块大模型。

## 冻结数据无运动回放

源epoch：`worklog/evidence/demo-runs/right_arm_shaiwang_grasp6_replace_reset_v1/run_1793170574041754936/epoch`。
输出：`worklog/evidence/20261029-shaiwang-frozen-replay/`。

| 阶段 | 秒 |
|---|---:|
| planner初始化（热态） | 0.545，和准备并行 |
| 接触几何/IK | 2.579 |
| cuRobo预抓取调用 | 4.263 |
| 包构建 | 0.340 |
| 230mm及反向几何 | 9.104 |
| 几何总准备 | 16.363 |
| 六段完整Native打包 | 约13.201 |

| Native段 | 计算运动时长/秒 |
|---|---:|
| pregrasp | 31.84 |
| contact | 6.56 |
| lift230 | 13.44 |
| lower230 | 13.44 |
| retreat | 6.56 |
| center（原路回起点） | 31.84 |
| 合计 | 103.68 |

103.68秒仅为计算轨迹时长，不含状态、夹爪、扫描、验证与服务调用，不能当作整轮实测承诺。
保持branch原速度/加速度来源与80ms Native采样；没有提高实机速度。
冻结数据不声称今天scene fresh。离线Native诊断仅在副本中更新过期时间字段，几何不变，副本无task-binding且execution_allowed=false，不能用于实机。

## 当日只读状态与真实阻塞

一次Python只读刷新：右臂errcode0、enabled=true、in_position=true、无estop/protective_stop/soft_limit；底盘IDLE，左臂有可信关节/工具状态。
独立C++ snapshot：工具1、queue0、active_queue0、inpos1、servo_active=false，约0.48秒完成并logout；未调用servo enable或任何移动接口。
文件锁模拟占用时，显式SDK读取返回409 `SDK_READ_DEFERRED_NATIVE_OWNER_ACTIVE`，未绕过互斥。

当日prepare输出：`worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793246751209822557/`。
1.23秒内失败，原始error=`[Errno 111] Connection refused`，并未形成新的SceneSnapshot，不是cuRobo超时。

另外，当前右臂TCP约BODY `[0.3448,-0.0741,0.9991]m`，是同事昨天返回的起点；全局named center为 `[0.3583,-0.0800,1.0278]m`，差约32mm。
最初center选择待确认；后续已明确选择全局named center，不采用当前起点。没有改写命名位姿或自动回位。

### 后续确认与center入口规划

5700已启动。ID6独立诊断成功，2.639秒，当前检测BODY约 `[0.669316,+0.074697,1.031276]m`，与昨日坐标不同。该诊断不作为center目标，也不假称与center环境扫描形成原子的抓取epoch。
center目标从named_poses读取，位置 `[0.358309303,-0.080000000,1.027835601]m`；零BODY偏置和已有TCP_LOCAL_Z −10°仅用于本任务目标，不修改全局。
CURRENT→center已通过现有SceneAwareMotion+fresh点云+cuRobo规划，Native包可执行。位置变化约32mm，姿态变化约4.33°。
计划ID `PLAN_240774de4b0b44208c1368897c859237`，轨迹哈希 `sha256:ed6455e6037e1f248b6ff4a3ee34c14532e285b78a2bcbd8a983571bb069c2b1`。
请求耗时16.349秒，规划worker约6.040秒；Native计算时长1.44秒、19采样，跟踪预测0.399°；未执行。
网页共享场景已有41个TCP轨迹点、9586个显示点云点。候选会正常过期，不能把本次预览当成永久执行许可。
证据：`worklog/evidence/shaiwang-center/plan_1793251616988833454/`。
新任务在prepare与执行前均核对全局center，末段再原路返回同一center；下一步先获得单独回center授权，再fresh准备前半程，不自动抓取。

## 验证与下一步

- 第一阶段全量无运动测试855项，OK，1项跳过，11.759秒；结果为tests-final-v3.log。
- 全局center入口补充后，现场全量无运动测试856项，OK，1项跳过，11.688秒；结果为tests-global-center.log。Mac任务专项18项单测通过。
- 原Golden九个固定输入按哈希核对；offset/config不改。
- 本轮没有发送机械臂、夹爪或底盘运动命令，未执行新Demo。
- 代码仍为独立候选分支，不push、不替换golden。

下一步：确认并执行已预览的回全局center动作 → fresh prepare和原始结果检查 → 请求新一次现场监督抓取授权 → 一次性执行完整前半程并记录故障/耗时 → 全部通过后再进入新专机识别/偏置/站位阶段。
