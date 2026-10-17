# 完整抓放 Demo 逐阶段代码与执行参考

日期：2026-10-17。与[故障审计报告](../reports/2026-10-17_ROUNDTRIP_DEMO_FAILURE_AND_GATE_AUDIT.md)一起阅读。本文件是离线审计说明，不是要求立即运行的工作单。

## 1 版本范围和证据

代码行号以`worklog/audits/2026-10-17-roundtrip-offline/source_snapshot/`冻结源码为准；对应[函数索引](../../worklog/audits/2026-10-17-roundtrip-offline/FUNCTION_INDEX.md)提供全部函数起止行和签名。[JSON索引](../../worklog/audits/2026-10-17-roundtrip-offline/source_inventory.json)包含每个函数调用名、所有if/raise、等待和timeout，以及源码SHA。

没有现场原文件的条目采用CHAT_TOOL_EVIDENCE，不冒充重跑的benchmark。所有资源预算未注明实测的均为ESTIMATE。时间区间不是统计置信区间，也不是p50/p95。

这条Demo是19阶段自定义`CycleRunner`，**不是已证明完整接入P3.9 SkillRuntime的Tray→Groove生产Scheme**。不要因为仓库中有SkillRegistry/Task Studio/ExecutionLease就认为此入口必然调用了它们。

## 2 客户期望合同

```text
GRASP站
  ID1检测 + Pixel Pro观测
  current → pregrasp（cuRobo自由空间，终点为抓取姿态）
  gripper40% → 55mm受约束接近 → close
  抓稳确认
  水平抬升总230mm（现实现100mm contact lift + 130mm attached free-space）
  底盘后退300mm → 右移850mm → 前进300mm → PLACE
  ID3检测烘干机参考角 → lower_middle偏置 → BODY Z+40mm
  水平持物运动到preland → 直接释放
  底盘后退300mm → 左移850mm → 前进300mm → 新GRASP
  HOLD；不收臂、不边开底盘边动臂
```

850mm是本轮GRASP向BODY +Y移动100mm、PLACE不变后的命令路线；历史是750mm。底盘回程是已定义三段的逆序逆向，不是任意地图自动导航。当前路线不是精密SLAM站位commissioning。

## 3 单位 坐标和姿态

- BODY原点：双臂基座中心连线中点正下方地面；+X前、+Y左、+Z上。
- 两臂基座历史固定关系见`config/robot_world.json`；不要用旧聊天里的120mm替代实际已修正的约120cm高度。
- 运动接口位置：m；joint：rad；展示角度常为deg；JAKA TCP平移字段：mm；5700内部返回依profile和协议解析。
- “夹爪朝前/水平”是**物理夹爪轴的定义**，不是简单把controller TCP的RPY都设0。见`motion/tcp_orientation.py`的`HORIZONTAL_FORWARD_R_BODY`、`level_rotation()`和`validate_level_path()`。
- 用户给定检测轴关系的名义旋转：检测+Z约BODY+X、检测+X约BODY−Y、检测+Y约BODY−Z；实际应使用fresh检测完整SE3，不用名义轴替换真实外参。
- 放置偏置必须明确在检测坐标还是BODY坐标；正式下发前转换成唯一SE3。既有`offset_frames.py`提供转换。
- `LEVEL_YAW_TARGET`锁水平并以yaw=0为目标，较`LEVEL_YAW_FREE`更强；可达性不同，不能不告知就互换。
- 夹爪40%在此用raw400，闭合raw0、释放raw400；不保证raw与物理毫米线性，尤其“闭合raw0但读数37”不等于抓空。

## 4 入口和跨进程调用图

```text
WebUI roundtrip_panel.js
  GET /api/demo/roundtrip/status
  POST /api/demo/roundtrip/start
    webui/server.py Handler.do_POST
      CanonicalBackendClient → :8766 /v1/call
        CanonicalBackend.roundtrip_start
          RoundtripLauncher.start
            freeze route + parameters + slot offset + authorization
            PTY + subprocess run_grasp_place_roundtrip.py
              recipe → CycleRunner.run → Live.<stage>

ART/CLI → canonical backend（通用scene/motion）
Demo目录注册 → demos/registry.py（目录/状态能力）
自定义完整Demo的实机启动目前还有专用HTTP入口，不应误称完全统一TaskRuntime。
```

默认页面8765、canonical backend8766。`Live.post()`仍绕回8765，再代理到8766；可减少一跳，但不能绕过资源占用、授权和绑定。

### 入口文件位置

| 文件与函数 | 位置 | 关键行为 |
|---|---|---|
| `webui/roundtrip_panel.js` | 整文件，冻结副本及索引列出fetch/disabled位置 | checkbox、start/stop、状态轮询；网络错误不等于任务停机 |
| `webui/server.py:Handler.do_GET/do_POST` | L124 / L166 | HTTP转发；异常可能被简化为409 |
| `canonical_backend.py:CanonicalBackend.roundtrip_start/status` | L193 / L199 | 正式启动与状态 |
| `demos/roundtrip_launcher.py:contract` | L29 | 参数/路线/slot hash、资产和stop latch |
| `RoundtripLauncher.start` | L92 | 一次授权冻结副本、PTY Popen、web_launch元数据 |
| `RoundtripLauncher.status/_running` | L61 / L54 | 只跟踪某entrypoint进程，临时恢复入口未统一纳管 |
| `roundtrip_demo.py:recipe/CycleRunner.run` | L42 / L106 | 19阶段串行循环；任意异常FAULT并stop |
| `run_grasp_place_roundtrip.py:main` | L302 | prepare/replay/execute/stop、TTY、run.lock、active.json |

