# ARES-R Roundtrip RC1 — 两天现场操作手册

本包的默认入口是硬件隔离的 SYNTHETIC_GPU_REPLAY。真实 cuRobo、IK、独立碰撞验证和 native 打包参与正式19阶段 CycleRunner；设备、视觉证据和安装变换是合成输入。它不是10月16日实机复现，也没有证明现场85cm横移或不收臂返程净空。现场运行必须另行通过原有显式授权入口与版本检查。

## 返场前 / Ubuntu 一键复核

在本仓库根目录使用已有健康 `.venv`。Python/Torch/CUDA/cuRobo/Warp版本和模型哈希见 manifest.json、RESULTS.json。只使用 GPU0。运行目录必须全新，resume 使用同一目录。

```bash
.venv/bin/python scripts/roundtrip_rc.py start --run-dir worklog/runtime/my-demo
.venv/bin/python scripts/roundtrip_rc.py status --run-dir worklog/runtime/my-demo
.venv/bin/python scripts/roundtrip_rc.py stop --run-dir worklog/runtime/my-demo
# Stop 锁存需检查故障和设备状态后显式清除；清除不触发运动。
.venv/bin/python scripts/roundtrip_rc.py clear-stop --run-dir worklog/runtime/my-demo
.venv/bin/python scripts/roundtrip_rc.py resume --run-dir worklog/runtime/my-demo
# 一键串行完整GPU闭环、检查点和故障验收：
.venv/bin/python scripts/validate_roundtrip_rc.py --output worklog/runtime/new-campaign
.venv/bin/python scripts/roundtrip_deploy_check.py --output worklog/runtime/deploy-check.json
```

新 checkout 的离线模型可由随包原始资产重建，不需要访问其他 GPU 或硬件：

```bash
.venv/bin/python scripts/prepare_curobo_model.py worklog/runtime/preview-model --source-directory release/roundtrip-rc1/assets/preview-source
```

脚本拒绝覆盖现有模型。cuRobo源码缓存缺失时，在联网准备环境用 `scripts/fetch_curobo_source.py worklog/runtime/curobo-pinned` 获取固定提交并安装到独立虚拟环境；GPU环境版本见manifest。网络隔离测试中不安装依赖或下载资产。

CLI 自动进入 bubblewrap 隔离：独立网络命名空间、无 USB/ACM 串口、只映射 GPU0，真实 CapabilityProvider.execute 拒绝执行。不要启动生产 systemd、Epic、真实运动或自动任务。首次 CUDA/新持物上下文冷启动明确采用45秒初始化预算；相同上下文 FAST 结果预算4秒。Stop/超时回收所属规划子进程，停止后不发布晚到结果。一个 canonical owner、run_id 和 job.json 供 CLI/WebUI/ART 共用；WebUI 可选 SYNTHETIC_GPU_REPLAY，ART `task status` 读取同一任务。19阶段的 GPU 规划由任务自身连续调用。

## 固定路线及每阶段恢复

|阶段|实际计算/模拟执行|恢复规则|
|---|---|---|
|PICK_PREPARE|ID1合成观测、真实完整contact/lift预检、真实cuRobo current→pregrasp、native打包|输入/模型/场景/起点失效才重新观测和规划；预检分支哈希绑定contact/lift|
|MOVE_PREGRASP|真实轨迹，设备模拟，SETTLING→ARRIVED|已到位不重发；失去确认阻止自动恢复|
|GRIPPER40|模拟张爪|已完成不重发|
|CONTACT_APPROACH|真实native contact，设备模拟|已到位不重发|
|CLOSE|模拟闭爪|候选不等于抓取确认；不重发|
|VERIFY_GRASP|HOLD_CANDIDATE，模拟时间戳与场景证据|未抬升时新增点不直接卡死流程|
|LIFT_INITIAL100|真实native 100mm，设备模拟到位|LIFT100_ARRIVED 可恢复，不重复抬升|
|ATTACH|抬升后 GRASP_CONFIRMED；所有权过滤、SceneSnapshot、cuRobo/独立校验一致|证据不确定即停；不得把桌面/隔板/dock删掉|
|LIFT_TO_HOLD230|真实持物cuRobo规划到绝对230mm目标|HOLD230 可恢复，不再相对抬升|
|TO_PLACE_back_030|模拟底盘−30cm|凭独立完成凭据跳过已完成移动|
|TO_PLACE_right_085|模拟底盘−85cm|响应丢失按command_id核对，不盲重发|
|TO_PLACE_forward_030|模拟底盘+30cm|BASE_AT_PLACE 可恢复|
|FRESH_ID3_OFFSET_PRELAND|PLACE新场景、ID3、lower_middle偏置+40mm；合成输入|base/scene变化使目标失效|
|MOVE_PRELAND|真实持物cuRobo与独立校验；模拟到位|到位后不重发|
|RELEASE|模拟释放与确认|释放结果不确定禁止自动重发和detach|
|DETACH|确认释放后清除持物；场景失效|无确认不得执行|
|RETREAT_BASE030|模拟−30cm，不收臂|现场扫掠待验收|
|RETURN_LEFT085|模拟逆横移+85cm，不收臂|现场扫掠待验收|
|RETURN_FORWARD030|模拟+30cm，COMPLETED|完成任务禁止resume|

