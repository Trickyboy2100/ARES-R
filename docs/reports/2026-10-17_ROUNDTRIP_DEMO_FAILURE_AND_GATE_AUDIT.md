# 完整抓放 Demo 耗时 故障与限制审计

日期：2026-10-17，Asia/Shanghai。审计对象为10月16日完整抓放联调及后续抬升恢复，不是一次新的现场测试。

## 结论先行

**这次联调没有达到可交付水平。主要问题不是机器人执行不了简单动作，而是已成功的能力没有被集成为一条经过真实数据闭环验证、耗时有界、可恢复的生产执行链。**

主要发现是：本地Demo副本FAST策略未被worker消费，但另一工作副本有实现，现场loaded版本尚待核实；调用方超时后求解仍继续；不同profile的GPU缓存叠加；接近/抬升可行性检查放在自由空间规划之后；抓取验证时序和点云语义不匹配；起点阈值上下层不一致；终点没有明确settle阶段；左臂只读SDK偶发失败升级为整任务故障；持物同时进入attached collision和环境点云；恢复靠现场新增脚本，而不是TaskRuntime中的正式状态迁移。版本分裂证据及根因限定见[推送前补充核查](../audits/2026-10-17_FAST_TIMEOUT_VERSION_SKEW_ADDENDUM.md)。

这些问题不应全部被称为“安全需要”。真正应保留的是控制器急停/碰撞/限位/有效状态和可证明的几何、动态约束；**实现缺陷、重复验证、隐藏常量、错误模型、丢失错误原因、无恢复入口不等于安全。**

本轮只读本地代码和已有资料，生成审计文件。没有连接`.32`，没有改生产配置、阈值、控制器或运动程序，没有推送。

### 审计包

- 本文：故障复盘、限制台账、责任和决策。
- [逐阶段执行参考](../audits/2026-10-17_ROUNDTRIP_EXECUTION_REFERENCE.md)：19阶段、每个调用入口、输入输出、时序、资源、估算、复现合同。
- [返场1至2天计划](../roadmaps/2026-10-17_ROUNDTRIP_1_2_DAY_DASH_PLAN.md)：优化顺序、建议决策、验收、停止研究型扩展。
- [函数位置索引](../../worklog/audits/2026-10-17-roundtrip-offline/FUNCTION_INDEX.md)：关键66份源码中的函数、签名、起止行。
- [完整静态索引](../../worklog/audits/2026-10-17-roundtrip-offline/source_inventory.json)：272份文件、1443个函数、2680个条件分支、1420处显式raise、149项等待/超时调用。**这些是静态审查候选，不能把2680个分支说成2680个正在阻断本Demo的门。**
- [证据数值账本](../../worklog/audits/2026-10-17-roundtrip-offline/chat_evidence_ledger.json)：本对话已读取的现场日志数值，注明不是原始日志副本。
- `worklog/audits/2026-10-17-roundtrip-offline/source_snapshot/`：66份关键源码的本地冻结副本。
- `SOURCE_SHA256SUMS`：包括配置文件在内的本地文件哈希。没有把共享账号秘密或全套站点配置明文归档到新目录。

### 证据等级与边界

| 标记 | 含义 |
|---|---|
| LOCAL_CODE | 本轮实际读取的本地源码/配置，可用SHA256定位 |
| CHAT_TOOL_EVIDENCE | 上轮对话里实际工具读到的现场结果，本轮未重取原文件 |
| LOCAL_ARTIFACT | 本地已有文件，例如早期Mock结果、底盘独立往返JSON |
| INFERENCE | 根据代码或现象推断，尚非现场根因认证 |
| ESTIMATE | 预算/资源/时间模型，不是实测p50/p95 |
| UNKNOWN | 缺少现场原始数据，不能补造 |

本地工作树：`ARES-R-offsets-20261016`，分支`codex/offset-frame-switch-20261016`，HEAD `9ff45177fdf9cbcde6e002cb6cffe630f7fe35e5`。现场代码包含其后未提交/未跟踪的修改，**只报HEAD不能复现实际运行源码**。以本审计的文件哈希和冻结源码补充说明；它仍不是10月17日`.32`实时状态。

本地还存在大量` 2.py / 2.json`重复副本；索引主动排除了这些名字，避免把备份当运行模块。正式模块、dirty patch、恢复脚本应在返场前统一打包，不能仅凭Git commit宣称已完成。

## 一 现场到底花了多少时间

### 可确认时间线

以下时间由对话里工具输出的Unix时间转换为Asia/Shanghai；不是从记忆估计。