## 5 19阶段逐项审计

下列预算都按现配置串行执行。`ESTIMATE`不能直接相加当实测全周期；重试、排队、资源失败另计。

### S01 PICK_PREPARE

**调用**：`CycleRunner → Live.prepare_pick():91 → plan_with_retries → Live._prepare_pick_once():93`。

输入：参数快照、系统配置、旧template-plan作为模型/seed来源、新ID1命令；不能将template的scene和目标当fresh。

内部顺序：

1. 新建`pick_attempt_<n>_<mode>`。
2. 用`vendor/venv311/bin/python3.11`运行`capture_manipulation_observation.py --profile right_pick`。
3. `ManipulationObservationTransaction.capture()`：before双臂状态→5700→fresh scene→after双臂状态→稳定性与provenance→COMMITTED。
4. 每个before/after状态均启动两次`audit_curobo_fk.py`；scene内部还读取两臂，故**一次pick观测可有6份双臂单侧audit**，不是只读一次joint。
5. `prepare_authorized_first_pick.py`读取target、表面分解和当前模型，求NORMAL/FLIPPED pregrasp IK；将等价360°joint表示移到离live start近的范围内；构造world/ignore target IDs/envelope。
6. runner改请求的FAST或QUALITY参数、warmup policy，保存request，再调用persistent planner。
7. 成功后才调用`build_first_pick_execution_package.py`生成26点contact和51点初始lift。
8. `verify_first_pick_package()`校验包；检查contact/lift水平；检查sender hash；分别把pregrasp/contact/lift重采样并native validate。

输出：epoch、pregrasp planner request/result/log、preparation、不可变first-pick package、三个native preview和audit。目录内可能有迟到worker结果，是否可执行必须看当前job状态，不能看到SUCCESS文件就执行。

**计时**：本次成功run的整个准备约238.81秒；不是cuRobo单次solve。观测样本约12秒量级；同一会话ID1独立检测曾约2.16秒。没有本轮完整CPU/RAM采样。

**资源**：多Python环境、Open3D/NumPy/SciPy、磁盘点云、GPU planner；GPU实测峰值可接近10.6GiB worker显存。CPU峰值和系统RSS未知。建议离线预算：点云阶段2–6GiB主机内存、少量CPU核至多核突发，必须返场用RSS采样确认。

**失败**：相机超时、协议无目标、双臂SDK、epoch变化、模型资产缺失、target组件身份错误、IK、OOM、deadline、碰撞、包hash、senderhash、source/native dynamics、目录冲突。

**关键缺陷**：整个准备有大量可以前置的可行性、版本和资产检查；当前把contact IK放在昂贵pregrasp solve之后。

### S02 MOVE_PREGRASP

**调用**：`Live.pick_segment('pregrasp'):146`。

先`/api/operations/telemetry`取双臂及base；比较inactive-left关节变化≤0.02°、tool ID；right与首点≤0.2°；`base_stationarity()`三样本确认IDLE+marker；right tool ID必须1。随后invalidate scene，以新时间打包native，validate，执行sender。

原生sender还检查：SDK login、健康状态、queue/servo idle、user/tool一致、**起点≤0.02°**、snapshot未过期。上层0.2°不能替代原生0.02°。

输出：`pregrasp.execute.txt`、validate.log、execute.jsonl。必须有target_reached和servo_disabled=0，无failed/abort。

本次实测：计划36.08秒，阶段39.52秒，差约3.44秒含前置读数、SDK/打包/收尾，不是单纯串口等待。资源：原生sender+SDK连接；12.5Hz反馈/日志；控制器自身实时环，不是Python逐点ServoJ。

### S03 GRIPPER40

**调用**：`Live.gripper(raw400):182 → scripts/gripper_direct_once.py move`。

串口来自`config/system.json:grippers.right.port`，不硬猜USB。115200；写0x54命令，单次response长度要求7字节；sleep0.3秒；再0xD9读8字节。runner另等0.75秒，启动read脚本；实际位置至少400−20。

实测阶段约1.25秒。每个exchange最长约1秒，move/read为分开的进程与串口打开；ESTIMATE正常1–2秒，超时受调用10秒上界限制。

检查不足也要审：`exchange()`主要校验长度，主函数没有完整验证回包头、device、command和checksum；串口one-shot入口也没有这里显式的跨进程flock。不能既把raw当绝对真相，又没有完整帧/资源一致性校验。

### S04 CONTACT_APPROACH

**调用**：`Live.pick_segment('contact')`；不是新的cuRobo自由空间solve。

原始26点来自`build_first_pick_execution_package.py:56–68`，沿verified approach axis固定姿态，从55mm pregrasp线性到grasp，每点用`RuntimeGoalIK.solve()`接续seed。`validate_bypass_segment()`对arm links、非相邻自碰撞、inactive、joint limits、方向/长度作检查；只放行受控active gripper/tool与observed pointcloud配对。

