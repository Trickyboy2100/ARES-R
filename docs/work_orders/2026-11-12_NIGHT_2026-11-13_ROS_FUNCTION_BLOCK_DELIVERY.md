# ARES-R ROS1 取放功能块交付冲刺：2026-11-12 晚间—11-13（现场即将离开）

> 状态：执行任务书（PROPOSAL / WORK ORDER），不等于已经完成的实机测试。  
> 基线：\`codex/ros1-center-restore-20261112\` @ \`fd2467c00fdeccaf5ba80f0f21a23cc070cc498f\`。  
> 目标：把现有“抓起又放回”与“扫描后放置”Demo组织为**甲方可直接调用的ROS1机械臂功能块**，不包含底盘移动；保留功能块01和既有Golden，先验收有实际安全证据的块，再逐步开放其余工位。  
> 客户系统：Node.js Mission动作组织、底盘与业务流程由甲方负责；本方提供ROS Action客户端交付源码+机器人主机ROS节点/canonical后端。不能用SSH作为客户的运行时调用接口。

## 0. 今天的事实（先看证据，不凭“已有demo”直接判定已经交付）

1. **功能块01已交付**：\`/ares_r/center_restore\`（独立 \`ares_r_center_restore/CenterRestore.action\`）在2026-11-12完成单Goal、真实两段\`当前→center→right/front_right_high_axes_aligned\`；任务总62.395s，最终保存姿态回读与Servo退出均已核对；只验收已保存目标/空手/工具3，\`CAPTURE_START\`尚仅逻辑测试。源码\`release/ros1-blocks-center-restore/\`；旧\`/ares_r/return_center\`保留原ABI。
2. **客户源码ZIP已经交付**：含Action/ROS节点/launch/示例client等7个文件，包内SHA 7/7可核。**它不包含底层cuRobo、SDK、JAKA运动后端**，也不应包含这些；机器人主机仍须运行对应canonical后端。
3. **跨机ROS网络尚未commissioned**：ZIP清单\`remote_network_commissioned=false\`。机器人原ROS Master \`127.0.0.1:11321\`是本机隔离配置；甲方“业务电脑直连、不经SSH”还需要按授权网络配置ROS_MASTER_URI/ROS_IP、双向解析与动态端口、firewall，并做独立客户端回归；不得直接暴露ROS1到不可信网络。
4. **离场前保全已有基础**：\`docs/integration/2026-11-12_ROS1_DELIVERY_ASSET_INDEX.md\`记载6个私有包，合计231,695,184字节，Mac私有目录\`/Users/andyee/Documents/ChatGPT/local/site-private-20261112-center-restore/\`；包含当次SceneSnapshot/原始BODY云、两段ROS真实日志/轨迹/Native、JAKA/Epic SDK合法依赖和源码差异。**仅据报告确认此前完成，离场前仍需做实际文件/哈希存在性检查。** 不上传原始点云、相机图片、厂家私有库或客户nodeapp源码到公开GitHub。
5. **两个源码层次**：根目录不是全部11月现场最新参数；\`release/site-source-20261112/\`是703文件的冻结现场快照，不能直接覆盖当前运行目录。先选择性同步正式运行代码和每个Block的effective参数、hash，再开发新ROS接口。

## 1. 业务功能盘点：按5个抓取 + 5个放置 + 1个辅助组织

需求来自现场同事的微信整理；“称上”是现场称量工位，实际站位/夹具/检测配置以现场登记为准。这里的“已有Demo”与“现参数实机ACCEPTED”是**两种状态**。

| ID（拟） | 业务功能块（底盘不动） | 现有Demo可复用程度 | 处理决定 / 验收状态 |
|---|---|---|---|
| U01 | 扫描→center→已保存右前高位 | \`center_restore\` | **ACCEPTED_SCOPE_LIMITED**：原ABI不改，先解决跨机客户连接 |
| P01 | 称上筛网：扫描抓取、抬升后**保持** | \`right_arm_sift_pick_lift_replace_reset_v1\` / ID6 | **先拆出ScanPick并实机复核**；历史V4整轮抓取/放回成功，但不等于“持物停稳后返回ROS成功”的独立功能已验收 |
| P02 | 称上料盘：扫描抓取、抬升后**保持** | \`right_arm_pick_lift_replace_reset_v1\` / ID1 | **先拆出ScanPick并实机复核**；10-23旧工具/速度合同下成功，11-09更换tcp3、zero-bias、0.2后需重验 |
| P03 | 除尘收料机筛网：扫描抓取、抬升保持 | 可复用P01的抓取执行**引擎** | **缺独立Demo/实机**；不能直接移植称上旧offset、对象身份、SceneSnapshot/站位、碰撞豁免；检测ID需现场确认 |
| P04 | 除尘收料机料盘：扫描抓取、抬升保持 | 可复用P02抓取执行**引擎** | **缺独立Demo/实机**；新工位先完成fresh识别、抓取点、接触、夹持和持物几何校验 |
| P05 | 烘干箱料盘：扫描抓取、抬升保持 | 可复用P02抓取执行**引擎** | **缺独立Demo/实机**；从烘干箱取出时不能只证明终点IK，须验证整段接触退出与载荷/机箱扫掠 |
| L01 | 除尘收料机筛网：扫描放置→受控下降/释放→退出→center | \`right_arm_dmp_place_v1\` / ID2 | **CANDIDATE**，本工位已发生\`983092\`保护停；最新60mm MoveL接触路径和退出40mm需独立安全验收 |
| L02 | 除尘收料机料盘：扫描放置→释放/退出→center | \`right_arm_liaopan_dmp_place_v1\` / ID2 | **CANDIDATE**：最新\`Y5_Z20_D20\`，即y+5mm,z+20mm预放置、20mm下降；旧目录/catalog有D10描述，需要统一 |
| L03 | 烘干箱料盘：ID3扫描→lower_middle放置→释放/退出→center | \`right_arm_liaopan_hongganxiang_place\` | **CANDIDATE**：11-11新偏置、yaw0、水平流形及30mm下降尚缺更新后实机；旧偏置曾遇j3近奇异且MoveL接受但没运动 |
| L04（需求待确认） | 称上筛网：扫描放回称量夹具→释放/退出→center | 复用L01的**放置状态机/MoveL实现** | **待新Demo验证**；不能只把DMP预放置偏置平移，需校准称上新检测参照、夹具深度、退出方向与净空 |
| L05（需求待确认） | 称上料盘：扫描放回称量夹具→释放/退出→center | 复用L02放置**引擎** | **待新Demo验证**；禁复用DMP的已批准鬼影体素家族作为称上默认豁免 |

正式要求已明确：P01–P05五个ScanPick、L01–L03三个ScanPlace（共8个）；若甲方确认“称上放置也独立调用”，新增L04/L05成为10个取放功能，外加U01。

**动作语义红线：** 现有称上“抓取→抬升→下降→放回→center”属于本工位回归/演示，不能直接当ROS ScanPick——ScanPick必须在**持物已确认、可安全静止保持**时结束，不能自动放回或回空手center。ScanPlace只接收“当前已经持物”的工位任务，完成fresh扫描→预放置→受控下降→松爪确认→退出接触区→必要时空手回center。两者间甲方可自行移动底盘，ROS Block不得调用\`/api/operations/base-move\`或AMR SDK。

## 2. 产品结构：少写节点，多复用现有执行器

短期不要创建10套独立JAKA/cuRobo实现。保留U01已交付的\`CenterRestore.action\`消息类型/MD5不变；针对取/放新增长时、可取消的通用ROS Action，例如：

\`\`\`
ROS1 /ares_r/run_block  (new Action; fixed v1 schema)
Goal: request_id, block_id, expected_profile_revision,
      target_id_or_slot_id, payload_session_id,
      onsite_observer_confirmed, prepared_environment_confirmed
Feedback: run_id, stage, state, payload_state, elapsed_s
Result: success, code, terminal_state, run_id, block_id,
        payload_session_id, payload_state,
        transport_handoff_ready, evidence_uri, details_json
\`\`\`

仅允许白名单\`block_id\`与冻结的profile revision，不让业务系统传任意关节、实时TCP坐标、速度、任意JSON/shell和场景排除列表。甲方希望按物体直接暴露单独Action时可以做**薄代理**，全部共享同一个canonical job/资源锁与底层RunBlock执行器；不新建第二个ROS Master和第二套运动算法。

**接口验收比脚本调用更严格**：
- ROS Goal accepted/HTTP 200≠物理动作成功；末端以真实Servo退出、关节/TCP新鲜到位、夹爪/物体后置条件判断。
- \`request_id\`永久幂等；同一个请求丢ACK不新建任务；BUSY不抢占；ROS Cancel先发Stop、物理真正静止后才返回STOPPED/PREEMPTED。
- 后端/ROS/客户端重启不得自动重放物理Goal，保护停不能自动清错。
- 允许客户以普通ROS Action客户端调用而**不通过SSH**；此性质需跨机网络现场验收。提供客户源码包仅含catkin msgs/client/README与ABI/hash，不包含本方闭源/私有后端。
- 一个\`payload_session_id\`跨P→甲方底盘转场→L：记录object类别、当前实测夹爪/工具、附着体几何、观测与校验版本；放置端fresh场景重新核对持物。真实载物扫掠未验证时不得给甲方\`transport_handoff_ready=true\`。

## 3. 极易复现的现场事故 → 禁止退化的交付合同

1. **2026-11-09 \`983092\`碰撞保护停**：DMP下降、工具还在槽中就斜向回center、或宽碰撞豁免导致绕行都可能触发。Place必须有\`PREPLACE_REACHED → CONTROLLED_DESCEND → RELEASE_CONFIRMED → RETREAT_CLEAR → CENTER\`，真实MoveL不经过点云cuRobo检查时另做关节软限位、下降方向、深度、扫掠、实际TCP位移；不能因controller接受命令就报成功。
2. **2026-11-11烘干箱近奇异**：旧偏置下30mm只可到24mm，j3≈0，MoveL“受理”却不运动。每次先预检目标与接触全段IK/奇异/软限位；结果需实际到位确认。
3. **DMP鬼影体素与烘干箱真实结构混淆**：不同工位和不同对象的\`goal_collision_waiver\`、\`false_positive_voxels\`必须随station/scene单独复审，不允许复制已批准prefix即放行；已确认11-11“并非误检”的障碍族应撤销豁免，保留硬碰撞与接触限定对。
4. **夹爪、持物和状态恢复**：Pick不能用raw开度单一值证明持物；完成须新鲜夹爪、受控抬升和场景证据。Place release不明时不detach、不return center。ROS/网络断连后命令是否已执行不明必须保留UNCERTAIN。
5. **U01既有成果**：保持真实两段ROS到位结果、Golden旧ReturnCenter、ROS Action MD5和退出/Stop逻辑；新增模块不得覆盖现行backend或端口配置。
6. **有效site参数**：近日tool3、zero TCP bias、0.2rad/s、实际抓取offset/放置offset均曾变化，任何历史\`GOLDEN\`若不能证明与当前SHA/工具一致，应标\`REACCEPT_REQUIRED\`，不能静默旧轨迹重放。

## 4. 现场即将离开：今天17点后最小交接（只做重要的）

**现场操作员/同事（不一定是本人）**：
- 确认当前机器人静止、控制器状态、底盘站位、持物与工具状态；不要为了备份再做一次运动，不清故障/不切分支/不重启生产服务。
- 确认\`/home/yikun/ARES-R-ROS-BLOCK01-20261112\`与\`/home/yikun/ARES-R-RC1-20261019\`现有服务、代码、工作区仍在，告知明日谁负责ROS和实机。
- 留下U01成功/受干扰保护停两类真实运行ID与日志位置；明天新的物理动作由现场人员显式授权。
- 明天3个缺失Pick的新工位：请拍/记录**授权的**物理装置和夹具间隙、目标类别/相机检测编号、底盘静止观测、真实起点与目标参照坐标系。资料进入私有存储，不入公共仓库。

**开发者/Mac（先核实而非重复全量复制）**：
- 现有6个私有归档\`ARCHIVE_INDEX.json\`原始文件和SHA确实可读，能解包；如用户离场后访问受限，再由现场授权人员增量复制新文件。
- 确认GitHub新代码分支\`codex/ros1-center-restore-20261112\` @ \`fd2467...\`；公开只提交代码、README、脱敏manifest；Mac备份新的ROS client ZIP（7个文件，ABI\`604285c...\`）。
- 项目保留所有CANDIDATE事故报告与真实原始点云/轨迹；把今天未保全的文件逐一标MISSING。至少有Mac+一份受控备份，不只留一台电脑。
- 将本任务书发给离线Codex并委托现场同事明日只做物理验证。

## 5. 今晚（11-12）回去做：离线Code+接口，而不是反复动真机

**目标交付：单一ROS ScanPick/ScanPlace Action骨架 + 有效Profile/版本清单 + 明天实机验收单**。

按次序：
1. 基于\`fd2467\`新建独立实施分支；校对当前根源码与\`release/site-source-20261112/\`：不要直接把snapshot覆盖Golden/生产。锁定\`P01/P02/L01/L02/L03\`有效的脚本、参数、工具、场景、碰撞策略和哈希；修正文档/catalog D10 vs 实际V7 D20冲突，只在文档/新profile改，不擅改现场生产参数。
2. 设计固定\`block_registry.json\`和\`CAPABILITIES.json\`：所有11项（含可选）可查到\`IMPLEMENTED / REACCEPT / PLAN_ONLY / DISABLED / ACCEPTED\`；仅U01现阶段默认ACCEPTED。ROS节点对未commissioned块只开放能力查询/prepare，不准物理Start。
3. 在原有\`ros1/ares_r_demo_bridge\`旁新建轻量ROS Action桥/客户端（不重写JAKA SDK）；Mock HTTP/ROS测试：反馈、成功/失败/Stop、第二个Goal BUSY、超时回执不明、request_id重发不重复运动、节点重启不可重复派发。
4. 把P01/P02既有“抓取抬升放回”**分离为持物结束点**（不执行下降/松爪/center），保持每个原Golden原脚本和参数不变；新增独立Block profile/薄runner。离线必须验证输出含\`HELD_CONFIRMED\`与payload session，且没有release/return_center/AMR命令。
5. 现有L01/L02/L03都复用\`run_dmp_place_demo.py\`模式，输出与ScanPlace一致的\`RELEASE_CONFIRMED + RETREAT_CLEAR\`；新的ROS Block必须可选择"放置后center"，但center必须发生在已退出槽/确认无物体后。
6. 不在今晚替3个缺失Pick编造场景偏置。先做参数模板与验证器，为明天的真实ID/工位数据填值，安全状态默认PLAN_ONLY。
7. 如果Ubuntu3080可用，隔离硬件网络后使用保存的实际scene/native轨迹做回放；没有原始场景或GPU则继续做可确定的纯代码工作，不将Mock标为物理成功。

**今晚最低完成定义**：\`RunBlock.action\`固定类型 + ROS包catkin能编译（若没有ROS环境则由现场/Ubuntu编译）、模拟Action契约通过、首批5个现有Demo的生效参数表、明日逐工位验收清单、一个独立实施commit。不要扩展成重写机器人框架。

## 6. 明天（11-13）现场同事按工位验证，你离线协作

**先复用，再验收，不要一天追求所有新工位都Golden。**

### 上午：功能定义与第一个独立Pick
- 甲方/现场同事确认8个必需Block和2个称上Place是否真的需要单独调用；确认甲方ROS客户端的真实机器/ROS master网络，进行一次**无需SSH**的U01跨机Action反馈/结果测试（前提为现场批准网络；不运动的Goal作为先导）。
- 现场挑一个实际可达、几何熟悉且工具/速度参数与当下匹配的称上Pick：P01筛网或P02料盘，采用全新ROS ScanPick **扫描→接触→持物抬升→停在HOLD**，不要沿原Demo自动放回。先只读扫描/规划，再有监督执行；录真实夹持、抬升、持物状态和Stop。
- 若原golden已验证的旧参数与当前\`tcp3/0.2/zero-bias\`不一致，不能以历史成功跳过复核。

### 下午：第一个独立Place + 一条组合流程
- 在已验收的Place里**按当天实际风险**选一个（优先可掌握场景、较少未确认碰撞豁免的DMP位置；不要默认烘干箱新参数已过），完成 \`fresh ID→preplace→受控descend→release→retreat→center\`。保存每阶段实际TCP、limiting joint、碰撞对象、原生servo/MoveL反馈与结果。
- 让甲方Mission分别调用U01和P/L单块（若现场允许），再演示外部顺序编排；**不让本方ROS Block移动底盘**。
- 执行一次可控的取消或无运动拒绝测试；实物风险高时只测试安全的负例，**不主动诱发真实碰撞或保护停**。
- 若时间仍有余力再到新工位验证P03/P04/P05之一的fresh识别和IK/接触包络；未通过就留PLAN_ONLY，不改全局阈值或豁免。

**实机候选顺序由现场场景决定**，不是必须移动底盘去按编号执行。所有真实运动有现场监督、物理急停与明确新授权。

## 7. 每个新ROS Block的最小“能交付”清单

- **合同**：固定block_id，站点和payload类型，pre/postcondition，参数有效revision SHA；
- **实现**：ROS Action可启动、反馈、取消；只复用canonical底层运行者，不自建JAKA控制器；
- **验证**：站点fresh扫描+模型/状态绑定+新轨迹、native/MoveL真实到位、夹爪验证/接触退出；
- **恢复**：明确STOPPED/FAULT/UNCERTAIN和如何人工处理；重发不会重复夹取/松爪；控制器983092等保护故障绝不自动清错；
- **证据**：run_id+scene SHA+plan/native SHA+actual controller/tcp/gripper+时间戳+对应ROS Result；
- **交付**：客户catkin源码包、Action MD5、客户端示例、跨机配置说明、版本锁、1页Quickstart、有效Block列表+不支持项。**客户ROS源码包不等于机器人主机后端可移植包**；主机独立发布manifest/rollback；
- **升级**：相机检测/offset/TCP/速度/持物几何变更时自动降级REACCEPT，经过独立现场验收后重新发布profile。

## 8. Codex每轮短报告合同

\`\`\`text
CLIENT_DEMO01_DELIVERY = VERIFIED_7_OF_7 / REMOTE_ROS_NOT_TESTED
FULL_BLOCK_REQUIREMENTS = 8_REQUIRED + 2_OPTIONAL + 1_UTILITY
PICK_HOLD_EXTRACTION = CODE_READY / OFFLINE_PASS / SITE_PASS / BLOCKED
PLACE_RELEASE_EXTRACTION = CODE_READY / OFFLINE_PASS / SITE_PASS / BLOCKED
RUNBLOCK_ACTION = BUILT / OFFLINE_PASS / CROSS_HOST_PASS
ACTIVE_PROFILES_HASH_LOCKED = YES/NO
SITE_DMP_AND_DRYER_RISKS_OPEN = [specific items]
PUBLIC_CODE_PUSH = branch + SHA
PRIVATE_EVIDENCE_BACKUP = verified copies + last real run index
TOMORROW_ONSITE_STEPS = 3 executable tests max
\`\`\`

不要把“多了几百项测试/又画一张图”当本轮交付。**最终验收看新增的可被甲方ROS业务软件调用、真正完成指定取/放并给出可信结果的模块数。**