| 时间 | 事件 | 实际结果 |
|---|---|---|
| 15:52:20 | 本地最早保留的该Demo Mock目录时间 | 只能证明已有回放产物，不代表实机就绪或设计开始时间 |
| 16:46:10–16:49:02 | 第一次完整任务启动 | 172.0秒，FAST超时、QUALITY两次显存不足，未运动 |
| 17:04:20–17:08:37 | 清显存后第二次启动 | 257.3秒；cuRobo成功，构建抓取执行包时接触IK失败，未运动 |
| 约17:17:06–17:17:16 | 用户批准左移10cm | 正式接口报告SETTLED；新GRASP命令路线更新为横移85cm，PLACE未改 |
| 17:19:53 | 新GRASP启动第三次完整任务 | 新扫描，正反抓接近+100mm抬升离线IK均通过 |
| 17:23:52–17:24:32 | MOVE_PREGRASP | 实际阶段约39.52秒；文件规划时长36.08秒 |
| 17:24:32–17:24:33 | GRIPPER40 | 约1.25秒 |
| 17:24:33–17:26:32附近 | CONTACT_APPROACH、随后闭爪 | 接近文件1439点×80ms，对应115.04秒；两事件之间约118.90秒还含收尾和闭爪，不能全部算接近纯运动 |
| 17:26:32–17:26:42 | VERIFY_GRASP | 点云变化被归为CHANGED_UNEXPECTED，约10.23秒后FAULT |
| 之后 | 人工确认抓稳，现场补恢复入口 | 出现左臂只读异常、原生起点不匹配、日志路径冲突；均未开始这次恢复的运动 |
| 17:34:31–17:35:46 | 从实际关节重建100mm抬升后执行 | 实际抬升约100mm；末拍final feedback mismatch，abort/servo disable返回0 |
| 稍后 | 只读复核抬升终点 | 控制器到位、无故障；最大关节残差约0.0000046° |
| 17:42:36–17:43:33 | 余下130mm规划 | 约57.34秒，三次起点碰撞；没有发剩余运动 |

从第一次一键启动到上述余130mm失败，跨越约**57分23秒**。从最早保留Mock目录时间到该失败跨越约**1小时51分13秒**；后者不是纯运行耗时，也不能当作精确“设计耗时”。

**三个主任务运行窗口合计约838秒，即约14分钟。加上已确认的一次100mm恢复窗口和最后130mm尝试窗口，约971秒，即16分11秒。** 与57分23秒窗口之间还有约41分钟，包含分析、文件检查、用户往返、改代码、部署、重载、独立采样、准备和未逐段计时的操作；不能把这些全部归因于GPU，也不能全部称为“机器人等待”。

本次有明显的工程和代理操作开销。其精确分项缺少完整工具时间线，标为UNKNOWN；不能用少数solve耗时解释整个小时。

### 三类时间必须分开

1. **软件端到端**：点击→观测→排队→初始化→求解→验证→打包→执行许可→首条ServoJ。
2. **物理运动**：首条ServoJ→终点稳定；底盘首动→停稳；夹爪下发→稳定读回。
3. **联调人工和开发**：提问/确认、查日志、现场改脚本、部署/重启和解释。它们不能成为客户正常周期的一部分。

后续UI必须同时显示这三类；“规划用了112秒”既不能解释全周期，也不能掩盖前端到首动的延迟。

## 二 首要根因 与应纠正的先前判断

### R1 FAST策略没有真正接到这条worker的求解入口

**范围限定：下面指本审计冻结的offsets副本。另一本地operations副本已含FAST实现，不能据此直接断言现场进程实际漏接；参见[版本分裂补充](../audits/2026-10-17_FAST_TIMEOUT_VERSION_SKEW_ADDENDUM.md)。**

`scripts/run_grasp_place_roundtrip.py:104`写入`solver_policy=FAST_SINGLE_PASS_V1`、initial_iters和max_goal_candidates。`scene_aware_planner.py:34`也会构造相似policy。

但本地冻结的`production_scene_worker.py:299`实际调用`planner.plan_cspace(... max_attempts=params['max_attempts'], enable_graph_attempt=...)`；其`main()`没有消费`solver_policy`、没有调用`latency_solver.solve_single_pass()`，也没有按该字段截断goal candidates。后者虽存在并有测试，**并不证明现场完整Demo使用了它**。

可用本地命令核对：

```sh
rg -n 'solver_policy|solve_single_pass|plan_cspace' src/ares_r/motion/production_scene_worker.py src/ares_r/motion/latency_solver.py
```

4/2 seed和CUDA graph字段仍可能被消费，不应说FAST全部字段都无效。问题是“单次快速solve/候选数量/iteration/距离backend”的完整合同没有落实。运行日志里的`planner_clearance_policy`又来自通用profile，曾显示8/8、graph=false，与请求字段不一致；**那是元数据不可信，不能单凭它推断实际用了哪组seed。**

建议：统一worker入口，输出`effective_solver_config`，并对实际调用次数、候选数、CUDA graph实用状态做集成测试。不是继续调小FAST超时数字。

### R2 4秒是等待超时 不是后端计算截止

`planner_service_client._call()`设置socket timeout；`persistent_planner_service.serve()`串行处理连接，调用worker后才响应。客户端离开不取消GPU任务，服务只在写回时吞掉BrokenPipe/ConnectionReset。