当前stage速度cap0.05rad/s、加速度0.10rad/s²、tracking stop1.5°。文件1439点、80ms，计划115.04秒；首尾SDK与闭爪前后加上后，总阶段边界约119秒。后者不是“几秒的伸手动作”。

先检查IK和时间参数化。若改为cuRobo contact，必须有固定姿态/接近方向和目标接触合同，不能让cspace绕远路径侵入不该接触的结构。

### S05 CLOSE

**调用**：`Live.gripper(raw0)`。本函数close不做额外“非完全闭合证明”，后续verify负责。

期望输出不是raw0，而是收到可靠命令响应和当前position_raw；若夹有物体，读回37可以符合持物状态。ESTIMATE约0.3–1.5秒；实际本次未单独保留精确S05时间片，UNKNOWN。

### S06 VERIFY_GRASP

**调用**：`Live.verify_grasp():192`。

顺序：build_live_planning_scene（再次全扫）→间隔读回→写JSONL→`verify_authorized_first_pick.py`加载before/after clean residual→TCP周围150mm、5mm voxel delta→`verify_grasp_v1()`。

配置：removed≥20 voxels、removed_fraction≥0.15；added_fraction>0.50优先判UNEXPECTED；readback spread≤20，hold>closed+20。

本次10.23秒后FAIL：removed2/3、added0.520408，读回37/37/37；两个夹爪gate通过，视觉分类失败。**这里尚未抬升，点云遮挡/自体残差不能直接证明抓空。**

缺陷：半径/voxel/delay脚本硬编码与versioned参数并存；三次读回采样时刻被重写成同一now。建议拆VERIFY_HOLD_CANDIDATE、受控test-lift、VERIFY_GRASP_FINAL，以及manifest记录的一次性人工替代，而不是把全verify全局禁用。

### S07 LIFT_INITIAL100

**调用**：`Live.pick_segment('lift')`，原包51点，BODY+Z100mm、固定当前抓取姿态。stage cap0.20rad/s、accel0.20rad/s²；contact bypass在这一段末端到期。

风险/失败：实际抓取终点与预先算好的lift首点偏差、原生终点过早判断、模型/工具变化、joint限位、控制器故障、包日志重复。

本次正常主线没有运行到此；人工确认后恢复实际运行约75.69秒，native发送窗口约72秒，物理约100mm完成。sender末拍判final feedback mismatch；停稳后实际关节与目标误差极小，controller in_position=true、errcode0。不能说“抬升失败所以完全没动”，也不能说“全Demo成功”。

### S08 ATTACH

**调用**：`Live.attach():207`，赋`self.package['coarse_attached_object_collision']`。纯内存动作，ESTIMATE<0.01秒，不能把它当作已经执行了新的scene归属处理。

几何由`attach_scene_object()`/`build_attached_collision()`把target从BODY转TCP/link6，并围成保守link6 AABB。当前记录尺寸约135×220×231mm，inflation4mm、source observation/revision绑定。

**现有缺口**：赋值没有让后续scene自体过滤知道持物。planner收到attachment并不等于self-filter已处理attachment。

### S09 LIFT_TO_HOLD230

**调用**：`Live.lift_remaining(.13):250 → free_move(position,'HOLD230'):213`。

当前值为实时TCP位置Z加130mm；若S07实际抬升不是精确100mm，总位移不是从原grasp绝对算230mm；应定义容差和绝对hold目标，避免多次恢复叠加130mm。

`free_move`构造request：right、BODY position、LEVEL_YAW_TARGET、yaw0、environment ON、FORCE_RESCAN、FAST、right_scene_aware_0_20、attachment geometry/revision。通过`/api/motion/plan`，成功后读planning/request再作hard level，随后`/api/operations/execute`；轮询run-status，300秒监控deadline，要求SUCCEEDED且target_reached。

三次规划失败总约57.34秒；起点gap−62.26mm，终点+45.98mm。**没有执行这130mm。** 当前起点BODY约`[0.806839,-0.210777,1.090344]m`，目标约`[0.806839,-0.210777,1.220344]m`。这些是10月16日最后记录，不是今日实时位置。

正常时间UNKNOWN：当前实测没有成功S09；ESTIMATE 10–60秒规划/打包+10–80秒运动，区间宽是因为未验收，不应对客户宣称固定秒数。新目标、附件和scene容量可能创建新planner并占更多GPU。

### S10 TO_PLACE_back_030

**调用**：`Live.base([-.30,0,0]):253 → /api/operations/base-move`。

canonical backend负责LocalScene invalidate→AMR request→真实完成观察→SETTLED；不是request accepted即到站。runner收到SUCCEEDED后又做新的完成marker+稳定窗口。

名义纯移动下界3秒（0.30/0.10），ESTIMATE含起停与重复settle约8–18秒；不是严格保证。本次持物转场未执行，不能引用空载试验当持物commission。

### S11 TO_PLACE_right_085

**调用**：`Live.base([0,-.85,0])`。名义纯移动下界8.5秒；ESTIMATE含起停/完成/重复settle约14–25秒。原750mm为7.5秒，左移新GRASP后总净变化850mm。

PLACE“保持不变”在此是命令路线定义，不是AMR里高精度station坐标保证。此前SLAM噪声和真实return误差未分离，不能以多次盲补让误差累加。

