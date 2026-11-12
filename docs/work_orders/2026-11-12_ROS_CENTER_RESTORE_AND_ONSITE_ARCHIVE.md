# 2026-11-12 现场冲刺任务书：功能块01 Center→Restore + 离场资料保全 + ROS交付续航

> **执行主体**：现场/本机 Codex（必要时经授权只读SSH到 `.32`）。
> **基线**：`codex/ros1-return-center-20261112` @ `97bb2d784c7c86be8e3176bb7d06529e1ee1926a`；此前ROS v0.2 center实机到位证据已保全。
> **本文件所在分支**：`planning/20261112-ros1-manipulation-block-delivery`。这是**独立任务书**，不是可直接部署的运动程序。
> **最终目标**：今天优先完成功能块01的两段真实/模拟闭环，并在离开现场之前保全全部关键源码、配置、模型、原生程序、ROS产物及现场成功/失败证据，以便之后离线完成ROS取/放功能库封装。

## A. 今日目标及优先级（按次序，不要无限追加新研究）

**P0 先保全再改**：检查当前运行中任务/设备状态；保全真实现场当前版本、尚未同步的diff/untracked/ignored必要文件与ROS/SDK/场景证据；确保现有已成功ROS回center和Golden仍可回退。

**P1 功能块01扩展**：做一个**可接续的两段动作**：`ACTUAL_CURRENT → GLOBAL_CENTER → PINNED_SAVED_POSE`。第二段必须实际规划/执行、并读取新鲜真实状态确认到达，整个ROS任务才算SUCCEEDED。

**P2 离线与短时现场验收**：先非运动预检+Action假后端/故障测试；在现场操作员明确确认净空、未持物和急停后，完成一次有证据的“两段实机回归”（如现场环境允许）。

**P3 离场交接**：新增/变更源码到独立Git分支、push（仅不含私有信息/未授权资产）；原始点云/运行日志、SDK二进制、环境清单、外参存Mac私有保全包并做独立SHA校验；生成可供Ubuntu离线接手的索引和重放说明。

**P4 后续ROS模块接口铺垫**：仅将已确认的取/放模块登记为 `CANDIDATE` 或 `REACCEPT_REQUIRED`，不在现场剩余时段盲目批量将Demo改成ROS服务。后续参考 `docs/integration/2026-11-12_ARES_R_ROS1_MANIPULATION_BLOCK_DELIVERY_BLUEPRINT.md`。

## B. 理解当前实际源码（Codex先核对，不许猜现场运行版本）

- ROS1包 `ros1/ares_r_demo_bridge/`：现有 `/ares_r/return_center`，`ReturnCenter.action` v0.2 (Goal=request_id+两项现场确认；Result含arm/pose_id/outcome/details_json)。**当前动作在center到位后就终止**，它本身并不具有回原位第二腿。
- `ros1/ares_r_demo_bridge/scripts/return_center_node.py` 只调用 canonical HTTP8775 `/api/demo-console/start/status/stop`，无第二套JAKA SDK；实机ROS已跑通过 `front_right_high_axes_aligned → right/center`，3次fresh读数约2.051mm / 0.00294°。
- `scripts/run_return_center_demo.py` / `demos/right_arm_return_center_v1/parameters.json`：FORCE_RESCAN、FAST→QUALITY、现场速度上限0.2rad/s、当前关节/工具实时读数、150°每关节行程门、3mm/3°到位合同；起点在碰撞时拒绝；任一段绝不能复用旧轨迹。
- `src/ares_r/motion/scene_aware_motion.py` 的 `MotionRequest` **已经支持 `goal_joints_rad` 与 `MotionGoal`**；返回保存的实际关节姿态优先使用这条已存在的scene-aware cuRobo接口，不要新增直接MoveJ/固定joint jump。
- 保存位置有歧义：现场刚保存过 `right/front_right_high_axes_aligned` 等姿态，但这不等于当前开始执行时的姿态。必须从**现有真实姿态注册表/本次采样**读取，并将准确来源固定到本次Goal；禁止自行认定存在某个固定JSON路径。
- 现场执行源一般在 `.32:/home/yikun/ARES-R-RC1-20261019`，ROS master曾单独监听127.0.0.1:11321；**先读进程和service确认当前有效路径、master和workspace，不能因文档旧路径就重启/覆盖**。

## C. 功能块01正确语义：一项ROS任务，两次独立规划/执行

### C1. 姿态来源：必须支持两种明确模式

