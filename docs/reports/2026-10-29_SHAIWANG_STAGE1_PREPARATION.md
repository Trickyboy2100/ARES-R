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

### 正式SIFT Golden branch 1.0.0保全

按操作员“前半程golden”验收，新增正式ID `right_arm_sift_pick_lift_replace_reset_v1`，显示别名 `demo-3-branch-sift-graspreset`，Golden为验证类型、BRANCH为任务关系，属于SIFT_COMPLETE_PICK_PLACE家族。未将新专机place或AMR导航宣称完成。原三个Golden别名保留。
目录含demo.json、README、source_parameters.json、station.json、evidence.json、native_assets.json、kinematic_assets.json、pinned_inputs.json。冻结V4偏置、SIFT-BLC-GRSP SLAM站位、成功六段hash、scene/pointcloud/package hash、URDF/SDK/Native版本和37项核心源码/配置hash。运行产物和原始点云仍在worklog/private，不塞入Demo定义。成功快照与旧轨迹不能跨运行直接执行。
正式入口 `scripts/run_sift_pick_reset_demo.py`，校验冻结内容后薄委托已经实测的run_shaiwang_stage1；没有复制算法或改旧Golden脚本。WebUI /demo-console新增独立卡片，ART共用DemoRegistry，console使用sift_pick_reset独立adapter；启动归属token传递有完全Mock网络测试，页面/选择/服务重启不运动。底层执行ID为right_arm_shaiwang_pick_reset_v1，正式别名与该历史ID映射在定义中明确保留。
现场只读asset校验成功，全量861tests、11.590秒，OK（1skip），日志tests-sift-golden.log。新增WebUI adapter仅做无运动集成测试，未再次点击实机启动；本轮无机器人动作、不push。

### V4永久偏置完整前半程复测成功