第一次FAST调用超时后，worker实际又完成了约80.25秒的完整请求并写出SUCCESS。后续QUALITY可排队等这个“已被放弃”的任务。**迟到的成功不能自动执行，但也不应让它继续占用关键路径。**

需要真正的job ID、单一deadline、排队/运行分离、取消确认、无孤儿求解；若GPU API不可中断，可由独立单任务worker回收上下文，但须评估冷启动，不应把整个控制后台一起重启。

### R3 长驻进程不等于长驻单一planner 更不等于显存有界

worker的`_RUNTIME_CACHE`按robot+spheres+parameters+orientation_lock+collision capacity生成key；profile、tool、attached geometry变化都可能创建新planner。FAST、QUALITY、空载/持物等缓存可以并存，代码没有显式LRU容量或显存预算。

显存实测：GPU约11.66GiB；worker占约9.93GiB时申请1.03GiB，但只剩991.88MiB；另有同事/原系统pose estimation进程约680MiB。只重启空闲planner后，总可用显存从约992MiB回到11163MiB，证明显存回收有效，**不证明求解链路已经提速或全链可运行**。

候选重试不能把OOM原样再跑一次。应先确认任务已结束、释放失败profile缓存，再按同一任务预算降资源或报告RESOURCE_EXHAUSTED；不能擅自杀其他人的进程。

### R4 先花几分钟规划 再检查最后55mm是否能抓到

自由空间cuRobo规划终点是pregrasp，接近和初始抬升在`build_first_pick_execution_package.main()`里用`RuntimeGoalIK.solve()`另行生成。全链原子分支能力没有被这条新Demo正式复用。

第二次任务：自由空间QUALITY请求约159.53秒，随后构建contact时才发现误差。有限离线复现里，第17/26点开始失败；终点误差逐步增至约7.51mm/2.66°。另外一组姿态的有限多初值测试也没找到合格解；这**不是物理不可达的数学证明**。

左移10cm后重新检测，同样的两种grasp symmetry均能通过接近+100mm抬升IK。说明目标/站位/分支确实改变了可行性，不是只有一个任意阈值在挡。

正确顺序应为：观测→有限多分支IK/接近/抬升可行性→选择小top-k→cuRobo自由空间验证→不可变包，而不是先规划再发现接触段不能执行。

### R5 验证失败的精确原因不只是“物体尚未被抬走”

`verify_grasp_v1`先判断added_fraction是否超过0.50；本次是0.520408，因此返回CHANGED_UNEXPECTED，`LOCAL_SCENE_OBJECT_REMOVED=false`。removed_fraction为0.666667，本身超过0.15要求。夹爪37/37/37稳定且高于闭合阈值，两个夹爪gate均通过。

先前“抬升前却要求物体消失”的解释指出了时序问题，但不够精确。准确结论：**算法在抬升前，用两个分别自体过滤后的场景的增删体素变化来证明抓取，夹爪伸入、遮挡、物体状态变化都可能产生新增体素；CHANGED_UNEXPECTED的全局分类覆盖了removed判定。** 不能从这个FAIL直接推断“抓空”。

另有证据质量缺陷：`verify_authorized_first_pick.py:33`在读入三次读回后，给三条记录赋同一个`now`，并硬编码delay/radius/voxel值。配置看似可改，实际脚本未全消费。应保存原始采样时刻，并拆成闭爪后的HOLD_CANDIDATE与安全小抬升后的GRASP_CONFIRMED。

### R6 起点与终点合同不统一

上层`Live.pick_segment()`允许0.2°起点差；C++ sender只允许0.02°。本次0.03551°通过上层，原生拒绝。**这不是同一条安全原则的合理重复，而是上下层合同不一致。**

C++最终检查在最后一次发送后的下一周期做一次读取，以40ms读取预算和0.05°终点差判断；没有独立settle状态。100mm抬升末拍触发final feedback mismatch，停稳后误差约0.0000046°且控制器到位。应区分ACTIVE_TRACKING、SETTLING、ARRIVED、真正FAULT；在受控且有界的settle窗口内继续监测，而不是立刻把正常跟随尾差升级为全任务失败。具体窗口/容差返场验证，不能离线宣布新数值已commission。

### R7 持物世界没有闭合

`Live.attach()`给后续规划传入coarse attached-object collision；但`SceneAwareMotionService.plan()`在调用`LocalSceneService.ensure_fresh()`时，仅传active_arm和scene policy，未把attachment交给点云自体过滤。

结果可能是：**规划机器人上挂着持物几何，fresh点云环境里又有同一持物。** 本次剩余130mm起点gap约−62.26mm，终点gap约+45.98mm；主要相交对象是当前扫描生成的protruding primitive。

现场认为它就是持物，重复建模与代码结构吻合；但本轮没有逐点归属认证，不能把所有负距离都等同于“肯定是自体”。当时提出的200mm持物自体过滤在中断前**没有实现**，不是“已经打开但还在误挡”。