### S12 TO_PLACE_forward_030

**调用**：`Live.base([.30,0,0])`。名义3秒，ESTIMATE8–18秒。完成后scene必须是SCENE_REQUIRED；持物和右臂保持HOLD的扫掠应按现场批准的姿态范围，而非任意姿态通用认证。

### S13 FRESH_ID3_OFFSET_PRELAND

**调用**：`Live.place_target(slot_id,height_m):273`。

取`/api/operations`当前lower_middle offset，与启动快照比较；取base revision和telemetry；EpicClient `_detect_profile(right_place_rightmost)`；检查success/pose、base revision未变。

位置链：

```text
T_body_slot = T_body_right_base × T_right_base_detected_reference × T_reference_slot
preland_xyz = translation(T_body_slot) + [0,0,0.040]m
orientation = level_rotation(yaw=0)，不是原始检测RPY照搬
```

offset格式存储见operations registry；本次UI启动示例值`[.315,-.238,.06,0,0,0]`应按当前offset frame/revision解释，不能直接当BODY delta相加。`config/robot_world.json`必须与Epic的armbase语义匹配。

输出：fresh detection ID/raw、slot/preland BODY xyz、registry revision、显示keypoint `roundtrip_preland`。显示marker不等于已规划或授权执行。

当前place detection不是同一个ManipulationObservationTransaction封装，只用前后base revision+一次telemetry；下一步free_move会另扫scene。目标/点云/机器人状态的同epoch绑定应补齐，而不是拿旧检测一直复用。

ESTIMATE ID3约2–4秒加状态/网络；**本轮没有成功全链到这里的实测**。

### S14 MOVE_PRELAND

**调用**：`Live.move_preland():299 → free_move(preland,'PRELAND40')`。

与S09同一generic scene/motion链，附着物仍在；每次尝试fresh scene。保持水平/yaw合同，不能因为目标在空中就跳过持物/隔板几何。

规划、打包、预检、执行分层见第6节。ESTIMATE正常30–180秒端到端（含未验证的当前fallback行为），优化后预算不是现状测量。实机尚未经过本轮路径，UNKNOWN。

### S15 RELEASE

**调用**：`Live.gripper(raw400)`，延迟readback须≥380后才返回。ESTIMATE1–2秒。

当前语义是TCP在slot+40mm时直接释放，不下降，不力控。**物体真正落差取决于grasp transform和物体底面，不等于40mm。** 本次现场接受这一特定实验，不代表泛化生产放置。

### S16 DETACH

**调用**：`Live.detach():210`，`attached=None`并invalidate OBJECT_RELEASED。ESTIMATE<1秒，HTTP/磁盘另计。

不应在release命令accepted但开度未确认时提前detach；也不应detach后沿用旧scene里被过滤的持物而不重建归属。

### S17 RETREAT_BASE030

**调用**：`Live.base([-.30,0,0])`，约3秒纯移动+完成/稳定开销。右臂不收臂。放置后的大扫掠净空需按实际姿态，不以“夹爪空载”替代。

### S18 RETURN_LEFT085

**调用**：`Live.base([0,.85,0])`，约8.5秒纯移动+起停/observer。

### S19 RETURN_FORWARD030

**调用**：`Live.base([.30,0,0])`，约3秒纯移动+observer。完成后`CycleRunner.run()`返回`RETURNED_GRASP`，但没有额外证明SLAM达到某个commissioned站位容差；客户验收应同时看实测地图状态和任务结果。

## 6 generic motion真正下沉的调用层

```text
Live.free_move
 → WebUI /api/motion/plan
 → SceneAwareDispatcher.motion_plan
 → SceneAwareMotionService.plan
   → operations policy归并
   → LocalSceneService.ensure_fresh
     → build_live_planning_scene
       → p32_scan_scene.py
         → capture_body_cloud
         → 左右audit_curobo_fk
         → export_whole_robot_geometry
         → build_p3_production_scene
           → mm→m / CAMERA→BODY / ROI / voxel
           → robot-owned filter / cleanup
           → support-object-unknown decomposition
           → SceneSnapshot / SceneCompiler / cuboids
   → PersistentCuroboPlanner.__call__
     → request/effective policy / model/tool/attachment
     → planner_service_client.plan
     → persistent_planner_service.serve
     → production_scene_worker.main
       → runtime cache/init / update_world
       → 可选full warmup / 正式solve(s)
       → CPU signed distance / dense验证 / serialize
   → evaluate_hard_validity
   → GenericNativePackager
 → Live再次hard level
 → /api/operations/execute
   → CanonicalBackend.motion_execute
   → scene_aware_execution.preflight
   → native supervised_path
 → target_reached / servo_disabled / run-status
```

### 调用层职责和代码位置