1. **`CAPTURE_START`**：在一切运动之前，冻结当前右臂**新鲜实测**六关节、BODY TCP SE(3)、tool_id/TCP、校准/底盘/station revision、左臂姿态、时间戳；然后 `当前 → center → 冻结的当前姿态`。这个模式是真正的“回原位往返”。
2. **`SAVED_POSE_REF`**：用户已有一个**明确保存的命名姿态/快照**，Goal需指定保存姿态ID及预期版本SHA；机器人从任意**当前**位姿先到center，再到该**事先保存的姿态**。例如此前演示用 `right/front_right_high_axes_aligned`，**实际能否引用要先验证该条记录当前真实存在且内容完整**。

两种模式不能隐式互换；Goal保存的target若后来被改写，拒绝并返回 `SAVED_POSE_REVISION_CHANGED`，绝不静默选择“最新姿态”。如果尚未确认用户此前保存的姿态位于哪个ROS/ART注册表，Codex应先只读核查并保存真实记录；没有记录时可选**现场明确指定**CAPTURE_START，不自行编造目标。

### C2. 建议的两腿状态机

```text
ADMITTED / ONE_CANONICAL_JOB
  → PRECHECK_EMPTY_HAND + BASE_STATIONARY + TOOL/CONTROLLER/LEFT_ARM_HEALTH
  → SAVE_AND_PIN_RESTORE_TARGET (id/sha; actual joints + body TCP + tool/base/state)
  → PLAN_CURRENT_TO_CENTER (fresh scene, cuRobo, native+dense validation)
  → EXECUTE_CURRENT_TO_CENTER
  → SETTLE_AND_VERIFY_CENTER (Servo退出 + fresh state连续到位)
  → PLAN_CENTER_TO_SAVED_POSE (fresh robot joints + scene, NEW cuRobo plan)
  → EXECUTE_CENTER_TO_SAVED_POSE
  → SETTLE_AND_VERIFY_SAVED_POSE (actual joints + BODY TCP + tool)
  → COMPLETED (only both legs verified)
或: FAULT / STOP_REQUESTED / STOP_UNCONFIRMED / RECOVERY_REQUIRED
```

细节：
- 两腿由**同一个canonical job / request_id / run_id / 全局运动排他锁**拥有，不能ROS先发一次旧return_center再发第二次孤立动作，否则取消/掉线时归属分裂。
- 如果初始就在center，第一腿可返回 `ALREADY_AT_CENTER` 并继续第二腿，**不能提前结束整个任务**；若目标也为center则两次fresh确认后允许合法no-motion成功。
- 新保存目标首选**原六关节**为精确姿态目标，同时保存原BODY TCP供交叉验证；TCP到位但IK跳到不同腕部支路，不应伪称已返回保存的关节姿态。对周期角等价分支允许与真实软限位/控制器姿态合同一致的显式规范化，并在证据中记录，不能私自换支路。
- 第二腿必须从到达center后的**实时关节**出发，重新检查控制器与场景/底盘状态，重新cuRobo规划→独立验证→native时间参数化→当次发送；不可倒放第一腿轨迹、不可直接`MoveJ`跳回保存关节、不可用旧观测或旧plan。
- 整个功能块**不能移动底盘**。底盘修订或实际位姿改变，或者saved pose绑定的tool/TCP、标定、安装变换失效时，拒绝第二腿/要求人工重新确认。
- 初版只支持**空手且确认夹爪无负载**。当前`return_center`没有经验证的attached payload路径；持物状态未知则拒绝，不把任意持物姿态回原位列为已认证功能。
- 维持每段实际有效关节软/硬限位、速度/加速度、150° native单段限额、中心禁区现行策略、碰撞和路径验证；若保存姿态需超过单腿限额，则安全拒绝/留在已到达姿态，不允许以修改阈值、自动添加随意waypoint或越过控制器保护解决。
- 终点必须**真实**达到；至少使用已验证的center 3mm/3°与稳定新鲜读数标准，并对saved目标另核对六关节（复用或更严格地界定现有arrival contract）、tool_id、BODY TCP位置及姿态，记录实际误差和样本序列。绝不能只看HTTP 200或ROS accepted。
- center到位而返程失败时返回 `CENTER_ARRIVED_RESTORE_FAILED` / `PARTIAL`，保留center真实状态、不自动执行其它姿态；取消/事故不自动继续返程。

### C3. ROS兼容方式（别破坏已成功Action）