正确修复是attached-object geometry由同一backend同时进入overlay、自体过滤、cuRobo和独立验证；TCP周围200mm可作有界候选区，实际删除应有持物归属。盲删整个球会把临近dock、隔板也删除，不适合作为默认生产策略。

### R8 短暂只读异常缺少恢复状态

`Live.telemetry()`要求`errors`完全为空，左臂`get_robot_status()`偶发SystemError即停止右臂任务。左臂inactive仍需真实关节/工具以构建障碍，但不意味着整个庞大SDK诊断包里的每个字段都必须成为每次右臂运动的前置必要条件。

已加的局部补丁：只对左臂只读、motion_enabled=false的状态解码SystemError做一次重连，不重连控制会话，不伪造状态；12项相关测试通过、三次现场遥测无错误。**这是局部取证，不是长期可靠性认证。** 仍需把碰撞所需最小状态与详细诊断分开，必要时复用独立native只读读数。

### R9 恢复入口不是正式Runtime能力

没有正式RESUME_FROM_VERIFIED_CHECKPOINT。为了继续100+130mm，现场新增`resume_confirmed_grasp_lift.py`、`finish_confirmed_lift_hold.py`，还出现旧native日志`open('x')`冲突；恢复次数/失败类型被写进脚本特殊分支。它们是诊断/临时恢复产物，**不能当作交付结构**。

还存在UI一致性问题：这些恢复进程通过`active.json`可让global stop感知，但RoundtripLauncher的`web_launch.json`和`_running()`仍跟踪原脚本，网页可能继续显示旧FAULT。恢复没有进入同一个canonical task/job状态机，客户无法判断“到底还在不在跑”。

### R10 测试和现场放行之间缺少一层

Mock全链通过，只证明调用顺序和参数；631项测试通过不等于这次现场场景、工具、轨迹、SDK和速度组合全部commission。

实际缺少的是用冻结成功实物数据做完整adapter dry-run：能否真正消费FAST策略、接触段是否通过、起点/终点合同是否一致、持物点是否自体过滤、执行日志目录是否唯一、故障能否从正式checkpoint恢复。

## 三 Codex接手方式也造成了延误

1. **把入口可点、Mock通过和可完整实机执行混在了交付节奏里。** 虽报告曾标注未commission，但没有在“一键开始”之前完成真实adapter闭环的最短必测清单。
2. **清显存只解决了资源症状，随后仍启动已知FAST超时取消缺陷未修的链路。** 应提前说明本次重试仍可能排队，并先隔离测同一接口的deadline行为。
3. **错误解释过早。** 曾把结果metadata里的8/8当成实际FAST参数，后续才核对真实请求；曾先说contact误差略超阈值，后续才算完整段发现误差增长。应先取完整证据再定性。
4. **现场新增多次性恢复脚本。** 这些脚本带来日志冲突、UI状态分裂和前置读数失效，增加“修复修复本身”的时间。
5. **没有把人工抓稳确认作为预先设计好的、范围明确的实验状态迁移。** 人工确认不等于取消所有保护；但应有一次性签字/事件、清晰替代哪个低置信度验证、哪些约束仍生效，而不是临场反复争论和改路径。
6. **没有提前区分实验模式和生产模式。** 现场应能选择明确的held-object过滤、已审核局部实验模式、诊断不阻断项；控制器急停/限位/实际故障不能跟模型不确定性共用一句“不能”。
7. **没有及时给出统一根因和完结边界。** 用户看到每清一项就出现下一项，软件应把可预知阻塞在运动前一次汇总，而不是每阶段再临时发现。

后续目标不是承诺“所有override必执行”，而是**把合法的现场实验授权、信息不确定性和不可绕过的控制器故障边界，提前写成可审计策略，减少临场判断和对话依赖**。

## 四 限制台账

分类：`P`=物理/控制器基础保护；`B`=场景/状态/工具绑定；`M`=模型与算法有效性；`E`=工程实现门；`D`=诊断/显示，通常不应单独阻断运动。分类是建议审计维度，不表示已经修改。

### A 启动 授权 占用与停止

| ID | 门或阻塞 | 位置 | 审计判断 |
|---|---|---|---|
| G01 | 页面现场确认框、can_start、JS busy | `webui/roundtrip_panel.js` | E；保留一次明确授权，禁用必须显示具体原因，不只灰按钮 |
| G02 | authorization字符串、onsite=true、contract SHA | `demos/roundtrip_launcher.py:92` | B/E；授权绑定正确，但ART/WebUI/恢复不应三套口令逻辑 |
| G03 | stop.request锁存 | launcher:40、runner:42 | B；区分人工Stop、控制器故障、规划失败，不能全部变成不可解释的人工解锁 |
| G04 | review_approved=false、TTY | runner main:352附近 | E；Web启动靠独立批准副本+PTY解决；不能要求长期改生产false为true |
| G05 | 参数、路线、slot offset revision一致 | launcher.contract/start；Live.place_target | B；必要，显示变化来源；正常UI版本号变化不应误伤 |
| G06 | 资产存在、SDK Python/native binary | launcher.contract；prepare | E；开机预热前一次完整检查，不到执行时才缺文件 |
| G07 | web cycle token、process占用 | launcher.check_physical_access；canonical_backend | B；必要，但恢复进程必须纳入同一ownership |
| G08 | run.lock与原生`/tmp/ares-r-right-servo.lock` | runner.main；C++main | B；避免双写；需明确owner、可读状态，不盲杀占用者 |
| G09 | output目录必须不存在、日志open('x') | runner.command、多处生成器 | E；保留证据不覆盖，但每attempt/job唯一目录，不应因旧日志卡正常恢复 |
| G10 | active.json与web_launch.json两个状态源 | launcher、runner、恢复脚本 | E；应单一task/job真相，消除旧FAULT与新运动并存显示 |