| 层 | 主要函数/位置 | 实际职责 |
|---|---|---|
| request解析 | `scene_aware_dispatch.py:_motion_request:24` | units、arm、goal、constraints、planning_mode |
| generic policy | `scene_aware_motion.py:SceneAwareMotionService.plan:250` | operations defaults、scene、planner、hard validation、打包 |
| scene生命周期 | `local_scene_service.py:scan:124 / ensure_fresh:173附近` | invalidation、epoch、TTL、fresh scene state |
| 相机/点云总入口 | `live_scene.py:build_live_planning_scene:24` | 固定只读subprocess pipeline、provenance checks |
| capture | `body_pointcloud.py:capture_body_cloud:245` | SDK/worker路径、原始单位、manifest |
| geometry | `perception/robot_collision.py` | 统一BODY geometry、robot-only self-filter |
| residue | `robot_owned_filter.py/residual_cloud.py/support_decomposition.py` | ROI/点云归属、清理与分解 |
| scene合同 | `world/scene_compiler.py` | collision world坐标变换和版本 |
| planner适配 | `scene_aware_planner.py:PersistentCuroboPlanner.__call__:110` | scene→request，model/tool/attachment/profile |
| worker | `production_scene_worker.py:main` | GPU缓存、求解、独立验证和报告 |
| 原生打包 | `scene_aware_execution.py:GenericNativePackager.__call__:64` | sourcepath→native、candidate binding |
| generic preflight | 同文件`preflight:166` | fresh左右状态、scene/start/tool/base/profile/trajectory gates |
| 执行 | `canonical_backend.py:motion_execute:66` | 资源/授权、线程、native sender、状态收尾 |
| 控制循环 | `scripts/jaka_right_demo.cpp:main/read/load` | 真正发ServoJ、读控制器状态、abort/disable/logout |

`scene_aware_execution.py`的SENDER路径是`...supervised_path_v5`；新pick参数是`...v6_pick`。**两文件名并不证明binary不同或相同**，应在返场采集SHA/SDK依赖；当前源码的pin hash也要与实际文件对应。

## 7 距离检查到底在检查什么

当前whole-arm采用大量collision spheres与world cuboids。worker会：

1. cuRobo GPU内部优化与碰撞判定。
2. `clearance_by_sample()`通过GPU FK取sphere中心后转CPU NumPy，逐cuboid计算signed distance。
3. start、goal、101点joint-linear baseline、planned dense path、trace等可能重复调用。
4. generic evaluate_hard_validity/level再判定。
5. contact bypass另用link OBB overlap和自碰撞，不与generic全路径完全同算法。

独立验证可发现模型/离散化/绑定问题，但**全量最小间隙数值报告不应与“有没有硬穿透”混成每阶段强制昂贵同步工作**。建议验收后分出：

- 执行前必需：同一geometry、同一scene、同一trajectory的hard collision/状态/动态验证。
- 异步诊断：所有障碍最近距离、全量trace、baseline比较、截图、pretty JSON。
- 失败归因：只对limiting links/objects加密计算和可视化。

先比较GPU/native距离实现与现独立validator，覆盖薄隔板、小物、工具、attachment；不能只说“cuRobo算过了所以所有验证都删”。

本次全局preferred已0mm；optimizer collision activation仍30mm；scene self-filter分别30/40mm；attachment inflation4mm；IK误差1.5mm；这些含义完全不同。当前代码仍计算min gap，**“以后不算”没有在此链路全局实现**。

## 8 动态时间参数 为什么小动作会变成一分钟

`package_native_preview()`取每关节site/native/tracking/stage最小速度和加速度；源path不改几何，`resample_for_native()`不断time-dilate，直到80ms离散速度/加速度满足sender。

contact源26点、dt按0.008传入；真实时长由重新打包决定，不是26×0.008。折线每个顶点速度方向改变，在几何误差≤1e−8要求下，不能随便拟合圆滑路径。相同0.20 cap可能得到10秒或70秒，要看关节弧长、曲率、离散加速度、边界静止和tracking模型。

### 仅作下界的量级计算

从对话读取的contact起终关节，最大单关节净变化约0.568rad。若v=.05、a=.10，单轴静止到静止梯形时间必要下界约`d/v + v/a = 11.9s`；实际文件115.04s。

100mm lift最大单关节净变化约0.984rad；v=.20、a=.20的同类必要下界约5.9s，实际native约72s。

这些下界**不是可执行轨迹或承诺时长**：不包含真实关节曲线路径、其它轴、奇异性、工具姿态或几何约束。但足以说明“速度上限已经0.2，所以只能这样慢”不成立。

改进优先：输出source/path/native各自时长、最大关节弧长、retiming stretch和限制关节；用受约束时间参数化代替粗粒度全路径拉伸。若要几何平滑，必须作为新路径重新碰撞验证并产生新hash，不能暗改已批准轨迹。

## 9 全部时间和资源预算

### 现状可确认值

| 项 | 已确认值 | 不能由此推断 |
|---|---:|---|
| FAST caller期限 | 4秒 | 后台4秒停止，或点击4秒首动 |
| QUALITY每请求等待上限 | site240秒 | 一轮全链≤240秒 |
| 首次FAST late worker | 80.25秒 | FAST具备几百毫秒部署性能 |
| 第二次QUALITY solve | 112.08秒 | 都是碰撞导致或都在GPU运算 |
| 第二次QUALITY整个worker | 159.53秒 | 与另一queued worker可无重叠相加 |
| 单次dense子项 | 约11秒 | 可与postprocess约35秒再次相加；它已包含其中 |
| 成功run PICK_PREPARE | 约238.81秒 | 每次均相同 |
| pregrasp文件/阶段 | 36.08/39.52秒 | contact/lift同速度就同耗时 |
| contact文件 | 115.04秒 | TCP路径长或物理障碍多的必然结果 |
| initial lift发送/恢复窗口 | 约72/75.69秒 | 230mm已完成 |
| base独立旧路线空载往返 | 100.856秒 | 新85cm路线持物往返已commission |
| 新GRASP左移命令观察器 | 9.079秒 | 实际精确位移已验证为100mm |
| GPU | RTX3060 Laptop，约11.66GiB | 8/8 planner可以无限缓存 |
| 其他pose进程 | 约680MiB | 可未经确认杀掉它 |