- **保留** `/ares_r/return_center` 和已验收 `ReturnCenter.action` v0.2原语义与消息MD5不变，作为安全兼容/Golden子技能。
- 新增专用功能块 `utility.center_restore.right.v1`，建议ROS Action `/ares_r/center_restore` + 新 `CenterRestore.action`，Goal含 `request_id,target_mode,saved_pose_id,expected_saved_pose_sha,onsite_observer_confirmed,prepared_environment_confirmed`，反馈含两腿`stage/phase/run_id/elapsed`，Result含 `success,terminal_state,return_to_saved_pose_verified,center_arrival,saved_arrival,run_id,evidence_uri,error_code`。
- 对甲方宣称的“功能块01”可在能力目录中将默认新接口映射到 `center_restore`，旧 `return_center` 保留为显式只回center工具；之后再统一到 `RunBlock.action`，不必为了今天交付先完成整个ROS功能库。
- 新Action节点仍只经HTTP8775 canonical Demo后端创建**同一两腿Job**，不自有JAKA控制；不得一个ROS Goal拆成两个互不关联的HTTP start。新ROS/Node进程启动本身不得运动。
- ROS `request_id` 必须持久幂等；相同ID重发只返回原任务状态；新的goal若占用中返回BUSY，不能由SimpleActionServer自动抢占正在运动的老goal；取消只停止本任务并确认native实际静止；已派发但回执不明时保持`UNCERTAIN`而不重发。
- 新Action message须在独立catkin workspace编译，客户端按新类型编译/source；不更改原ReturnCenter消息字段。甲方旧nodeapp不要求今天一起改完。

## D. 今天先做什么，再做什么（时间短也有可交付结果）

### D0（立即；无运动）保存现场当前真相

1. 在`.32`只读记录：`hostname, date, git HEAD/status/diff/untracked/ignored, effective source path, systemd ExecStart, running PIDs+cmdline, ROS_MASTER_URI/rosnode, actual tool/TCP, site velocity, loaded URDF/robot.yml/sphere model, cuRobo/Torch/CUDA/Warp versions, current sender executable/SDK hashes`。不在正在运行的生产树 `git checkout/reset/clean`。
2. 同步本次ROS实机成功run及历史失败run对应完整目录（包括原始telemetry、TF/FK、planner_request/planning.json、SceneSnapshot/点云、native源和目标文件、sender feedback、Stop/保护停日志）；首次保全采用**只读复制**，不得删改现场源文件。
3. 保存此前命名姿态 `front_right_high_axes_aligned` 或本次现场保存姿态在真实注册表中的**完整结构与来源**，核对单位/关节圈数、工具、BODY TCP和修改时间；生成相应 `saved_pose_record.json` + SHA。注意不要把固定站位/姿态当跨工位有效。
4. 对已有私有归档 `/Users/andyee/Documents/ChatGPT/local/site-private-20261112-offline-handoff/` 做增量比对；它已归档703份现场源码与134份依赖/证据，但**不保证包含本任务新产生的姿态注册记录和两腿结果**。新证据采用带SHA的增量包，不改旧归档内容。

### D1（离线优先）构造两腿执行器

1. 保留现有回center脚本/ROS桥为Golden；在独立工作树新增 `right_arm_center_restore_v1` runner（或同等薄封装），调用现有 `scene_aware_motion`/native/arrival/canonical接口。
2. 不另造运动算法。将 `center_goal`, plan/dispatch/arrive的共享逻辑抽为可复用纯helper，第二腿使用 `goal_joints_rad` 或经验证的显式BODY姿态+精确关节目标；先用完整真实关节证据作离线回放。
3. 无运动 `--prepare` 要能够捕获/固定目标、检查双腿规划可行性（第二腿起点以center计划终点作SIMULATED rehearsal，必须明确标为预测，不算实时场景验证）、校验目标SHA和安全门；准备状态绝不执行。
4. 单Goal下保存 `job.json, saved_pose_record.json, center_leg/, restore_leg/, goal_binding.json, ros_feedback.jsonl, result.json`；每段分别记录计划/真实开始/实际到位/失败对象/耗时/轨迹SHA/控制器停止结果。
5. 先完成ROS fake HTTP transport：正常双成功、第一腿失败、center到位第二腿失败、ROS取消两腿、重复request_id、断开重连、START response lost、保存姿态已变、起点已在center、持物不明、控制器保护停、额外Goal BUSY，以及重启后不自动执行等。

