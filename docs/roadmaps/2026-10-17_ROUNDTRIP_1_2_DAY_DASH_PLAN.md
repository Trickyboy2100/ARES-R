# 完整抓放 Demo 返场一至两天冲刺计划

日期：2026-10-17。此文件为审计后的候选实施计划，不授权现在修改参数或执行机器人。

## 1 交付范围

唯一主线：当前右臂取料→水平抬升230mm→固定底盘路线至PLACE→ID3参考角+下层中间偏置→上方40mm释放→不收臂原路返回。

保留：现有A/B与golden first-pick作为独立回归；现有Epic匹配、BODY外参、基础SceneAwareMotion/cuRobo/native sender。

本冲刺不做：新WebUI框架、PPO/Isaac训练、换模型库、双臂并发、边开底盘边动臂、连续Servo流、force研究、新dock泛化研究、重新自由6DoF外参拟合。已有Task Studio只作为正式任务客户端，不另建算法。

**验收核心：同一脚本/Runtime包自主完成，没有Codex逐阶段设计路线、手工读日志后下下一步；故障时有正式恢复，不重做已完成物理动作。**

## 2 先决条件

- 审计后确定最终task参数和路线；当前命令路线新GRASP横向850mm、PLACE不变，返场重新确认实际站位，不盲用SLAM旧值。
- 回收10月16日原始run/scene/native/effective config；冻结集成分支与文件哈希，保全同事dirty，不reset/revert。
- 明确持物几何来源和夹爪/TCP语义；不临时扩展原接触bypass到任意距离。
- 现场至少一名持续观察者、物理急停可用；试验空间按真实持物和释放后姿态的扫掠检查，而非只看TCP。
- 假设1名主集成开发、1名现场操作者/审核者。以下人时为工程估算；若缺少原始证据或模型不一致，不能保证1天完成。

## 3 最值得先做的十项

节省时间是量级估计，不能直接相加：多项作用在相同关键路径上。

| 排名 | 工作 | 当前证据/代价 | 预期收益 ESTIMATE | 工作量 ESTIMATE | 风险和依赖 |
|---|---|---|---|---|---|
| 1 | 把FAST_SINGLE_PASS真正接到唯一worker；effective config可读 | FAST请求迟到80秒，QUALITY worker159秒 | 正常solve目标≤2秒、配置deadline4秒；端到端仍含scan/validate；单次可少数十至百秒 | 2–4小时 | MEDIUM；固定scene对照，必须验证真实调用而非只unit test |
| 2 | job deadline/cancel/显存预算与缓存上限 | 客户端超时不取消，GPU不足1GiB，OOM机械重试 | 消除迟到计算和排队；避免每次清显存重新开始 | 2–4小时 | MEDIUM；单job owner，回收不能影响控制进程或他人GPU任务 |
| 3 | pregrasp前做contact/lift有限分支筛选 | 159秒后才发现contact IK失败 | 几秒内失败并报告分支，不浪费完整solve；新GRASP正反抓已可行 | 1–3小时 | LOW/MEDIUM；现有IK精度不先改，DP大研究不属于本冲刺 |
| 4 | attachment-aware self-filter与同geometry overlay | 起点−62mm，planner已attach但scene未过滤持物 | 解决当前130mm主阻塞，减少无意义重试；不是“多保守一点”可解 | 3–5小时 | MEDIUM/HIGH；误删隔板风险，必须overlay和hold-out，不做整球盲删 |
| 5 | 抓取验证改时序、原始时间戳、一次人工确认分支 | 抬升前delta误判，added52%触发FAIL | 去掉每次现场争论/写恢复脚本；目标正常验证2–5秒或已审人工一次确认 | 1–3小时 | MEDIUM；不能将夹爪读数单独等同物体确已抓稳 |
| 6 | 统一起点/终点/SETTLING与恢复 | 上层0.2°/native0.02°冲突；末拍失败后已精确到位 | 减少误FAULT和现场数分钟恢复；明确到底动没动 | 2–4小时 | MEDIUM；有界settle、保留跟踪/controller保护；具体阈值由测量决定 |
| 7 | 最小只读state provider与会话重连 | 左臂大status包异常阻断right | 短暂通信问题自动恢复但不伪造状态；降低重复登录和诊断负担 | 1–3小时 | MEDIUM；真实inactive joints/tool仍必须可靠，控制会话不能重连重置 |
| 8 | native时间参数化审计与修复 | contact115秒，lift72秒，均远高于量级下界 | 同速度/加速度上限下可能显著减少时间，先以10–40秒级段预算验证，不保证具体值 | 3–6小时 | MEDIUM/HIGH；精确几何保形、曲率、跟踪和载荷，禁止未经验证只抬上限 |
| 9 | 单一canonical checkpoint/resume、状态与错误 | 两个临时恢复脚本、旧日志冲突、UI旧FAULT | 不再靠Codex手工恢复；重试不重复close/lift/base/release | 2–4小时 | MEDIUM；确认设备实际状态、不可逆动作的幂等设计 |
| 10 | 合并重复scan/audit/settle，异步诊断 | V1串行观测、多次双臂audit、base重复5点稳定、CPU全障碍报告 | 观测/转场节省数十秒；首动延迟可解释 | 2–4小时 | MEDIUM；相机并发互斥、同epoch与controller完成语义保留 |