### B 配置固定值与任务策略

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G11 | right active、left HOLD_CURRENT、禁止并发 | `manipulation/roundtrip_demo.py:11` | B/P；本客户Demo范围，保持串行，不扩双臂同步研究 |
| G12 | ID1/ID3命令完全相等 | 同上:14 | B/E；当前防错；未来注册profile而不是重复字符串 |
| G13 | planning_attempt_modes必须FAST/QUALITY/QUALITY、deadline必须4 | 同上:20–27 | E；这些是策略不是物理极限，应versioned schema，不用改Python才能调 |
| G14 | 初始contact lift只能100mm、总高分解一致 | 同上:28 | M/B；这是当前已审contact语义，不等于230mm应被禁止；应明确100+130各自路径 |
| G15 | lift速度/加速度≤0.20、base≤0.10 | 同上:32–38 | P/B；必须说明是版本/站点限制，不是cuRobo算力限制 |
| G16 | preland在0–100mm、gripper raw0–1000 | 同上 | B/M；单位、实际开度要可见 |
| G17 | 路线revision白名单且段值完全相等 | recipe:45–53 | E/B；本轮改75→85cm必须同时改Python，属于交付不灵活，应改审核后的数据驱动路线 |
| G18 | 无stow、无底盘/臂并发 | recipe、parameters | 现场已选策略，当前不重新引入收臂或并发 |

### C 观测与场景

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G19 | 5700成功、pose存在、profile匹配、right/用途正确 | observation_transaction.capture | B；必要，但错误需保留原文、space/object/camera和有效pose数 |
| G20 | before/after双臂六有限关节、变化≤0.25° | 同上 | B；观测稳定性，不是Servo起点容差 |
| G21 | before/after各两臂FK audit，加scene内部两臂audit | capture脚本+p32 | E/B；一次成功pick观测可达6次arm audit，必须拆验收/快照，不每次跑完整校准基线 |
| G22 | 5700后才执行5000 scene采集 | 旧ObservationTransaction | E；V2并发能力存在但这条入口仍走V1；不能直接并发争用同一相机，需先验证项目资源互斥 |
| G23 | CAMERA mm→m一次、固定外参、manifest/hash一致 | body_pointcloud、live_scene | B；必要且不重ICP |
| G24 | body ROI `[.22,-.76,.70]`到`[1.30,.76,1.40]m` | scene_aware_motion.json | M；不是物理安全边界；ROI外未知不能当空，盒子/层板需hold-out |
| G25 | early voxel7.5mm、radius清理、support分解 | p32、build_p3、perception | M/E；速度/小物保留折中，须有删点/保留统计，不凭画面干净决定 |
| G26 | robot self-filter30mm、gripper40mm | 配置+p32 | M；建模/传感误差，不应与planner clearance混用或多重膨胀 |
| G27 | target coarse primitive忽略规则 | prepare_authorized_first_pick | M/B；当前按target组件前缀忽略，可能过宽；需要证明不是连通dock一起删 |
| G28 | central exclusion当前OFF，历史半宽70mm | site/profile/operations | M/B；OFF不应仍计算并要求有限margin；需审计所有入口统一 |
| G29 | AMR/臂动作invalidate；TTL300秒；active arm一致 | LocalSceneService | B；必要；arm只动后是否每次全重扫要按环境依赖而非机械重复决定 |
| G30 | fresh scene失败一律停止 | local_scene.scan | B；可有只读重试/硬件重连，不使用旧scene自动续走 |
| G31 | attached geometry未传入self-filter | SceneAwareMotion.plan→ensure_fresh | M/E；当前直接阻塞的核心缺陷，不是加大间隙能解决 |