操作员认可抓取姿态后授权松爪、回退、立即完整运行。先使用同一接触上下文退回55mm；通用free-space在该点仍判INVALID_START_COLLISION，未执行center。随后按已授权退回再退40mm（总95mm），接触validator通过后执行，再fresh scan/cuRobo回center成功（Native31.407秒）。两段退回证据 `worklog/evidence/shaiwang-contact-adjust/1793258855859944819/` 和 `1793258972416151069/`；center证据 `worklog/evidence/operations-execution/1793259036512900318/`。这是本轮人工检查后的起点恢复，不把额外95mm作为常规Demo退回长度；常规Demo仍沿已规划contact反向退回。
之后完整自动V4前半程成功：目录 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793259072432485426/`，PICK_LIFT_REPLACE_RESET_COMPLETE、backend SUCCEEDED/exit0，执行141.268秒。fresh准备38.953秒、初始四段Native打包4.436秒，成功这一轮扫描准备至完成累计约184.66秒（不含前述检查点恢复/额外退回及center）。使用参数 `[+2,+2,−7]mm`、BODY yaw+2°、pitch down1°和旧local-Z−10°，未改变速度或底盘。

|V4实机阶段|墙钟秒|
|---|---:|
|夹爪预检/开40%|0.111 / 1.261|
|预抓取|34.785|
|并行下一段准备残余等待|0.006|
|接近抓取|10.124|
|闭爪/抬升前验证|0.408 / 2.005|
|连续230mm抬升|17.034|
|抬升后并行验证|8.986|
|原路下降230mm|17.041|
|松爪|1.260|
|退回预抓取|10.117|
|回center|34.774|

六段均target_reached及servo_disabled code0；max tracking分别0.3669/0.1942/0.4863/0.2663/0.2194/0.2313°。POST_LIFT的时戳/夹爪稳定/持物/抬升到位/scene evidence gates全部通过。终态center位置误差2.058mm、姿态误差0.00488°。原目标已放回，夹爪松开，底盘未动。
参数commissioning_state仅更新为STAGE1_V4_PICK_LIFT_REPLACE_RESET_VERIFIED并绑定成功证据。新专机place和AMR转场仍未验证，未宣布完整新Golden main完成，未push。

### V4：累计右旋2°，闭爪后原地保持

按操作员明确要求，在V3当前位置TCP中心再绕BODY Z右旋1°（相对最初+4°修正累计右旋2°），成功目录 `worklog/evidence/shaiwang-contact-adjust/1793258531623731961/`。Native规划1.92秒，实际位移 `[+0.003446,−0.041938,+0.005858]mm`，target_reached/servo disable确认。之后仅执行右夹爪close raw0，延迟读回73，fault0；原始命令与状态存同目录close-command.json、close-delayed-readback.json、gripper-hold-status.json、hold-telemetry.json。没有抬升、底盘运动或回center。
V4永久参数只把Demo body_yaw_correction_deg从+3°改为+2°；目标平移 `[+2,+2,−7]mm`、下俯1°、旧local-Z −10°保持。按“没有提出问题则保存”的明确要求落盘，并保留full_pick_reset_with_v4_offsets_pending；整轮新偏置实机复测仍待执行，不宣称已完成。当前夹爪闭合持物于原抓取检查点，等待人工核对，任何回center/松爪/抬升均需后续指令。

### V3永久偏置与TCP中心右旋1°完成

操作员已明确认可当前抓取位置，并要求TCP中心yaw右旋1°、完成后保存永久偏置。本轮仅执行原地yaw微调，成功目录 `worklog/evidence/shaiwang-contact-adjust/1793258240721578616/`，Native规划时长1.84秒，实际TCP位移 `[+0.014857,−0.043880,+0.049008]mm`（模长约0.0674mm），servo disable及target_reached确认，未闭爪。微调基于上一已完成微调的after.json检查点，双臂/工具/底盘history绑定保持。
params.json升级V3：检测目标BODY位移累计 `[+2,+2,−7]mm`；Demo姿态维持旧local-Z −10°，BODY yaw累计逆时针3°，并对当前TCP前向施加下俯1°。将平移归入每次检测目标偏置，yaw/pitch归入Demo全程右臂姿态补偿；controller tool及原Golden参数不变。逆补偿按相反次序移除pitch/yaw/local-Z，单测检查任意姿态下正逆一致与BODY平移不随检测轴旋转。
inspection_stop_before_close切回false，为下一次完整前半程预备，但本轮没有启动抓取、回center或回程。标注CONTACT_OFFSETS_APPROVED_FULL_RECHECK_PENDING，不冒称V3整轮已经实机验收。站位SIFT-BLC-GRSP不变。
现场全量858tests，11.548秒，OK（1skip）；日志tests-permanent-offset-v3.log。重载空闲隔离后端只用于加载新配置，未自动开始任何运动。

### 接触检查点微调成功（未修改偏置配置）

后续仅授权当前位置后撤BODY X−3mm、左移Y+2mm、朝前端下俯1°。普通free-space fresh扫描把当前目标接触区判INVALID_START_COLLISION，未执行；因此使用已完成开40%检查点的stationary task-contact上下文，创建独立≤6mm/≤2°的PICK_CONTACT_ADJUST检查，并保留所有Link/non-target/self/controller检查。旧contact/escape最短25mm策略不变，普通motion API不开放此模式。
`scripts/run_shaiwang_contact_adjust.py`检查双臂状态/工具未变化、底盘IDLE且log/queue未变化、夹爪open40，连续IK与dense target-only contact验证后Native执行。原接触scene明确作为同站静止上下文记录，没有伪称新fresh scene，也未删除障碍。
成功目录 `worklog/evidence/shaiwang-contact-adjust/1793257790266658012/`。Native规划时长2.32秒，实测BODY位移 `[−2.996706,+1.993906,−0.038313]mm`，终点 `[0.688003776,−0.216602252,1.024967751]m`，到位及servo disable确认。没有闭爪、抬升或底盘指令；未把这次微调累计写入task偏置，等待人工确认。新增短距离策略单测同时验证旧最小长度约束不变及臂体碰撞仍拒绝，5tests通过。

### V2双偏置及闭爪前检查实机完成

按新授权，保留原−10°TCP_LOCAL_Z补偿，另加BODY +Z逆时针4°右臂Demo姿态修正；独立的检测位置偏置为BODY `[+5,0,−7]mm`，每次检测后叠加，raw检测数据不变。center位置不应用检测平移，只应用Demo姿态补偿；不修改controller tool、原Golden参数或左臂。
当前站位追加为SIFT-BLC-GRSP，config/manipulation_stations.json保留原站位。map379，SLAM x0.202325m/y0.753431m/yaw−4.83633°，confidence原值31.86；仅记录观测不宣称高精度导航commissioning。注册证据 worklog/evidence/station-registration/1793257129635709127/，没有发送底盘运动。
4°center姿态校正成功（Native3.010秒），之后fresh扫描规划并执行至CONTACT_HOLD_BEFORE_CLOSE。任务检查模式通过params的inspection_stop_before_close=true绑定，当前不允许自动闭爪或抬升。
本次目录 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793257202644547034/`，准备39.114秒，预打包约4.356秒，动作/检查编排49.331秒。结果CONTACT_INSPECTION_BEFORE_CLOSE、backend SUCCEEDED。事件只含夹爪状态、开40%、PREGRASP、CONTACT；无CLOSE/LIFT/LOWER/RELEASE事件，gripper_close_command_sent=false，六段任务未继续。
raw目标XYZ `[0.685875405,-0.219920655,1.032246550]m`，偏置后 `[0.690875405,-0.219920655,1.025246550]m`；最终只读实际TCP `[0.691005215,-0.218598217,1.024987464]m`。停下后夹爪独立readback399（40%命令400），fault0。等待人工核对，不自动继续。
新增偏置组合单测验证BODY平移不会随目标姿态旋转，BODY yaw与原local-Z补偿组合及逆变换正确；专项19tests通过。现场Python全量857tests、11.613秒，OK（1skip），日志tests-offset-inspection.log。本机全量869tests有6项环境错误（Linux /proc缺失2项、sandbox socket bind被拒4项，2skip），未将其表述为本机全测通过；没有改这些无关旧测试。