### 现场硬超时预算

- pick最多3次，FAST4秒、两次QUALITY各240秒，单看客户端solver等候上界即484秒；外层每次capture/prepare各300秒、build300秒另计。这个实现没有一个可信的任务总deadline。
- scene subprocess240秒；SDK audit30秒；backend client有300秒；Live.get20秒、Live.post默认150秒、planning240+120秒；各层超时不是同一deadline。
- generic执行监控300秒，native最大240秒；HTTP响应丢失后，执行是否仍在跑必须查询job，不得当“没执行”重发。
- 串口每exchange1秒，上层command10秒；Stop HTTP10秒，child wait10秒但没有总能强制回收的证明。
- `pool.shutdown(wait=True)`可能等待未结束的HTTP future；SIGTERM后没有完整join/kill状态机，不能仅凭Python异常保证整个后台已停止。

### 资源预算 ESTIMATE

| 资源 | 常驻/峰值预算建议 | 验证方法 |
|---|---|---|
| GPU | 单planner按受控profile预算；建议启动前保留20–30%余量作工程目标，不是当前commission阈值 | nvidia-smi与Torch allocated/reserved、runtime cache count、每请求前后记录 |
| GPU scene | cuboid bucket最小512、按256扩容；object数变化可能新建runtime | 记录actual primitive/sphere count与capacity，不固定历史障碍数量 |
| CPU RAM | scene处理暂预算2–6GiB，可能更高；当前实测RSS未知 | 每stage峰值RSS/USS、点数、voxel数、临时数组、并发进程 |
| CPU计算 | 大量NumPy距离/分解、SciPy IK、反复Python import；实际核数和CPU时间未知 | perf_counter+process_time、子进程CPU/RSS采样 |
| 点云 | 历史1920×1200约230.4万点；float32 XYZ原始约27.65MB/帧（26.37MiB），彩色PLY历史约33MB | 区分N×3 float32、float64复制、PNG、双份PLY；不能把原始数组大小当峰值RAM |
| 磁盘 | 5–10次fresh scan可轻易数百MB；大量JSONL/pretty轨迹另计 | 文件bytes/写盘耗时、实时日志延迟、磁盘可用空间 |
| 网络 | 23MB级EpicRaw历史样本，5700约2秒但现场负载变化 | capture设备耗时/传输/解码分别记；不把Wi-Fi路由问题一概归因规划 |
| native日志 | 12.5Hz；115秒约1440条sample，通常MB量级但需实测 | 不逐sample fsync；日志队列丢失策略不能影响控制保护 |

### 全链现状模型 不是实测完成周期

当前完整抓放没有成功跑完，不能给出可信全周期p50/p95。仅将已测物理段和未测后半段估算拼成工程范围，现状成功无重试一轮也可能约**8–18分钟**，规划重试/资源冲突可更久；精确数字必须用完整runner一次真实闭环验证。

不变已测动作就包括约36秒pregrasp+115秒contact+72秒initial lift；再加近100秒量级base往返，未算余130mm和preland，就已约323秒。**不能一边承诺所有现有运动时长不动，一边保证全周期两三分钟。**

返场目标应拆分：软件首动等待、单段规划、物理动作、完整周期；不要用“cuRobo低于2秒”替代交付速度。

## 10 未来日志最小合同

统一monotonic与wall时间，每个job/stage/attempt至少记录：

```text
task_id / job_id / attempt_id / stage / actor
requested_at / admitted_at / queue_exit / worker_start
capture_start/end / detection_start/end / robot_state_before/after
decode / CAMERA_to_BODY / self_filter / attached_filter / cleanup / decomposition
snapshot_id / scene_digest / calibration_revision / geometry_revision
active/inactive tool+joint revisions / payload revision
requested_solver_config / effective_solver_config / loaded_module_sha
world_update / initialization / one_time_warmup / each_solve / validation / package
deadline / cancellation_requested / cancellation_confirmed / late_result_discarded
native_source_dt / native_dt / source_duration / stretched_duration
limiting_velocity_joint / limiting_acceleration_joint / max_tracking / p95 / RMS
servo_enable / first_sample / last_sample / settling / target_reached / servo_disable
device_request / accepted / completion / stable
fault_type / actual_error / retryability / last_safe_checkpoint / suggested_action
```

原始readback每次独立采样时刻，不能事后重写。所有HTTPError保留response body；`SystemExit2`、`409 Conflict`、`Failed to fetch`不能作为最终用户可读原因。

## 11 如何复核和调用

### 安全离线调用 本轮已做

```sh
cd /path/to/ARES-R-offsets-20261016
python3 scripts/audit_roundtrip_offline_inventory.py --output worklog/audits/NEW_UNIQUE_AUDIT_DIRECTORY
```

只解析文件和调用Git只读命令，生成审计输出；不import ARES硬件服务、不访问网络、不运行Demo。目录必须新建，不能覆盖本审计证据。