### D IK 分支 姿态与接触窗口

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G32 | NORMAL/FLIPPED_180，历史goal只作seed | prepare_authorized_first_pick | M；应在规划前检查全链而非只pregrasp |
| G33 | IK position≤1.5mm、orientation≤0.6° | RuntimeGoalIK.solve:34 | M；先报告实际误差曲线、分支和约束；不能仅说“不安全” |
| G34 | 关节URDF边界内缩0.02rad | RuntimeGoalIK.__init__ | M/B；注意这是约1.146°，不是原生0.02°，两者不可混淆 |
| G35 | least_squares max_nfev90，正则`.0005*(q-seed)` | 同上 | M/E；数值求解失败不是不可达证明；有界多初值与连续分支应前置 |
| G36 | contact26点、lift51点、固定姿态 | build_first_pick_execution_package | M；可做受约束cuRobo接近，但不能把普通任意绕路cspace当直线contact |
| G37 | bypass仅指定manipulation stage、active tool/观测世界配对 | ContactBypassPolicy | B/M；不应关闭臂体、非目标结构或controller保护 |
| G38 | contact/lift长度约≤101mm、侧偏≤2mm、单调、最低25mm | validate_bypass_segment | M；当前100mm语义有界，230mm应另有free-space持物模型 |
| G39 | arm links对world、自碰撞、inactive arm、joint limits | 同上 | P/M；模型必须一致，粗OBB重叠应归因而不是盲增margin |
| G40 | 全程水平≤3°，yaw目标0 | Live._level、tcp_orientation、planner lock | M/任务质量；水平和yaw应拆开，yaw固定可能降低可行性；必须尊重本次已定任务语义 |
| G41 | level manifold无连续seed则FAIL；max IK step等 | production worker | M/E；只在该请求启用时生效，不能把这个历史门说成每次都触发 |

### E cuRobo与独立验证

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G42 | requested FAST4/2、graph=true；QUALITY8/8、graph=false | latency/profile/site | E；须输出effective参数，不靠配置名推断 |
| G43 | 最大attempts来自site；goal_candidates与benchmark_runs循环 | worker.solve/main | E；一个UI请求可能多次solve，必须逐次计时并有全局预算 |
| G44 | 每个新runtime一次full warmup solve | worker:319–327 | E；generic QUALITY仍可触发，失败warmup也会标warmup_done；应服务启动预热而非每个任务丢完整解 |
| G45 | FAST socket4秒、QUALITY240秒 | client/runner | E；没有全任务deadline；三次重试并非总计12秒 |
| G46 | CUDA OOM / 内存无界缓存 | persistent worker | E；资源失败不应机械重试相同配置 |
| G47 | start/goal碰撞、self collision、whole-arm world | cuRobo+worker | P/M；真实碰撞拒绝应保留，模型错误必须先归因 |
| G48 | preferred=0mm、hard floor=0mm、optimizer activation=30mm | scene profile | M；三个数不同。preferred0不等于关闭碰撞或关闭最小距离计算 |
| G49 | 每障碍CPU距离：起点、终点、101点baseline、dense路径 | worker.clearance_by_sample等 | E/M；GPU→CPU及重复全量扫是耗时源，诊断全量min不应无条件阻塞；替代验证需先对照验收 |
| G50 | dense subsamples4、batch128及orientation再验 | worker+Live | M/E；必要性按同一contract统一，已验同hash不应重复昂贵计算 |
| G51 | ignored cuboid ID不存在即错误 | worker | B；防止错删；不要用固定cluster ID作为长期身份 |
| G52 | runtime cache key含全部parameters/spheres/orientation/capacity | worker | E；频繁变化破坏复用、叠显存；应按受控profile和容量管理 |

### F 打包 速度和原生执行

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G53 | 80ms固定采样，2–10000点，≤240秒 | native_execution_package+C++ | P/B；当前sender合同，不可只改上层参数 |
| G54 | velocity/accel取site、native、tracking、stage最小值 | package_native_preview | P/B；UI的0.2rad/s是上限，不等于运动平均速度 |
| G55 | 折线保几何重采样、geometry error≤1e-8 | native_demo.resample_for_native | M/E；关节折点的离散加速度可导致大幅time dilation，重点优化时间参数化/源路径平滑而非只抬velocity cap |
| G56 | max_excursion默认150°，本pick传220° | packager+C++ | E/B；历史150门仍有旁支，不应误称全局已删；按实际sender及关节范围统一审计 |
| G57 | tool ID=1、tool offset1e-6一致、user ID=0 | Live/C++ | B/P；工具变更不能无声继续；应统一单位及允差 |
| G58 | package digest、sender binary SHA相等 | verify package/sender | B；保留但同hash可缓存验证；v5/v6文件名是否相同二进制本轮未核实 |
| G59 | 上层起点0.2° vs native0.02° | Live.pick_segment:156、C++:140 | E/P；实测触发，优先统一，不直接删除起点绑定 |
| G60 | inactive-left变化≤0.02°且tool ID一致 | Live.pick_segment | B/M；与观测稳定0.25°不同用途；需容差来自误差预算，不混用数值 |
| G61 | native idle、servo未开、queue为空、inpos | C++main | P；保留，给出忙的owner或残留会话，不静默清控制器队列 |
| G62 | 实时跟踪≤1.5°，对比上一条目标 | C++sample loop | P；不是IK误差、不是到位误差，不能用一个“偏差阈值”全局改 |
| G63 | 读发单周期≤40ms、deadline lag≤40ms | 同上 | P/E；必须测网络/调度/日志负载；非实时证据写盘不应压入该周期 |
| G64 | actual TCP displacement cap、joint/site limits | 同上 | P/B；本long motion上限与微动不同，UI应显示实际mode |
| G65 | 父进程丢失、信号、日志写失败即abort | 同上 | P/E；合理监督，但磁盘满/pretty日志可成为运动故障源，需队列/背压设计 |
| G66 | final一次读取≤40ms且关节差≤0.05° | C++终点 | E/P；实测过早失败，增加有界SETTLING状态而非忽略真实故障 |
| G67 | 必须target_reached、servo_disabled=0、不能有failed/abort | Live.pick_segment | B；上层缺少“已到位但结束确认失败”的正式核验恢复路径 |
| G68 | snapshot时间≤300秒，controller safety状态 | C++load/read | B/P；过期必须对原scene/起点真实绑定，不可重写时间就当场景变新 |