十项全部精修总计约19–40人时，**不是诚实的单人一天工作量**。1–2天现场冲刺成立的前提，是主要软件修复在返场前完成并通过冻结数据/Mock adapter验收；现场主要做commissioning，而不是继续写架构。

## 4 不等于删限制 应逐项决定的策略

### 4.1 立即修掉的工程缺陷

- ignored solver_policy、deadline只在socket端生效、cache无限增。
- profile/effective metadata不一致；HTTPError只报409、worker只报SystemExit2。
- 日志目录复用；恢复ownership/UI不统一；active文件与实际进程分裂。
- 验证脚本重写读回时间戳、配置半径/delay硬编码。
- 上下层不同起点阈值、没有SETTLING。
- attachment只进planner不进self-filter。

这些不是等待“降低安全等级”才能修的事项。

### 4.2 应有开关和明确scope的实验策略

- 感知环境避障参与与否，当前是否识别/持物；默认AUTO不能暗中等于所有模式都OFF。
- central exclusion：现已OFF，应所有入口同值，不能历史template重新打开。
- preferred clearance、optimizer activation、scene inflation、robot/payload self-filter margin分别显示，不用同一个“间隙”滑块代表。
- 阶段速度/加速度/跟踪预算；versioned DEMO_ONLY不污染其它motion mode。
- 人工抓稳确认：只替代明确的visual verification gate，有source run、签字时间、时效和边界。
- 抓取IK质量等级：严格目标精度与实验允许精度可由审核确定，但必须显示整段最坏误差，不只看第一个超限点。

本次contact终点7.5mm/2.66°远不止第17点的1.57mm/0.62°，不能以“只放宽一点”为由隐去最坏误差。反过来，0.02°/0.05°等现有常量也不是天然正确：需要按控制器精度、到位收敛和任务误差预算重新审定，而不是因为已经写进C++就永久不可改。

### 4.3 保留但必须做得可解释的基础保护

- 真实急停、controller碰撞/限位/故障、非有限/失效反馈、双进程写同一控制器。
- scene/模型/工具/轨迹绑定与实际起点一致；不能靠重写timestamp把旧scene伪装fresh。
- 对全臂、夹爪、持物、inactive arm的真实外部硬碰撞；模型归属错误要修模型。
- stop不自动补走，release不因超时误重发，base accepted不当settled。

## 5 返场前离线必须交付

### A 单一可运行包

```text
task definition + reviewed parameter snapshot
station/route contract
skill adapters（复用现有服务）
runtime state machine/checkpoint/recovery
scene + robot + attachment geometry合同
planner effective profile + deadline contract
native sender binary/source/SDK manifest
source SHA + tests + offline replay证据
```

golden first-pick不迁移、不替换；新runtime additive、状态目录隔离。临时恢复脚本保留为历史诊断，正式任务不调用它们。

### B 明确状态机

```text
OBSERVING → BRANCH_PRECHECK → PICK_PREPARED → MOVING_PREGRASP
→ CONTACT_APPROACH → CLOSED_HOLD_CANDIDATE
→ VERIFIED / OPERATOR_CONFIRMED
→ TEST_OR_INITIAL_LIFT → SETTLING → ARRIVED
→ ATTACHED_WORLD_READY → LIFT_TO_HOLD → HOLD230
→ BASE_TRANSIT → PLACE_OBSERVING → PLACE_PREPARED
→ MOVING_PRELAND → RELEASE_CONFIRMED → DETACHED
→ BASE_RETURN → COMPLETED

任何阶段可进入 STOPPED / FAULT / RECOVERY_REQUIRED
恢复不是重新从起点开始，而是重新验证当前checkpoint和物理状态。
```