### D2（仅现场人员明确确认后）最小实机双腿回归

1. 先用**已确认安全的保存姿态**做单次非运动准备，检查两段是否确实可规划（特别是从center到保存姿态的软限位、150°和真实障碍，不仅是IK终点）。确认工作区无物体/无载荷、base静止、左臂保持、控制器无errcode/保护停/drag、工具和标定有效；现场人员掌握硬急停。
2. 一次 ROS `CenterRestore` goal连续执行两腿：真实CURRENT→CENTER→SAVED；每段打印当前阶段，完成两次fresh到位读数、Servo退出及工具状态确认；保存实测终端关节/TCP误差与完整原生反馈。
3. 如果任一腿触发 `errcode=4128769 / 983092`、实际碰撞、进入奇异/软限位、未确认Stop或持物异常：立即停止并保留错误与当前状态，不自动清除控制器保护、不可为了过关降低障碍检查、不派发下一腿。
4. 第二腿完整结束且姿态被验证后，才输出 `CENTER_RESTORE_COMPLETED` / ROS `SUCCEEDED`；若时间不够做实机两腿，明确交付 `OFFLINE_ONLY / SITE_PENDING`，**不要把ROS单腿成功写成双腿成功**。

### D3（离场前必须完成）保存可在另一台电脑复现的最小资料

**代码包（审核后可push GitHub独立分支，不含私密字段）**：当前ROS包 `.action/.srv`、节点与客户端、launch/package.xml/CMakeLists、站点runner和测试、已审定demo/parameters/registry、演示目标的脱敏姿态结构示例、架构/操作文档、manifest、commit SHA、SDK引用而非二进制。

**私有数据/依赖包（Mac或批准的私有存储，禁止进入公共GitHub）**：最新两腿真实run、旧center ROS成功/FAULT及保护停run、RAW Epic/Pixel Pro frame和clean pointcloud、scene/compilation及工具/相机标定、site配置原文、真实saved pose record、URDF/STL/碰撞球完整资产、pinned robot.yml、Native sender实际二进制与编译日志、JAKA/Epic SDK已授权库/头、ROS工作空间生成消息定义与md5、Python各venv pip freeze/Torch-CUDA-cuRobo版本、实际启动服务文件和日志、当前运行时目标/姿态注册表。

**严禁push**：口令、令牌、私钥、SSH配置凭据、私人业务数据库、客户nodeapp原始代码、未经授权的厂商二进制、带敏感环境的原始照片/点云。对每个归档做字节SHA256、列总数、尺寸、来源、验证结果及可恢复性；GitHub只push安全脱敏索引。

**离线重建合同**：任何文件被遗漏，都列 `MISSING`，不把 `.gitignore`、一个SHA或聊天中数值冒充文件本身。保留三份映射：`repo_path → source SHA → runtime actual path`、`ROS Action MD5/ABI → built workspace`、`run_id → source/scene/native/feedback/pose evidence SHA`。

建议归档成果：
```text
docs/reports/2026-11-12_ONSITE_CENTER_RESTORE_AND_HANDOFF.md
docs/integration/2026-11-12_CENTER_RESTORE_API_CONTRACT.md
docs/integration/2026-11-12_ROS1_DELIVERY_ASSET_INDEX.md
release/ros1-blocks-center-restore/MANIFEST.json
release/ros1-blocks-center-restore/README.md
worklog/private-handoff-manifests/2026-11-12/*.json   # 仅脱敏摘要
```

### D4（时间允许时）为未来ROS取/放准备

- 比对根目录/11-12现场快照的6个候选功能块、params哈希和现场证据；先修正料盘DMP README/catalog旧D10与现行V7 D20不一致，以及烘干箱ID3偏置版本和误检体素安全白名单的继承风险；**不变更生产参数**。
- 输出每个块的 `ACCEPTED / REACCEPT_REQUIRED / CANDIDATE / PLAN_ONLY` 及其实际源文件位置、backend调用入口、required_tool_id、site velocity、payload state、问题和证据指针。
- 下次离线继续开发通用ROS `RunBlock.action`/ScanPick/ScanPlace，今天不因此占用已很少的现场实机窗口。

## E. 独立安全停止与故障处理合同（引用既有现场教训）