### G 抓取 放置与底盘

| ID | 当前条件 | 位置 | 审计判断 |
|---|---|---|---|
| G69 | 串口1秒响应、长度正确、readback | gripper_direct_once | P/B；当前脚本未完整校验所有帧字段/校验和，详见执行参考，不把裸raw当可靠持物认证 |
| G70 | open命令后0.75秒、raw容差20 | Live.gripper | B/M；开爪稳定时间可按读回到位提前结束，不能只固定sleep |
| G71 | delayed read [.25,.75,1.5]、spread≤20、hold>closed+20 | verify scripts | M/B；实际原始时间戳应保留，不能事后批量赋now |
| G72 | scene delta radius150mm、voxel5mm、removed≥20/15%、added≤50% | verification config+脚本 | M；时序/遮挡问题已实测，合理改验证设计而非把所有图像变化当抓空 |
| G73 | verified才lift、attach后才free-space | recipe | B；可有一次性人工确认替代视觉证据，但不能顺带取消controller等无关门 |
| G74 | attached revision/hash、所有几何消费者一致 | attached_collision+planner | B/M；应同时自体过滤，否则自身阻挡自身 |
| G75 | fresh ID3成功、offset未变、base revision未变 | place_target | B；目前非统一place ObservationTransaction，必须补齐前后状态/观测绑定 |
| G76 | slot+40mm直接释放，不下降 | recipe/parameters | 现场接受的实验语义，不是力控放置；实际物体落差不等于TCP40mm |
| G77 | base request accepted后必须observer SETTLED | CanonicalBackend.base_move | P/B；保留真完成，不用accept充到站 |
| G78 | runner又等fresh completion marker+5稳定样本 | Live.base | E/B；与backend observer重复，通常额外约2–3秒/段；选单一完成真相 |
| G79 | 每段base总超时60秒、map不变、无yaw | Live.base | B/P；大段85cm在0.1m/s名义8.5秒，不应因SLAM小漂移盲补移动 |
| G80 | base_stationarity看IDLE+marker稳定，SLAM map稳定另报 | live_state | B；保持位置可信度语义，不把noisy SLAM当精密验收 |
| G81 | 每程fresh scan/scene与基础版本绑定 | LocalSceneService/scene execution | B；能共用同epoch的检测与scene，不要相邻两个接口重复扫同一不变场景 |
| G82 | 释放后不收臂原路返回 | recipe | 现场已授权特定扫掠；软件不能把长期任意姿态的扫掠也标commissioned |

### 补充 容易漏掉的有效数值来源

| ID | 发现 | 审计判断 |
|---|---|---|
| G83 | 本地`jaka_mini2_motion.site.json`每轴max_velocity为0.10rad/s，但Demo/profile写0.20 | packager取最小值；除AB专用分支会抬site副本外，generic/pick未必实际到0.20。必须取现场hash+native audit，不能把本地0.10当10月17日现场定论 |
| G84 | site soft_limit_margin为0.087266rad=5°，IK模型内缩0.02rad≈1.146° | IK可能通过而native package再因更大soft margin拒绝；统一有效joint margin并前置报告 |
| G85 | site max_start_error_rad=0.03rad≈1.719° | 并不支配这条native路径；不能修改它就声称0.02°起点门已改变 |
| G86 | supervised tracking预算1.48°、lag模型0.12秒，速度预算约0.215rad/s，再受0.20上限约束 | 这是模型推导，不是控制器实测时延；不能与legacy0.18°预算混用 |
| G87 | native resampling最多200次，stretch最少乘1.02、最多每轮乘1.6 | 可能引入CPU打包成本和过度拉时；要求输出最终stretch与限制轴 |
| G88 | `body_pointcloud.capture_body_cloud()`每次还做support-table拟合与artifact/hash | 不是重新标定外参，但仍有额外CPU/IO；应分项计时 |
| G89 | 相机fast worker socket超时可fallback one-shot；场景、planner和SDK各有不同环境 | 快路径失败后可能悄悄变冷/变慢；应显示effective capture path、Python版本和fallback原因 |
| G90 | generic native packager对left直接拒绝，right speed scope/state也检查 | 是当前commission范围，不是左右控制器能力差异；别把旧AB profile强塞到其它模式 |