必须区分“命令未发”“命令已发但结果未知”“已到位但收尾确认异常”“真正控制器故障”。现有一次exit code不能覆盖这四类。

### C 冻结数据回放与故障注入

| 场景 | 预期 |
|---|---|
| 当前新GRASP真实成功contact/lift数据 | 分支预检先PASS，再进行昂贵free-space规划 |
| 旧GRASP contact不可行数值样本 | 早失败并保留完整误差曲线，不先跑159秒 |
| 5700无目标/截断/timeout | 不提交epoch，不动设备 |
| FAST任务超时 | 收到CANCELLED/已回收确认，无孤儿结果可执行，无队列堵塞 |
| QUALITY OOM | RESOURCE_EXHAUSTED，资源回收后才允许有界重试 |
| 左臂status包失败但独立joint/tool有效 | 使用正式只读provider，不伪造全status、不控制左臂 |
| 左臂joint变化/工具变化 | scene/plan失效，不能拿旧left模型继续 |
| contact/100mm首点偏差0.035°样本 | 在统一合同处一次解释/重建，不上层通过再native拒绝 |
| 末拍误差后在受控窗口收敛 | SETTLING→ARRIVED；超窗/真实fault才失败 |
| 持物点云与attachment重复 | 只移除matching payload-owned点，外部table/隔板仍保留 |
| 用户Stop/网络页面断开 | Stop停止设备并锁定明确原因；页面断开不擅自续跑或重复启动 |
| base accept但未完成 | 不base_settled，不后续arm plan |
| release反馈不确定 | 不detach、不自动撤底盘，不重复关/开夹爪 |
| 恢复前已有运动发生 | 不允许同一轨迹重发，必须新state/scene/plan |

离线测试不能替代实机验收，但应把大部分工程失败挡在现场之前。

## 6 现场第1天 建议时间盒

### 0至1小时 状态与包一致性

- 只读取证：源码/配置/native/SDK hashes、driver版本、GPU空闲内存、服务启动模块版本。
- 站位/物体/载荷和当前夹爪状态重新确认；不要认为10月16日最后HOLD仍然成立。
- 使用同canonical backend显示当前task、持物、scene和stop原因；清理只属于已结束job的缓存。
- 查清BODY+Y左移后的真实站位，PLACE仍是哪个物理站，避免累加相对移动误差。

退出：`PACKAGE_MATCH=YES`、`STATE_PROVIDER_READY=YES`、`PLANNER_SERVICE_READY=YES`。

### 1至2.5小时 不发运动的同接口预验

- 一次fresh pick epoch；对两种symmetry做contact/lift预检。
- 同frozen scene重复FAST10次、QUALITY3次，记录queue/init/warmup/solve/validate/package，单独报告warm与cold。
- 在真实持物或固定样本点云上overlay payload self-filter；证明table/隔板保留，报告删点数量/范围/最大外删。
- preview整个任务的可执行段与place semantic template；base移动后的place轨迹必须fresh scene重算，不把旧scene轨迹当真。

退出：`NO_IGNORED_FAST_POLICY=YES`、`NO_ORPHAN_SOLVE=YES`、`ATTACHED_WORLD_READY=YES`。

### 2.5至4小时 小段实机验收

- 用现有commissioned速度，只验证current→pregrasp、contact、闭爪、初始lift、settle、剩余lift。
- 每段记录最大/p95/RMS tracking、位置姿态误差、实际时长。这个窗口不同时修改速度和碰撞模型，防止归因混乱。
- 若time dilation导致一分钟小动作，先记录并确认预算；不现场连续拉大全部阈值。

退出：`PICK_TO_HOLD230=YES`、`FORMAL_RECOVERY_READY=YES`，不靠新增一次性脚本。

### 4至6小时 一次全链

- 人工确认整条持物和释放后扫掠与4cm释放实验。
- 一次完整runner授权；正常流程无额外Codex handoff。
- 记录GRASP/PLACE/返回的位置观察、ID1/ID3 epoch、所有轨迹hash和scene versions。
- 任何真实fault进入正式recovery，先核对动作已发/未发，不整任务重开。

退出：`ONE_FULL_PHYSICAL_CYCLE=YES`、`NO_CODEX_STEP_ASSIST=YES`。

### 6至8小时 固化而不是扩功能

- 再完成2次全链，比较同一参数的耗时与结果。
- 清理release→return等未实际验证语义；保留失败证据。
- 正常fast-forward保存代码/配置/报告；大点云按既有受控归档方式，不仓促公开上传。

