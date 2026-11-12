# ARES-R ROS1「扫描—取料/放料」功能块交付蓝图（建议稿）

**编制：2026-11-12。状态：PROPOSAL，未取得甲方最终接口签字；本文件仅是规划，不启动/修改现场机器人。**

基于：
- [甲方 nodeapp 参考源码导读](2026-11-12_CLIENT_NODEAPP_ROS_INTEGRATION_REFERENCE.md)；
- \`ros1/ares_r_demo_bridge\` 的 ROS1 Noetic \`/ares_r/return_center\` v0.2；
- 仓库根 \`demos/\`、\`demos/catalog_aliases.json\`；
- \`release/site-source-20261112/\` 现场源码快照及 \`docs/reports/2026-11-12_OFFLINE_HANDOFF.md\`；
- 各 DMP/料盘/筛网/烘干箱 Demo 的 **demo.json、当前 parameters.json、README 和明确标注的实机/干跑证据**。

## 0. 交付决策（不要偏离）

目标不是把“完整底盘抓放 Demo”打包成一个 ROS 服务，而是**向甲方提供一组可独立调用、可组合的机械臂能力块**：每个块负责**新鲜扫描、目标确定、场景绑定、规划、受控执行、真实到位/夹持/释放验证、安全终止和报告**。机器人底盘的导航、到站、相机可见性前提和 Mission 顺序由甲方负责。**ROS 功能块内部禁止调用底盘运动 API**。

边界图：

\`\`\`
甲方 nodeapp / Mission
   ├── ARES ScanPick Action  → RETURN: HOLD_CONFIRMED + payload_session_id
   ├── 甲方底盘移动（ARES 禁止在此自行移动底盘）
   ├── ARES ScanPlace Action → RETURN: RELEASE_CONFIRMED + RETREAT_CLEAR
   └── ARES ReturnCenter Action（无持物/经验证持物的专门profile）
                ↓ ROS1 Action / MQTT或MQC适配层（客户端侧）
同一 ARES-R canonical backend / DemoConsole / execution lease
                ↓
已有 5700 + Pixel Pro → scene → cuRobo → JAKA/native → 夹爪 → fresh feedback
\`\`\`

**禁止：** ROS节点直接拥有第二套 JAKA SDK/ServoJ 实现；每个 Demo 自建一个 ROS Master；把 Node.js \`execSync('rosservice call ...')\` 当作长时间运动的可靠Action；因 ROS 节点重启而重放运动；统一将 FAILED/ABORTED/STOPPED 解释为“完成”；用历史scene、旧trajectory/lease、历史夹持假设代替fresh验证。

## 1. 现有能力清单与建议发布等级

验收证据必须与**最新参数、TCP/tool ID、site velocity、外参、工位和碰撞策略**绑定；历史 golden 不能自动证明新配置也已通过。

| Block ID（建议稳定外部名） | 主要来源 | 站点/检测 | 拟公开语义 | 当前证据等级、缺口 |
|---|---|---|---|---|
| \`utility.return_center.right.v1\` | \`right_arm_return_center_v1\` + 现有ROS \`ReturnCenter.action\` | 不执行目标扫描；每次强制新scene | 当前空手/已建模载荷状态→全局center | **ROS1实机通过**：2026-11-12 3次fresh读数确认约2.051mm；目前**不建模持物**，绝不能作为含物自动恢复 |
| \`pick.tray.hold230.v1\` | \`right_arm_pick_lift_replace_reset_v1\` pick→hold部分；\`right_arm_epic_pick_lift_v1\`保留golden | 固定夹具 ID1 | fresh识别+抓取+连续230mm抬升，停在已批准转场持物姿态 | 2026-10-23 旧tool/补偿/速度参数下做过两次连续pick-reset；11-09切换tcp3、zero TCP bias、site 0.2后**需重新验收pick-hold**，且须从“再放回”复合流程正式抽出安全截止点 |
| \`pick.sieve.hold230.v1\` | \`right_arm_sift_pick_lift_replace_reset_v1\` / \`right_arm_shaiwang_pick_reset_v1\` | SIFT-BLC-GRSP，ID6 | fresh识别筛网+抓取+230mm抬升后保持 | 10-29 V4偏置旧合同完成连续pick-reset；从该流程抽出独立pick-hold仍需checkpoint/持物证据、实际停止点验收；历史临时料盘payload模型不等于已测筛网模型 |
| \`place.sieve.dmp.v1\` | \`right_arm_dmp_place_v1\` | DMP，ID2 | 已持筛网→fresh识别→预放置→受控下降60mm→释放→退出接触区 | 现为CANDIDATE，place+center整链未闭环；MoveL绕过cuRobo体素门、983092保护停、起点软限位及先退出再回center有重大约束 |
| \`place.tray.dmp.v1\` | \`right_arm_liaopan_dmp_place_v1\`（共用\`run_dmp_place_demo.py\`） | DMP，ID2 | 已持料盘→fresh识别→预放置→受控下降→释放/退出 | 11-11有效\`parameters\`版本是 **Y5_Z20_D20**，即y+5mm,z+20mm、下降20mm；catalog仍描述旧D10，必须统一；整体放置未实机通过 |
| \`place.tray.dryer.lower_middle.v1\` | \`right_arm_liaopan_hongganxiang_place\`（同脚本） | 烘干箱 PLACE_STATION，ID3，lower_middle | 已持料盘→fresh ID3→泊位→预放置上30mm→下降30mm→释放/退出 | CANDIDATE，11-11新检测坐标偏置 revision21、新水平流形/新IK后**尚无新版本干跑/实机**；旧参数曾受肘部奇异性影响，且误检体素曾被现场更正为真实结构 |
| \`diagnostic.pick_replace.*\` | 两个\`pick_lift_replace_reset\` golden | 夹具 | 抓起再原位放回 | 保留独立现场回归与示教工具，**不作为独立扫描取/放主交付接口** |
| \`legacy.full_roundtrip.*\` / \`sift_dmp_roundtrip\` | 旧跨站全链 | 包含底盘移动 | 仅内部参考/历史回归 | **不进入本次 ROS 功能块目录**；甲方负责跨站编排。旧roundtrip的接续成功不等于同一脚本连续成功 |

**注意数据来源区别：** 仓库根目录当前有 ROS1 回center 和部分golden Demo，11-12专机放置的最新内容多数只位于 \`release/site-source-20261112/\`。快照是保全而非可运行发布；首先选择性移植、对齐hash，并建立唯一正式manifest。禁止整个snapshot直接覆盖生产工作树或把旧root参数当成现场effective参数。

## 2. 建议的接口组织：少量稳定Action + 可扩展BlockRegistry

**近期最小改动：** 继续使用现成的 \`ros1/ares_r_demo_bridge\`（ROS1 Noetic、catkin、现有 \`/ares_r/return_center\` v0.2 **不再破坏其MD5**），增加**一个** \`/ares_r/run_block\` Action；内部通过白名单 \`block_id\` 将请求映射到已有 canonical DemoConsole/TaskRunner。将来如果甲方更喜欢明确的 \`/ares_r/scan_pick\`、\`/ares_r/scan_place\` 两个Action，可增加**薄代理**，不得各自复制执行器。

ROS Action 因Goal/Feedback/Result/Cancel适用于耗时长的感知+规划+动作。不要公开让客户端传任意关节、坐标、速度、\`parameters_json\`或任意 shell 命令。正常功能块由审核后的 \`block_id + profile_revision + target/slot\` 选定。

建议 \`RunBlock.action\` v0.1（**示意合同，必须经甲方审阅后冻结字段**）：

\`\`\`text
string request_id                 # 必填；同一请求重试沿用，防止重复启动
string block_id                   # 必须在已发布白名单，例 pick.sieve.hold230.v1
string expected_profile_revision  # 拒绝运行时参数漂移
string target_id                  # 受BlockRegistry约束，不是原始TCP目标
string payload_session_id         # Place必须提供；Pick创建；无载荷回center禁带
bool onsite_observer_confirmed
bool prepared_environment_confirmed
---
bool success
string code                       # 稳定业务错误码，不只是HTTP/ROS状态
string terminal_state             # COMPLETED/FAULT/STOPPED/RECOVERY_REQUIRED/UNCERTAIN
string run_id
string block_id
string payload_session_id
string payload_state              # NONE/HOLD_CANDIDATE/HELD_CONFIRMED/RELEASED_CONFIRMED/UNKNOWN
bool transport_handoff_ready      # 如未验证全身载物扫掠，必须false
string evidence_uri               # 私有路径/索引，不含大量点云
string details_json               # 附加非敏感测量/版本哈希；稳定字段应直接定义
---
string run_id
string stage
string phase
string payload_state
float64 elapsed_s
string code
\`\`\`

增加**只读** \`ListBlocks.srv\` / \`GetBlockStatus.srv\`（也可先复用现有 HTTP status），返回有效Profile、station、required_tool、发布等级、可运行/阻塞原因和latest revision；必要时加 \`/ares_r/block_status\`、\`/ares_r/safety_status\` 只读Topic。ROS1 namespace不含每个对象特定的业务编号。

\`return_center\`已有物理回归，保持现有Action；检查是否需要额外\`payload_state\`守卫，**现有回center不建模持物，必须拒绝不明持物时调用**。不能用新Action接口更名/变动让甲方先前编译的ReturnCenter消息MD5失效。

同一瞬间只允许一个机械臂动作Job。ROS新Goal到达时若设备忙应返回 \`BUSY\` 并**不抢占当前作业**；尤其ROS1 \`SimpleActionServer\` 的新Goal默认交接/预抢占语义，需要显式验证，不能靠“会有底层锁”处理掉不可逆命令。建议使用显式Goal admission或具备拒绝新Goal能力的ActionServer外加canonical lease。

## 3. 每个Block的统一生命周期与跨站持物交接

\`\`\`
IDLE
 → ADMITTED（request_id去重、白名单、profile校验、全局执行资源独占）
 → PREFLIGHT（底盘静止、右/左臂、tool_id/TCP、控制器保护、站点速度、gripper/载荷、场景新鲜度）
 → SCANNING（fresh 5700+Pixel Pro；出报告/geometry/epoch）
 → PLANNING（目标/安全约束/持物世界归属、cuRobo与独立验证、绑定native哈希）
 → EXECUTING（命令ID，已派发/ACK/反馈）
 → SETTLING（真实新鲜TCP/关节/Servo退出/夹爪状态）
 → VERIFYING（Pick持物确证 / Place释放确证+清除接触区）
 → COMPLETED（仅真实到位且该Block后置条件满足）
或 RECOVERABLE / UNCERTAIN / PROTECTIVE_STOP / FAULT / STOP_UNCONFIRMED
\`\`\`

### Pick 完成合同

Pick功能块**结束在持物安全保持状态**，不要自动放回夹具/回空手center。只有夹持和受控抬升后的新鲜证据成立，才能产生持久化 \`payload_session_id\`，记录：
- 物体\`object_id\`、类别（TRAY/SIEVE）、姿态和与TCP/link6的变换；
- 附着物几何、点云归属、校验版本、tool_id、当前真实右臂关节和夹爪读数；
- 验收站位/环境前提、执行run_id、证据索引、\`HOLD_CONFIRMED\`状态；
- 允许外部底盘移动前必须再确认**载物全机器人扫掠空间及装置净空**；取料完成并不自动表示所有路线\`transport_handoff_ready=true\`。

甲方只有获得持物结果及转场放行后才向自己的底盘动作下命令。

### Place 开始合同

Place输入必须有**未消费且能与真实状态核对的 payload_session_id**，不是仅一个\`has_object=true\`布尔值。甲方完成底盘移动并报告到站后：
- 再查真实底盘静止、pose revision/站位有效期；禁止假定历史地图坐标精确；
- 读取机器人/夹爪实际状态，新鲜扫描新站点，旧pick scene和计划失效；
- 以link6/TCP持物变换重新构建当前Body SceneSnapshot，载荷仍有权属；
- 进入可验证的预放置目标→受控接触/下降→松爪回读→姿态与净空确认→post-release retreat；
- **直到释放确证**才将payload从ATTACHED转RELEASED，提交结果；\`RELEASE_UNKNOWN\`时不detach、不回center、不自动重发松爪。
- 后置\`return_center\`仅在确认已脱离设备槽/夹具且无载荷或具有专门验证的持物center profile时可执行。

### Stop/取消和不可逆命令

\`ROS_CANCEL_REQUESTED → BACKEND_STOP_REQUESTED → NATIVE/CONTROLLER_STOP_ACK → SERVO_DISABLED + ACTUAL_STATIONARY → ROS_PREEMPTED\`；未等到停止不能报PREEMPTED“已停”，返回\`STOP_UNCONFIRMED / RECOVERY_REQUIRED\`并保持物理设备排他，禁止下一Goal。

控制器保护停/碰撞锁存时不自动清错、不自动点动恢复；真实硬急停仍独立有效。ROS节点重启不得重新运行旧Goal。命令已派发但HTTP/ROS回应丢失时先以\`request_id + canonical run_id + command_id\`查询，不能用新ID重新执行同一抓/放/MoveL。

## 4. 从现场事故提炼不可省略的安全合同

| 历史证据 | 可能导致的真实风险 | 交付门槛 |
|---|---|---|
| 11-09 DMP曾在 \`0.065m\`/绕行下降或工具未退出时触发\`errcode=983092\`保护停 | MoveL虽然能发送，但物理接触和真实结构未必被点云/规划识别；斜着从槽内回center会撞结构 | 明确\`PREPLACE_REACHED → CONTACT_DESCEND → RELEASE → RETREAT_CLEAR → CENTER\`；MoveL需要端到端扫掠/关节软限位/轴向与深度门；不能只靠JAKA碰撞保护兜底 |
| 11-11 烘干箱旧偏置使下降只到24/30mm，j3≈0、雅可比σ_min≈0.0001，\`linear_move\`接受但不运动 | 接收ACK/调用无异常不等于到位或可继续松爪 | 前置整段IK、奇异性/软限位、必要时限制运动；以**真实TCP位移、角度/到位证据**判定完成，不能靠MoveL接受返回 |
| 多次把\`observed_support_*\`误检列入豁免；11-11现场纠正“并非误检” | 宽前缀删除可能掩盖真实桌面/隔板 | 白名单绑定station+scene_epoch+物理确认；不沿用另一个工位的鬼影家族；\`goal_collision_waiver\`和\`false_positive_voxels\`不能因复制配置自动继承为客户可执行策略；未知/真实障碍保留并fail-closed |
| demo5 x−55mm退让触及j3软限位−125°，使用x−40mm；旧回center末段保护停 | 假定所有对象都能用55mm退出导致限位/结构干涉 | 退让是独立受控阶段；实际可达距离和净空要提前验证，若自动截短必须将“实际退让距离/是否脱离接触区”作为完成条件，不得只看命令成功 |
| 回center曾\`errcode=4128769\`、旧末拍误判fault；11-12修复后3次新鲜到位读数确认 | ROS Action如果把开始/结束状态混淆，会误报完成或误报失败 | 实际Servo退出 + 多次新鲜到位读数 + 保留原失败证据；ROS \`SUCCEEDED\`只有真实ARRIVED_CONFIRMED |
| pick/hold的旧golden后来切换到\`tcp3\`、zero TCP bias、0.2rad/s | 历史成功不能认证新配置；相机偏置与工具偏置混淆 | 每个Block的profile/evidence hash绑定；改变tool/TCP、姿态补偿、速度、payload就降级\`REACCEPT_REQUIRED\` |
| 旧任务已有STOP后不确认、重复dispatch、后台planner晚到结果等教训 | 重试造成重复机械动作、继续控制或旧轨迹执行 | 命令拥有者唯一、request_id幂等、停止回执、场景/版本epoch、native派发前hash；中止保留\`UNKNOWN\`现场核对 |

特别指出：当前site参数中有些DMP下降模式设置\`CONTROLLER_LINEAR_MOVE\`，而文档明确说明它**不经过cuRobo的观测体素碰撞检查**；有的\`descent_axis_gate_enabled=false\`。在这些条件下，不得因为\`scene check\`或\`controller acceptance\`为PASS就标为可自动发布。接触合法区、扫掠净空/软限位、垂直/退出路径应作为独立门；真实保护停不能通过ROS自动清除。

## 5. 目录结构：短期复用现有包，长期可拆分

建议短期：

\`\`\`text
ros1/ares_r_demo_bridge/
  action/
    ReturnCenter.action           # 已验收v0.2，保持原MD5
    RunBlock.action               # 新增：多功能块通用Goal/Feedback/Result
  srv/
    ListBlocks.srv                # 只读能力清单（第一阶段也可先HTTP）
    GetBlockStatus.srv            # 只读单次Job状态
  scripts/
    return_center_node.py         # 现有不重写
    run_block_node.py             # 一个统一Action入口
    run_block_client.py           # 供甲方/同事测试
    test_run_block_offline.py     # fake backend，无设备
  launch/
    return_center.launch
    manipulation_blocks.launch
  config/
    blocks.yaml                   # 仅allowlisted block + profile rev
  README.md                       # 接口/取消/错误码/环境/现场命令

src/ares_r/manipulation/
  ros_block_registry.py           # block → canonical demo/stage + profile/预检
  ros_block_contract.py           # 幂等、持物交接、状态、错误分类
  # 重用已部署Demo执行器/SceneAware/Device backend，不复制规划和控制

config/ros_blocks/
  pick_tray_v1.json
  pick_sieve_v1.json
  place_sieve_dmp_v1.json
  place_tray_dmp_v1.json
  place_tray_dryer_v1.json

tests/ros_contract/
  test_registry_versions.py
  test_action_goal_and_busy.py
  test_pick_payload_handoff.py
  test_place_payload_and_release.py
  test_stop_uncertain_restart.py
  test_site_profile_consistency.py

release/ros1-manipulation-blocks/
  VERSION
  MANIFEST.json                   # repo/worker/tool/calibration/native/profile hash
  CAPABILITIES.json               # 状态: RELEASED / REACCEPT / CANDIDATE / DISABLED
  INSTALL.md
  CLIENT_INTEGRATION.md
  SAFETY_AND_RECOVERY.md
  ACCEPTANCE_MATRIX.md
  OFFLINE_RESULTS.md
  onsite-evidence-index.json      # 指针/哈希，不入库原始隐私图像
\`\`\`

中长期可将Action/Msg/Srv单独抽为 \`ares_r_interfaces\`，桥接节点放 \`ares_r_ros_bridge\`，动作/规划运行时留在非ROS Python包。这不是返场前置条件。

**甲方适配：** \`nodeapp/modules/mission\`继续拥有Mission和底盘。建议新\`AresManipulationAction\`经Mqc/局部Python actionlib sidecar调用ROS1动作；异步轮询/事件映射，不用 \`execSync\`字符串命令。当前ROS Master为loopback \`127.0.0.1:11321\`，甲方若异机部署需决定ROS网络配置或在ARES主机运行受控bridge；不得在未审批情况下把ROS master/控制HTTP开放到生产网段。**旧\`/process/entry\`的srv类型及state编号未确认，不能把新block直接映射为其整数。**

ROS Noetic在2025-05-31已EOL；因为甲方现有工程用ROS1，近期交付保留已运行的Noetic环境并冻结依赖，未来预留ROS2适配接口，不在本次返场期间整体迁移。

## 6. 分层验收与发布标准

**一个block只有当新版参数 + 真实后端 + 真实设备 + 后置条件共同成立才标\`ACCEPTED\`：**

- L0 静态：唯一目录/参数，source hash，固定ROS Goal/Result/反馈，catkin能编译，Golden未变；
- L1 纯离线：模拟ROS Action → canonical假后端的成功/失败/取消/超时、旧request_id重发、BUSY、节点重启，零物理I/O；
- L2 现场无运动：真实底盘静止+工具状态、相机ID、偏置/目标、SceneSnapshot、起终点和受限接触/退出路径的规划预检；
- L3 现场监督单块：真实native/JAKA/夹爪，完成扫描→取或放→实际确认；每条异常留下明确停止状态，真实故障不自动续跑；
- L4 甲方集成：甲方Mission异步启动block、接收Feedback和Result，再控制自身底盘，然后Place；取消、掉线、重复请求、保护停、空抓、误检、释放不确定均能正确阻止错误下一步。

每个block交付一条\`ACCEPTANCE_MATRIX\`记录：\`block_id, profile_sha, backend_sha, tool_id, station, object/slot, test_levels, latest_real_run_id, success_evidence, stop_test, failure_exceptions, operator_approved, status\`。

**不接受的“成功”：** 只有HTTP 200/ROS Goal accepted；脚本退出0但无native到位；空载模拟成功；运行了旧参数; MoveL accepted但未运动；抓取旧payload持有但后来变成未知; 停止命令发出但Servo未确认静止；靠手工clear 983092后接续却标为原请求自动完整成功。

## 7. 推进顺序与两天现场任务

### 返场前/第一轮Codex：接口与资产闭合（只离线）

1. 对照 \`release/site-source-20261112/\` 和根目录，对所有拟交付block列\`effective code path/config SHA\`；**立刻修正 catalog 与参数 V7 D20 的差异**，禁止把历史README当唯一生效值。选择性把需要的现场代码接回正式可运行树，不能把snapshot覆盖production/golden。
2. 保持\`ReturnCenter.action\`已验收版本不变；新增一个ROS \`RunBlock.action\`+BlockRegistry+假后端测试；客户端示例独立运行。更改Action消息后必须重新catkin编译客户端。
3. 不先写第二套机械臂算法。复用真实 DemoConsole 的startup、status、cancel、日志与全局占用；补\`request_id→run_id\`幂等映射和绝对时限；重启无自动重放。
4. 先构建\`payload_session\`持久对象并在新Pick/Place间可读，Place缺凭据必须拒绝；模拟外部底盘移动后强制fresh scene/真实stationarity验证。
5. 生成\`CAPABILITIES.json\`，候选未经新版验收默认只允许PLAN_ONLY/DRY_RUN，不允许ROS Motion Goal。

### 第一天现场：低风险能力验证，优先做可以交付的闭环

1. 不覆盖现场RC1；先版本/工具tcp3/site velocity/模型/native/revision一致性；确认11321 ROS master是否被别的程序占用，保留人工E-stop，初始只读。
2. 用已有\`/ares_r/return_center\`做一轮无载荷版本核对/无运动负例；此前11-12已有实机回归，可作为首个Accepted block。
3. 先验证tray或sieve中**可独立停止在HOLD230**的Pick block（不要沿原位放回的完整脚本自动松爪）；确认真实夹持、连续230mm、payload身份与持物状态持久化。
4. 在**不移动底盘**的相同站位做安全回归和ROS Cancel/FAULT/BUSY/repeated-id；若现场缺经过审核的载物转场扫掠，不承诺\`transport_handoff_ready\`。
5. 输出已物理验收block及详细错误案例；如果pick失败保留原golden回归，不强行把没验收的改成RELEASED。

### 第二天现场：Place与甲方集成

1. 优先选择一条几何/装置风险已确认、可监督且未自动删除真实障碍的Place（DMP筛网或料盘），单块完成SCAN→PREPLACE→DESCEND→RELEASE→RETREAT_CLEAR；后续再做烘干箱lower_middle的新偏置版本。
2. 针对11-09控制器983092、11-11奇异性、现实/误检对象区分，逐项复核；不得让“自动清故障”和“禁用全部桌面碰撞”成为交付策略。
3. 甲方Nodeapp新Mission Action调用：ROS Pick结果→甲方可选底盘动→ROS Place结果→ROS ReturnCenter；核对跨站payload_session、run_id、Stop/重试/掉线后状态。底盘路线本身不由ARES ROS规划或派发。
4. 封版导出ROS catkin package、配置manifest、客户调用样例、Block列表、操作/恢复手册和成功/失败原始证据索引，保留回退点。

**范围优先级：** 优先保证“1个已验收center + 1个已验收Pick + 1个已验收Place + 甲方可以顺序组合”真实交付。剩余place变体按配置/验收逐项增加。两个工作日无法诚实保证所有尚为CANDIDATE的放置块一起通过；未通过必须标CANDIDATE/PLAN_ONLY而非伪装可执行。

## 8. 明确的Codex实施任务

第一轮只做到：**\`RunBlock.action\` + 现有DemoConsole复用 + BLOCK_REGISTRY + 幂等/并发 + 模拟Action全通过 + 有效参数版本对齐 + 返回一个能够解释所有block状态的CLI/ROS能力清单**。保留旧ROS center不改、不运动。

第二轮：抽取并验收1个\`scan_pick_hold230\`、1个\`scan_place_release_retreat\`的正式独立Block，强制跨Goal payload_session 和安全前置/后置，进行离线回放及可视化，并准备现场检查表。

第三轮：真实现场版本/几何检查、授权、物理分块验收，最后由甲方Mission端到端回归。**每轮退出必须看新增可交付Block的真实状态，不看新增单测数量或Demo目录数量。**