| 现实场景 | 必须行为 |
|---|---|
| 2026-11-12旧ROS回center曾因末端验证误报FAULT，但后有正式ARRIVED_CONFIRMED回归 | 保存旧FAULT和成功回归两份证据，不重写历史日志；新两腿每段实测核实到位 |
| 2026-11-06 center初次dispatch曾`errcode=4128769`、0采样无动作 | 只有核验ZERO_MOTION+控制器已健康+真实起点不变才允许按既有规则一次有界新规划；不得一般性自动重发 |
| 2026-11-09 DMP槽内退出或下降触发`983092`保护停 | `PROTECTIVE_STOP`立即停止，绝不尝试继续RETURN_SAVED，不清除故障 |
| cuRobo预测碰撞（含`INVALID_START/GOAL_COLLISION`）或近奇异/软限位 | 保留碰撞与轴信息；不通过全局删除体素/降低门限解决 |
| ROS Cancel/SSH断线/Action客户端超时 | STOP_REQUESTED≠已停；必须收到控制器真正停止/Servo退出/新鲜静止回读，才可解除占用；未确认报STOP_UNCONFIRMED |
| 请求重发/ROS节点自动重启 | 同request_id永不自动重跑已派发腿；持久化本次Goal与每腿command_id，先问后端已执行进度 |
| 任何阶段实际持物未知 | BLOCK01空手版本禁止运动；不能把center回程的空手几何用于带料运动 |

## F. Codex每轮必须交付的短报告（避免现场被大量文字拖住）

返回六个明确字段：

```text
CURRENT_SITE_RUNTIME_VERIFIED = YES/NO
SAVED_TARGET_CAPTURED_AND_PINNED = YES/NO + pose_id/sha/mode
ROS_CENTER_RESTORE_OFFLINE = PASS/FAIL + cases
ROS_CENTER_RESTORE_PHYSICAL = BOTH_LEGS_PASS / PARTIAL / NOT_RUN
PRIVATE_HANDOFF_ARCHIVE_VERIFIED = YES/NO + counts/sha/locations
PUBLIC_CODE_PUSHED = YES/NO + branch/sha
```

报告中至少列两腿 `source/target q、BODY TCP、tool、planner start/goal/scene、native SHA、真实controller ACK/Servo状态、新鲜最终误差、Stop与故障证据`；不能把独立的一腿ReturnCenter成功当两腿完成。

## G. 行动纪律与停止条件

- **立即开始做**：只读站点检查、现有保存姿态定位、数据保全和离线实现。无需再向用户索要已知的目录/分支/服务器地址。
- **真实运动**：只能在现场明确操作员授权、净空确认和可用急停情况下进行；没有新鲜状态/可靠目标时不派发。不得因追求进度关闭碰撞/故障/Servo/限位检查。
- 不让Codex为了微小耗时优化重复跑大量GPU benchmark。先把两腿的稳定语义、真实验证和离场资料做齐。
- 不碰现有Golden和原ROS `/ares_r/return_center` MD5；只用新分支/新demo/action，确认回退路径后部署。
- 时间紧张时优先排序：**保全现场不可再得的材料 → 实现/离线验证两腿 → 现场有监督一次双腿 → 增量保全结果并push → 后续ROS功能块清单**。如果剩余现场时间不足，宁可带走真实资料和清晰 `SITE_PENDING`，也不能假报双腿已验收。

## H. 可立即定位的主要源码

- `ros1/ares_r_demo_bridge/action/ReturnCenter.action`（旧接口不改）；`scripts/return_center_node.py`；`scripts/test_bridge_offline.py`
- `scripts/run_return_center_demo.py`、`demos/right_arm_return_center_v1/parameters.json`、`demos/right_arm_return_center_v1/demo.json`（以现场有效源为准）
- `src/ares_r/motion/scene_aware_motion.py` 的 `MotionRequest.goal_joints_rad`、`MotionGoal`，`src/ares_r/manipulation/task_contract.py:center_goal`、`src/ares_r/motion/arrival_contract.py`
- `src/ares_r/demos/console.py`、`src/ares_r/demos/registry.py`、`src/ares_r/canonical_backend.py`（唯一任务拥有者与后台状态）
- `config/named_poses.json`、现场已保存pose registry与当前tool/TCP、`config/jaka_mini2_motion.site.json`
- `docs/reports/2026-11-12_OFFLINE_HANDOFF.md`、`release/site-source-20261112/`、`docs/integration/2026-11-12_CLIENT_NODEAPP_ROS_INTEGRATION_REFERENCE.md`

**最终结论必须是完整两腿证据与可离线重建的资产清单，不是又写一个“待做”报告。**