### 修复后完整实机前半程成功

任务 `right_arm_shaiwang_pick_reset_v1`，成功目录 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793256176366037010/`。结果PICK_LIFT_REPLACE_RESET_COMPLETE，backend SUCCEEDED，exit0。fresh准备38.594秒；预打包四段约4.265秒；从runner启动至完整回center共138.433秒（不含本轮之前的修复、失败及center恢复）。约181.3秒为本次成功fresh准备+初始打包+执行累计，不能忽略前面失败修复另耗时。

|实机阶段|实测墙钟秒|
|---|---:|
|夹爪状态|0.112|
|开40%|1.260|
|center→pregrasp|33.879|
|并行下一段Native等待|0.006|
|接近抓取|9.711|
|闭爪|0.408|
|抬升前验证|2.005|
|连续抬升230mm|16.933|
|抬升后并行readback+场景验证|8.884|
|原路下降230mm|16.938|
|松爪|1.260|
|退回预抓取|9.716|
|回全局center|33.883|

六段均target_reached=true、servo_disabled code0；最大tracking依次0.6867/0.1768/0.5284/0.5290/0.1810/0.6852°。抬升后验证GRASP_CONFIRMED，所有时间戳/夹爪稳定/持物/抬升到位/场景证据gate通过，夹爪延迟readback74。终态全局center位置误差2.056mm、姿态误差0.00438°，检查通过。底盘和左臂未执行运动，旧偏置只读。
并行机制已实际生效：抬升/下降Native在预抓取执行时准备，NEXT_NATIVE_READY残余等待仅0.006秒；但扫描17.29秒、预抓取规划请求9.10秒，以及六段各约2.7秒外围开销仍可优化，不宣称已达到最快。
Mac原始执行日志备份目录 `/Users/andyee/Documents/ChatGPT/local/site-private-20261029-shaiwang/success-run-1793256176366037010/`。此成功只覆盖新对象前半程，未验证新专机放置、导航或完整取放，未自动标记为新的Golden main。

### 重启后首次实机调试与sender到位误判修复

机器重启后8775/8776未启动，已只核对隔离目录进程和端口，将旧services.json/planner.sock改名保全后重新启动隔离服务；原生产目录未修改。
重启后center读数位置差3.852mm，先fresh规划回center；首次controller errcode4128769在0运动采样前拒绝，未清错；后续只读errcode0后fresh规划重试成功。
实机尝试目录 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793255910755731832/`：fresh准备38.570秒，通过全部几何；夹爪开40%成功；预抓取389采样实际执行到终点，但settling误报tool/user changed，未继续contact或夹取。
根因是任务专用native_sender.cpp settling使用read(robot)（tool_data默认false），随后却比较未填充的final.tool零值与实际工具偏移。已修为read(robot,true)，保留tool/user/offset一致性检查。工具实际仍tool1/user0、errcode0，不是实际换工具。原Golden二进制没有替换。
修复sender源码SHA256 `34316035ab38fe31a542aa3c9ab008d8d76cb8965e72c4e4a71de7add29e8a48`，二进制SHA256 `768fe69243010f07669b207d7403e5a6d58e585b6aad6366dd91d0090163b506`；本机专项18tests通过。
未持物状态fresh cuRobo回center成功，Native31.568秒、max tracking0.3234°、servo disable确认；证据 `worklog/evidence/operations-execution/1793256140488680143/`。随后按本次授权重新fresh准备完整前半程。