### H 历史门 不能混成这条Demo的真实调用

仓库还存在P3.3候选30mm minimum、precision0.015rad/s、AB专用限制、150° envelope、V1/V2 trajectory、ExecutionLease、SkillRuntime资源锁和旧terminal硬件开关等。完整静态索引包含这些，但**是否执行必须看实际调用路径**。

例如`DualArmSafetyKernel.preflight_execution_candidate()`里的旧P3.3 diagnostic不能直接代表本次`Live.pick_segment()`的路径；后者直接走已验证package+native sender。通用`GenericNativePackager/preflight`则确实用到generic collision gate和scene/state绑定。不能用“底层有SafetyKernel”掩盖两条执行路径不统一，也不能为了清旧门把未调用历史分支全部删掉。

## 五 override和实验授权应如何正式落地

以下为待审设计，不是已经修改的软件：

- 单次manifest写明：哪项自动结论被人工替代、当前物体/站位/姿态、有效时长、最大动作、速度、起点和工具版本、哪些门仍保留。
- `OPERATOR_CONFIRMED_GRASP`可以替代指定视觉抓稳判据，不自动代表left状态、attached geometry、控制器到位或后续任意场景都已验证。
- `MANUAL_SUPERVISED_EXPERIMENT`必须是明确产品模式：可配置感知是否参与、局部模型如何使用、有界命令和停止。不能靠Codex临时改代码、删障碍或改native常量。
- 点云分三类：ROBOT_OWNED、ATTACHED_OBJECT、EXTERNAL。错误归属是模型缺陷；不应用通用margin去掩盖。
- 关键限制要在计划前一次汇总，显示实际值、来源、失败对象和可采取动作。不要只返回409、SystemExit2或“不安全”。
- 现有controller急停/碰撞/限位/故障、非有限反馈、实机资源互斥和真实硬碰撞不应被无差别关闭。这里不承诺所有现场override都必须自动执行。

## 六 返场前应先审的十项决策

| 优先级 | 决策 | 建议 |
|---|---|---|
| P0 | 是否停止继续维护临时恢复脚本为主线 | 是；保留证据，正式恢复回TaskRuntime |
| P0 | 是否统一FAST真实调用和绝对deadline | 是；4秒不是把socket数字写成4 |
| P0 | 是否前置contact/lift全链分支可行性 | 是；先小成本排除不能抓/抬的分支 |
| P0 | 是否加入attachment-aware点云self-filter | 是；以同一持物geometry为事实来源 |
| P0 | 是否将终点分为SETTLING/ARRIVED/FAULT | 是；有界，不直接增加动态tracking阈值 |
| P0 | 是否拆分抓取验证并支持一次性人工确认 | 是；修时序和时间戳，保留审计 |
| P1 | 是否废除重复全量CPU最小距离报告 | 先对照验证再从同步主路径移出诊断；硬碰撞验证保留 |
| P1 | 是否审计时间参数化导致115秒接近 | 是；不能只提高velocity cap |
| P1 | 是否把路线、profile、stage限制真正数据化 | 是；审核后的85cm路线不应依赖改Python白名单 |
| P1 | 是否把客户正常周期设计为不需要Codex逐步介入 | 是；UI只是客户端，runner自主推进和恢复 |

详细工期、测试和周期预算见[返场计划](../roadmaps/2026-10-17_ROUNDTRIP_1_2_DAY_DASH_PLAN.md)。这轮只列审计建议，没有实施上述优化，也没有宣称“下一次必成功”。

## 七 尚缺的现场原始材料

为了将上述CHAT_TOOL_EVIDENCE升级为可复现原始证据，返场后仅做归档：

1. 三个`web_*`完整run目录及对应`logs/roundtrip-web-*.log`。
2. 该次所有`confirmed_lift_*`及finish_hold目录，native输入、JSONL、原始readback。
3. 三个余130mm `PLAN_*`：998c1812d2ff462e934e5872c1079a3c、5fac3267121c41dba683bc9b043823b5、b570ced607b64a5e981b15c67ab9d68b。
4. 所绑定CAMERA/BODY点云、scene snapshot/compiled world、T_body_camera、model/tool配置版本。
5. 现场systemd单元、环境、进程启动时间、planner模块源码hash、native v5/v6二进制hash和SDK动态库版本。
6. 原始native timing audit、resampling stretch、源码trajectory采样间隔和物理feedback。
7. AMR移动前后status及坐标系/完成日志，不用旧预测站位冒充当前精确SLAM坐标。

**不需要为取这些材料运动机器人或重新采集场景。** 本轮离线条件下没有伪造这些原文件，也没有声称Ubuntu或GitHub已经收到它们。