若中午前还没有PICK_TO_HOLD230，取消当日新增UI和任何研究扩展；聚焦一个明确根因，不再叠三套恢复脚本。

## 7 现场第2天 可靠性与速度

- 前半天：固定参数至少10次完整循环；记录成功次数/失败类型，不只展示一次“幸运轨迹”。10次是本次Demo验收建议，不等于工业可靠性认证。
- 只在主线稳定后审native retiming，同一geometry/scene/任务质量和速度/加速度上限下比较实际耗时；若改变几何或物理profile，重新验证，不暗换。
- 诊断CPU distance移异步、去重复scan/audit/settle等优化逐项开关对照，记录实际省时，不合并成一次大改。
- 后半天：正常周期演示、Stop、故障恢复和同事独立操作；输出一页操作说明与一键入口。
- 所有实机操作继续由现场具备急停条件的人员观察；故障注入优先Mock或设备静止状态，不故意制造带载碰撞。

## 8 性能指标和现实周期模型

### 软件指标 建议验收目标 非现状声明

| 指标 | 建议 |
|---|---|
| warm cuRobo solve | p50≤2秒；hard request deadline4秒合同真正生效 |
| queued work | 正常单任务queue近0；不得排队等已超时job |
| worker初始化 | 冷启动单列，服务预热后不再计入正常每程 |
| fresh scan→validated native-ready | 第一版目标约10–20秒，必须拆capture/scene/solve/validate，不把solve≤2秒说成端到端≤2秒 |
| 状态读取 | 依现场测量规定有界重连、数据时效与稳定窗口，UI显示每侧age |
| 正常全链 | 先连续成功并测量；没有完整真实周期前不填p50/p95 |
| 异常响应 | Stop/真实fault路径单独记录；不能为了速度删除controller保护 |

### 四档周期模型

| 档位 | 范围 | 周期估算 | 条件 |
|---|---|---|---|
| BASELINE_CURRENT | 10月16日当前混合链路 | 约8–18分钟/成功无异常轮的工程估算，失败排查更久；完整成功未测 | contact115秒、lift72秒已测，其余place/转场含估算 |
| PHASE1_SOFTWARE_CLOSURE | 修FAST/deadline/cache/epoch/attachment/verification/settle/recovery，不先提高物理上限 | 约6–10分钟 ESTIMATE | 保留当前已测慢motion时长；不能承诺≤420秒一定达成 |
| PHASE2_RETIMED_SAME_CAPS | 修time parameterization，保持审定速度/accel caps，必要的新path重新验证 | 约3.5–6分钟 ESTIMATE | contact/lift显著缩短有证据；base、release、scope不变 |
| PHASE3_PIPELINED_DATA | 在稳定后减少重复scan/audit/同步诊断，prepare-ahead有正确失效 | 约3–5分钟 ESTIMATE | 不是当前冲刺先决条件；不需要continuous Servo stream才可完成Demo |

这些模型与9月P3.8E的606/420/290/230秒模型来自不同代码/轨迹和任务版本，不能混在一起当“已经证明提速”。目标应由客户最终节拍要求裁定，再以实测更新。

## 9 每个可配置“坎”的审核表格式

```text
gate_id:
category: CONTROLLER / STATE_BINDING / MODEL / QUALITY / DIAGNOSTIC / ENGINEERING
stage_and_entrypoint:
actual_code_symbol_and_sha:
units_and_current_effective_value:
why_required:
measured_false_positive:
worst_case_failure_if_removed:
configurable_scope_and_owner:
normal_fail_action:
read_retry_or_replan_policy:
manual_confirmation_allowed_and_scope:
commissioning_evidence:
decision: KEEP / FIX_IMPLEMENTATION / RELOCATE / PARAMETERIZE / REMOVE_DUPLICATE / NEEDS_EVIDENCE
```

默认先审实现缺陷和合同冲突，而不是让操作者每个gate重新证明“现场安全”。

## 10 最终交付清单

- 一键启动/Stop/正式resume，同一backend和唯一task状态；ART和WebUI一致。
- 19阶段或审核后的等价正式Scheme，完整参数和版本明确，途中无需Codex设计waypoint。
- 实物持物overlay/self-filter/planner一致，无200mm整球盲删。
- 真正effective FAST和cancel证据，GPU内存有界。
- 真实10次循环结果、失败复盘、逐段实测waterfall、原始文件清单与SHA。
- 已完成与未完成清楚分开；独立base空载往返、golden first-pick、Mock通过都不能替代完整交付验收。