### 后续fresh扫描成功：完整前半程planning-only通过

本次目录 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793254374769374631/`。
ID6 fresh epoch、接触IK、cuRobo预抓取、连续230mm抬升与反向下降、退回预抓取、原路center全部几何通过。六段Native原文件离线validator全部通过，未连接控制器执行；补齐Native后旧四段binding另存为task-binding-before-complete-native.json，新binding验证通过。

|准备阶段|实测秒|
|---|---:|
|夹爪只读预检|0.034|
|persistent planner初始化检查（与观测并行）|0.437|
|fresh观测事务（双臂状态、ID6、点云与场景）|17.131|
|接触几何/IK预检|2.704|
|−10°补偿核对|0.041|
|cuRobo请求整体|9.275|
|构建抓取包|0.338|
|230mm与反向几何验证|9.072|
|几何准备总墙钟|38.597|
|全部六段Native打包累计|12.994|

cuRobo worker复用persistent runtime，无重复full warmup solve；world update 0.238秒，planner调用6.751秒，报告solve5.855秒，独立dense validation0.982秒。当前这次求解仍超过此前2秒目标，不将“使用快速实现”误报为“低于2秒”。全部串行准备计算约51.59秒，不含本次人工查阅/命令间隔。

BODY XYZ（m）：center `[0.358309,-0.080000,1.027835]` → pregrasp `[0.629967,-0.220821,1.031881]` → grasp `[0.684968,-0.220733,1.031981]` → lifted `[0.684968,-0.220733,1.261981]`。回程严格反向，−10°补偿保留。
Native计算运动时长：预抓取31.12秒、接触6.96秒、抬升14.08秒、下降14.08秒、退回6.96秒、center31.12秒，合计104.32秒；不包含夹爪、验证、SDK与流程等待，不是实机cycle time。实际速度峰值自由段约0.10rad/s、接触约0.048rad/s，未改速度参数。
证据：timings.json、planning-summary.json、native-validation-current.json、native-manifest.json、epoch/manipulation_observation.json、pregrasp/planning.json。状态为PLANNING_ONLY_PASS，未执行抓取、夹爪、抬升或reset；实机仍需单独授权及执行时fresh admission。

### 全局center实机到位后的当前站位复测

右臂单独回全局center成功，执行证据 `worklog/evidence/operations-execution/1793253013399242234/`；Native 1.972秒、19样本、最大tracking 0.1831°、servo disable确认。独立只读到位核验位置误差2.058mm、姿态误差0.00138°。

随后仅prepare两次，未执行抓取/抬升/reset。两次命令均为 `320,2,6,1,1,0`，未取得当前有效抓取目标，故未进入接触IK、cuRobo正式求解或Native打包。

|阶段|首次（秒）|重试（秒）|
|---|---:|---:|
|夹爪只读预检|0.022|0.064|
|规划器initialize-only，与观测并行|13.232|0.442|
|观测尝试，含双臂前置只读状态与ID6|3.423|3.411|
|prepare总墙钟|13.256|3.477|

首轮Epic原始响应 `000,3020`，未检测出结果；不是规划超时或碰撞拒绝。完整点云SceneSnapshot不提交，不能用昨天目标代替当前目标。重试不重复full warmup solve，initialize-only返回正常。
证据目录分别为 `worklog/evidence/demo-runs/right_arm_shaiwang_pick_reset_v1/run_1793253824453459785/` 和 `run_1793253886948617996/`。
当前结论为CURRENT_SCENE_PICK_RESET_NOT_YET_VERIFIED，需先恢复ID6当前目标识别。旧冻结数据的103.68秒仅是历史几何运动估算，不能作为本次成功结果。

- 第一阶段全量无运动测试855项，OK，1项跳过，11.759秒；结果为tests-final-v3.log。
- 全局center入口补充后，现场全量无运动测试856项，OK，1项跳过，11.688秒；结果为tests-global-center.log。Mac任务专项18项单测通过。
- 原Golden九个固定输入按哈希核对；offset/config不改。
- 本轮没有发送机械臂、夹爪或底盘运动命令，未执行新Demo。
- 代码仍为独立候选分支，不push、不替换golden。

下一步：确认并执行已预览的回全局center动作 → fresh prepare和原始结果检查 → 请求新一次现场监督抓取授权 → 一次性执行完整前半程并记录故障/耗时 → 全部通过后再进入新专机识别/偏置/站位阶段。