`--prepare`/`--replay`是既有runner的非运动入口，但部分版本读取site资产并写runtime；应在隔离工作树使用，不在运行中的正式runtime跑全量测试。

### 现场入口说明 非本轮执行命令

完整Demo目前由WebUI专用start接口启动；CLI已有`--execute`要求review批准副本、授权、现场确认和TTY。**直接运行默认parameters会因review_approved=false拒绝，这不是故障修复方法。**

临时恢复脚本只有两份：`resume_confirmed_grasp_lift.py`与`finish_confirmed_lift_hold.py`。它们包含特定10月16日checkpoint、尝试次数和错误类型分支，不应给同事作为通用“继续”按钮。返场前统一成正式resume接口，保留原始历史，不reset/revert。

## 12 待补的原始数据与复现要求

必须获取每条trajectory的source points+native points+dt、每次state采样、source scene、原始相机manifest和body cloud、source/effective configs、加载模块/二进制/SDK hash。只有最终位置或一张截图不足以解释115秒contact。

本轮只保存静态源码和聊天已读数值；不声称已经抓到现场所有未提交日志。不能用旧9月scene来证明10月16日contact/attached collision正确。

## 13 参数有效来源和覆盖顺序

同一个参数名出现在多处不代表最后生效值相同。最低限度应打印：requested、site、profile、worker effective、native actual五层。

| 参数组 | 当前值或路径 | 实际消费者 / 注意 |
|---|---|---|
| Demo revision | RIGHT_GRASP_PLACE_ROUNDTRIP_2026_10_16_V2_NO_STOW_RETRY3 | launcher启动时冻结，不只看磁盘默认参数 |
| review_approved | 默认false，一次启动副本true | main检查；不是全局永久授权 |
| active/inactive | right / HOLD_CURRENT | recipe与执行；不允许由此省略left真实geometry |
| pick/place | `right_pick / right_place_rightmost` | Epic task_profiles；space2/object1或3/camera1的实际映射要保留raw/meta |
| slot | lower_middle | operations registry当前offset，启动快照绑定 |
| base route | config/grasp_place_base_route.json | 单独route snapshot；V2横向.85m，不用旧tray_to_groove base_contracts的.3/−.4 |
| base speed | .10m/s | 底盘preview/adapter也可能有site限制 |
| pregrasp | .055m | Demo与tray_to_groove_v2.contact.selected必须一致，否则准备FAIL |
| lift | .10+.13=.23m | source contact package只有前.10；余.13走fresh scene自由空间 |
| preland | .04m | Demo覆盖旧tray_to_groove_v2.place.preplace_height=.05、placement_offset=.005语义，不混成45/55mm |
| gripper | prepare400 / close0 / release400 | Demo使用raw，不沿用旧任务release_percent20 |
| open verify | tolerance20、delay.75秒 | Live.gripper使用；不是visual grasp判据 |
| grasp reads | .25/.75/1.5秒 | runner执行间隔；verifier又硬编码这些label，需统一 |
| scene delta | radius.15m、voxel.005m | verifier脚本硬编码；修改参数文件radius目前不保证生效 |
| motion profile | right_scene_aware_0_20 | generic packager按scope校验，site最低cap仍参与 |
| lift cap | velocity.20 / acceleration.20 | pick native打包；本地site max_velocity .10可能成为实际有效上限 |
| contact cap | velocity.05 / acceleration.10 | 实际contact115秒并非单纯1/v缩放 |
| tracking stop | 1.5° | native实时上一条target跟踪门，不是IK和到位门 |
| FAST | 4IK/2trajopt、graph=true、initial_iters50、候选1 | worker确实消费哪些必须实测；本地生产worker未消费solver_policy |
| QUALITY | site timeout240、8/8、graph=false、max_attempts5、graph_attempt1 | 每个“attempt”内部还可能多次solve；不是一次固定2秒 |
| interpolation | source .008s、buffer5000 | native .080s；buffer不足也可导致失败，需记录实际点数 |
| validation | subsamples4、batch128 | 不是4mm/128障碍，单位不可混用 |
| clearance | preferred0、hard0、activation.030m | 三类用途；min距离运算当前仍执行 |
| self-filter | robot.030 / gripper.040m | 仅机器人；当前不自动包含attached payload |
| world inflation | profile obstacle inflation0 | support/decomposition、geometry、attachment仍各可能有自己的余量 |
| tool envelope | .008m，opening40% union | 不等于独立component模型；已有component代码未在本Demo强制启用 |
| attached | .004m inflation，本次link6 AABB约.135×.220×.231m | coarse模型，抓取变换来自source package；当前需self-filter闭环 |
| center/exclusion | 中央禁区disabled，half-width.07m | 这个Demo没有center/stow步骤；不要被旧中心收臂Scheme重新带入 |
| horizontal | 最大3°，yaw目标0 | .6°是IK姿态残差，两个判据不同 |
| native start | .02° | 与Live .2°、site .03rad不同；优先统一合同 |
| native end | .05°、单次40ms读取 | 当前无正式settle阶段 |
| joint boundaries | 本地site J1/J4/J6±360°，J2±125°，J3±130°，J5±120° | 这是本地配置值，非本轮核实过的实物型号或controller限位读取 |
| software margin | site5°；IK另内缩约1.146° | 可能晚期打包才冲突，必须统一 |
| sender/pin | pick v6_pick，generic v5，source SHA pin | 返场核实实际binary hash、SDK依赖和loaded module hash |
| capture Python | vendor3.11，BODY scene配置为calib3.9，SDK audit为system python3 | 不同venv的import/ABI/NumPy/Open3D可形成冷启动和库冲突 |