原始/native轨迹、限制关节、stretch、密集碰撞/姿态和动态证明写入每次运行的 native/、plan_*/。events.json 提供每阶段墙钟；GPU调用与显存写入 gpu_calls.json。设备瞬时模拟的墙钟不代表实机周期；瀑布包含 native 规划时长和底盘名义29秒的周期估计，不作现场保证。

## 第一天：版本与几何验收

1. 先备份 `.32` 当前源码提交、配置、SDK、native binary、service单元及关键资产的哈希和实际路径。在独立新目录部署RC，不覆盖原golden first-pick或integration/source-delivery分支，不自动启动服务。
2. 在 `.32` 运行 `roundtrip_deploy_check.py --require-site --site-evidence <证据索引.json>`。SITE_PENDING 不得手动改成PASS；索引每项包含 status、实测证据path、sha256。源码路径应与 manifest 完全一致。
3. 补齐10月16日原始点云/反馈、现场URDF、TCP、碰撞球覆盖、左右工具和标定。preview commissioned=false，只允许离线。使用现场SDK重新编译 native sender、校验版本/源码/二进制哈希和 validate-supervised-path；新源码新增两次稳定读数的settling。原sender哈希门禁保持，未经审核的重编译二进制不会自动获准。
4. 实测地图坐标/BODY方向和 GRASP↔PLACE 三段：−30cm、−85cm、+30cm；验证载物230mm高度的扫掠包络与平台、dock、隔板净空。审核 ID3 lower_middle 的偏置坐标系、TCP姿态和释放点+40mm。
5. 专门检查释放后原姿态不收臂逆路线：全机器人与已放置物、舱门、dock、桌面包络，不能由规划单臂终点或Mock底盘通过推导净空。现场10GB级显存需与视觉/服务并发测量；独立离线GPU峰值不是并发占用上限。
6. 有人监护、物理急停有效后按现有授权流程分段验证，保留真实时间戳、跟踪、动力学、到位和握持证据。任何不确定状态先停止。

## 第二天：闭环及恢复验收

1. 确认第一天证据完整、版本无漂移。检查物理Stop和软件Stop、左臂只读短暂失败、到位迟滞、网络响应丢失；必须通过实际遥测核对，不根据HTTP成功推断运动完成。
2. 以批准参数启动现有正式 `run_grasp_place_roundtrip.py --execute` / WebUI SITE 入口。现场授权仍需现场观察者、review批准、TTY及原先所有限制；本包没有自动授权部署。
3. 分别在 LIFT100_ARRIVED、GRASP_CONFIRMED、HOLD230、BASE_AT_PLACE 停止并恢复。实际左右关节/工具、底盘地图位姿和持物状态不符即停。已派发却没有完整成功证据的命令保持 UNCERTAIN，必须现场核对后再决定，不能清空记录强行重试。
4. 连续完整循环并保存逐阶段时间、显存、场景和恢复证据。未达到稳定要求继续标SITE_PENDING，保留原golden可回退入口。

## 显存与维护

规划工作进程仅一个，Torch allocator fraction=.75（本机约7.75GB上限），不是显卡总占用预留机制。CUDA/Warp/视觉还会占显存。查看 RESULTS 的实测 allocated/reserved 与规模；不得把小合成场景占用当现场10GB级并发证明。OOM/超时销毁所属上下文后才允许重试，不留孤儿计算。NVML 580.178.04 与已加载内核580.173.02不匹配单列维护；CUDA正常期间不重装/重启。停机维护时对齐用户态库/内核模块后重新检查CUDA与NVML。

## 回退

停止新任务并核对真实静止/夹持状态，保存job、command_records、原始遥测和日志。停止此次RC自己启动的进程，禁止 kill-all GPU。切回事先保留的原部署目录及备份配置/二进制；按原部署步骤显式启动服务。不要对开发树 git reset，不覆盖golden，不把RC的pending命令记录清除后重跑。恢复失败的现场命令需要人工核对真实设备状态。本包的SITE_PENDING没有软件方式可绕过。