native最终上限公式：

```text
v_i = min(site_v_i, supervised_native_v, tracking_speed_cap, stage_v)
a_i = min(site_a_i, native_a, stage_a)
```

本地site每轴v=.10，profile写.20时仍可能有效.10；generic packager只对RIGHT_ARM_AB_DEMO_ONLY抬site副本，不对RIGHT_ARM_SCENE_AWARE_FREE_SPACE同样处理。这里**只能确认本地代码潜在覆盖关系**，不能在没有现场native audit的情况下声称10月16日所有轨迹有效速度恰好.10。

## 14 HTTP接口清单与调用语义

| 接口 | 请求和返回要点 | 会不会运动 |
|---|---|---|
| GET `/api/demo/roundtrip/status` | state/running/current_event/blockers/can_start/contract SHA | 否；旧恢复任务可能不在此状态源 |
| POST `/api/demo/roundtrip/start` | authorization、onsite_observer_confirmed、contract SHA；返回run/log | **是，后台完整流程**；不得为测试随意调用 |
| POST `/api/demo/roundtrip/stop` | 复用operations_stop | **会请求停止运动**；不是仅清网页 |
| GET `/api/operations` | dryer slots、offset、policy、software limits、revision | 否 |
| POST `/api/operations/update` | action/body/expected_revision；当前Demo用keypoint | 一般配置/显示；具体action必须审计，不当运动接口 |
| POST `/api/operations/telemetry` | body可为空；返回arms/base/errors | 只读设备，但SDK/网络负载可影响实时通信 |
| GET `/api/scene/status` | state/epoch/base revision/age | 否 |
| POST `/api/scene/scan` | arm，强制fresh scan | 相机采集，不发机械运动 |
| POST `/api/scene/invalidate` | reason | 不发运动；使后续旧scene不可用 |
| POST `/api/motion/plan` | arm、position_m、orientation、yaw_target、planning_mode、scene_policy、speed_profile、attachment等 | planning-only；会扫描和占GPU |
| GET `/api/motion/<plan_id>` | plan handle/preview | 不运动；不能以marker显示代替验收 |
| GET `/api/motion/status` | scene-aware planning state | 不运动 |
| POST `/api/operations/execute` | plan_id、trajectory hash、授权、onsite、cycle token | **执行已绑定轨迹** |
| GET `/api/operations/run-status` | canonical physical运行结果和target_reached | 不运动 |
| POST `/api/operations/base-preview` | x_m/y_m/yaw_deg/linear_mps | 预览，不运动 |
| POST `/api/operations/base-move` | 同上+MOVE BASE授权和owner token | **运动且等待真实observer** |
| POST `/api/operations/stop` | 当前job停止 | **abort/servo disable/base stop等实际效果** |
| POST `/api/operations/jog` | BODY或joint离散目标 | 当前dispatcher生成plan；需与execute按钮区分，不能把“点JOG没动”当硬件失效 |
| POST `/api/operations/record` | plan/关键点保存 | 非运动，仍需绑定geometry/revision |

示意plan payload，仅说明字段，**不是可复用现场目标或执行授权**：

```json
{
  "arm": "right",
  "position_m": [0.8, -0.2, 1.2],
  "orientation": "LEVEL_YAW_TARGET",
  "yaw_target_rad": 0,
  "scene_policy": "FORCE_RESCAN",
  "planning_mode": "FAST",
  "environment_avoidance": "ON",
  "speed_profile": "right_scene_aware_0_20",
  "request_label": "AUDITED_TASK_STAGE",
  "source": "reviewed_task_runtime"
}
```

持物时还必须传当前`attached_object_geometry`及其revision；**目前传了它不等于scene self-filter会消费**。不可从旧日志复制attachment给一个没有物体的新场景。

## 15 失败文件与正式交付状态

正常一次运行应至少有：

```text
launches/<id>/parameters.json + route.json + authorization.json
web_<id>/events.json
pick_attempt_<n>_<mode>/epoch/manipulation_observation.json
pick_attempt_<n>_<mode>/pregrasp_plan/{planner_request,planning,preparation}.json
pick_attempt_<n>_<mode>/package/first_pick_execution_package.json
pick_attempt_<n>_<mode>/native/{segment}.audit.json
pick_attempt_<n>_<mode>/native/{segment}.execute.txt + .jsonl
verification.json + raw readback files + post scene
HOLD230/PRELAND40 plan handles + level result
scene-aware-motion/PLAN_*/native_package/candidate_manifest.json
operations-execution/* actual native logs and result
base completion samples / before-after poses / revisions
result.json（只有真实19阶段完成才是RETURNED_GRASP）
```

缺文件、迟到文件、旧版本SUCCESS、只有Mock result，都不能补写成完整成功。用户人工认可抓稳与轨迹视觉效果应保存为独立operator event，不改写之前FAIL原记录。
