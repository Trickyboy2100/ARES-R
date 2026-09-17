# 2026-09-17 展示包与“双臂整机化”工作单

## 0. 目的

本工作单服务两个目标：

1. 把 ARES-R 当前已经具备或即将具备的能力，整理成一组**可以录像、录屏、复现、对外展示**的 demo；
2. 从软件架构上明确：JAKA 左右臂虽然是两个独立控制器，但 ARES-R 在机器人系统层必须把它们视为**一台完整的双臂移动机器人**，而不是两个互不相关的单臂机器人。

本工作单不是要求立刻实现 12-DoF 同步双臂规划。当前优先级仍然是：真实世界坐标、碰撞场景、规划、受监督执行、E2E 串联。

在 `2026-09-17_BODY_REGISTRATION_COLLISION_WORLD_ORDER.md` 完成前，不要为了录视频提前绕过 BODY registration / collision / SafetyKernel 门。

---

# 1. 双臂整机化的正式系统身份

ARES-R 顶层只应暴露一台机器人：

```text
ARESRobot / DualArmMobileRobot
├── body_frame
├── mobile_base
├── head_camera / Epic
├── left_manipulator
│   ├── arm
│   ├── gripper
│   └── tool / attachment
├── right_manipulator
│   ├── arm
│   ├── gripper
│   └── tool / attachment
├── whole_robot_state
├── whole_robot_collision_model
├── world_model
├── scene_compiler
├── dual_arm_coordinator
└── safety_kernel
```

不要在任务层继续形成两套：

```text
left_robot
right_robot
```

正确关系是：

```text
one robot
  ├─ two manipulators
  └─ one shared world and one motion authority
```

## 1.1 设备层可以独立，系统层必须统一

允许保留：

```text
JakaLeftAdapter
JakaRightAdapter
LeftGripperAdapter
RightGripperAdapter
```

因为底层真实设备、IP、SDK 会话、故障状态本来就是分开的。

但从以下层开始必须统一：

```text
RobotState
WorldModel
SceneSnapshot
CollisionWorld
MotionAuthorization
SharedZone ownership
AMR-arm interlock
Task state
EventLog / run_id
```

任务层不应该出现：

```text
left_pick_task.py
right_pick_task.py
```

而应该是：

```text
Pick(object, arm_policy=AUTO|LEFT|RIGHT)
```

`LEFT/RIGHT` 只作为 commissioning/debug override 或任务确有约束时的 policy；默认应允许 coordinator 决定。

---

# 2. 双臂规划成熟度分级

不要把“一台双臂机器人”等同于“必须立刻做 12-DoF 联合轨迹优化”。

## V0 — SINGLE_ARM_AWARE（当前必须先完成）

```text
一次只授权一条臂运动
另一条臂固定在实时/已知姿态
另一条臂完整 collision geometry 进入 scene
中央/共享区受统一 ownership 控制
底盘运动时双臂必须 transport-safe
```

这已经是一台完整双臂机器人，而不是两个单臂系统。

## V1 — SEQUENTIAL_DUAL（E2E 稳定后）

```text
coordinator 自动选择 arm
left plan / right plan 共用一个 SceneSnapshot
一臂完成后重新 freeze state
必要时另一臂继续
支持 handover / fixture-assisted regrasp 的顺序协同
```

## V2 — SYNCHRONIZED / WHOLE-BODY（有真实任务需求时）

只有以下任务真正需要时再做：

```text
双臂共同托举
同步插装
大物体协同搬运
需要两臂时序耦合的操作
```

届时再评估：

```text
12-DoF joint planning
spatiotemporal coordination
mobile-base + dual-arm whole-body planning
```

不要为了“看起来更双臂”过早引入高风险复杂度。

---

# 3. WholeRobotState / WholeRobotPose 应成为共同合同

后续逐步收敛到：

```text
WholeRobotState
  timestamp
  base_state
  left_joints
  right_joints
  left_tool_revision
  right_tool_revision
  left_gripper_state
  right_gripper_state
  left_attachment
  right_attachment
  scene_snapshot_id
  active_motion_owner
  shared_zone_owner
```

命名姿态也不要只理解为“左关节组 + 右关节组两个孤立目标”。

应升级为 `WholeRobotPose` / `RobotPosture` 概念，例如：

```text
transport_safe
observe_front
ready
up
forward
side
```

其定义可包含：

```text
left target
right target
base precondition
allowed tools
payload restrictions
shared-zone condition
verified execution route
speed profile
```

V0 执行“both up”仍然可以：

```text
plan left → execute left → verify
re-freeze whole robot state
plan right with new left geometry → execute right → verify
```

而不是同时发两个独立命令。

---

# 4. Demo 套件总览

目标不是造一个华丽 GUI，而是复用真实数据和现有模块，形成 6 个层层递进、可以录屏/录像的 demo。

建议统一命名：

```text
D0 Whole Robot World View
D1 Perception / Pointcloud Pipeline
D2 Collision World
D3 cuRobo Plan Comparison
D4 Supervised Real Motion
D5 Dual-Arm Coordination
D6 E2E Pick-Transport-Place
```

每个 demo 都必须：

- 有 `run_id`；
- 记录 git commit；
- 记录 config/tool/calibration/scene revision；
- 能离线回放；
- 明确是 `OFFLINE / CAMERA_ONLY / PLANNING_ONLY / REAL_MOTION` 哪一种；
- 不允许把未 commission 的内容包装成 production-ready。

---

# 5. D0 — Whole Robot World View

## 目的

让任何人一眼看到：ARES-R 控制的是**一台双臂移动机器人**。

## 画面必须有

```text
ARES-R BODY axes
mobile base / chassis envelope
left arm
right arm
left/right TCP
tool revision
central 14 cm exclusion slab
shared/center zone
camera pose/frustum（T_body_camera 可用后）
transport-safe posture indicator
active motion owner
```

同时显示：

```text
LEFT  READY/BLOCKED
RIGHT READY/BLOCKED
BASE  STOPPED/MOVING
SCENE ACTIVE/STALE
```

## 实现方式

优先扩展现有 `world view` 数据层，不强制引入新 GUI framework。

可提供两个输出：

1. Terminal `world view --detailed`；
2. offline HTML `world_view_<run_id>.html`，可旋转/切换 TOP/REAR/RIGHT 或至少播放当前姿态快照。

如果实现交互 3D 代价过高，V0 用 3 个正交投影 + 一个伪 3D view 即可。

## 录像方式

- **录屏即可**；
- 若同时读取真实 JAKA 状态，手机无需架设；
- 最后 5 秒切到 terminal，显示左右 tool revision 与 central clearance。

---

# 6. D1 — Perception / Pointcloud Pipeline

## 目的

展示“机器人如何把相机看到的环境变成可用于规划的世界”。

## 推荐六阶段可视化

```text
1 CAMERA RAW
2 SUPPORT PLANES
3 LEVEL FRAME
4 BODY OVERLAY
5 BODY ROI + SELF FILTER
6 FINAL RESIDUAL + AABB
```

每张图/GUI 标题必须写清 frame：

```text
CAMERA
LEVEL_CANDIDATE
BODY
```

禁止把 CAMERA-frame 红框称为真实机器人避障世界。

## D1A CAMERA RAW

显示：

- 原始点云；
- camera origin；
- optical axis；
- 点数 / frameID / SHA；
- 有效点比例。

## D1B SUPPORT PLANES

显示 multi-plane RANSAC：

- 每个候选 plane 不同颜色；
- normal；
- area；
- inlier count；
- residual RMS；
- 自动选中的 table/support plane。

## D1C LEVEL FRAME

将 support plane 法向旋到 +Z。

显式标：

```text
LEVEL FRAME ONLY
YAW / XY ORIGIN NOT YET BODY UNLESS BODY REGISTRATION PASSED
```

## D1D BODY OVERLAY

T_body_camera 有候选或已 commission 后显示：

- BODY axes；
- raw/voxel cloud；
- current right/left robot geometry；
- TCP/tool；
- table/support plane；
- central exclusion slab。

必须输出 registration residual / qualitative overlay status。

## D1E SELF FILTER

最好支持 before/after toggle：

```text
BEFORE: cloud contains robot
AFTER: robot points removed, table/object remain
```

## D1F FINAL WORLD

显示：

- table known geometry；
- known station/device geometry；
- target object 单独标识；
- unknown residual AABB；
- inactive arm；
- active tool / payload；
- BODY ROI boundary。

## 录像方式

这个 demo **最适合录屏 GUI**。

如果页面支持 step selector：

```text
RAW → PLANE → LEVEL → BODY → SELF FILTER → COLLISION WORLD
```

录屏 30–45 s 即可。

同时可以架手机拍一张机器人/桌面实景，最后做画面对照，但不是必须。

---

# 7. D2 — Collision World “机器人真正认为哪里不能去”

## 目的

D1 强调感知处理；D2 只强调最终 planner world。

## 画面

只保留：

```text
whole robot collision model
inactive arm
active arm start state
tool / payload
table/device known geometry
unknown AABB
central exclusion
planned target
```

不显示大片 raw pointcloud，避免画面太杂。

需要一个图层图例：

```text
ROBOT
KNOWN WORLD
UNKNOWN OBSTACLE
TARGET
NO-GO / SHARED ZONE
```

## 关键输出

`collision_world.json` 或 SceneCompiler 产物和可视化必须同源。

不能为了展示单独画一份与 planner 不同的数据。

---

# 8. D3 — cuRobo Planning Comparison

## 目的

用最直观的方式证明“避障不是 PPT，而是真的影响规划”。

同一个：

```text
start
+
goal
```

生成三个场景：

### FREE

```text
无阻挡
→ 最直接的轨迹
```

### REAL / OBSTACLE

```text
插入真实 collision world 障碍
→ 绕行轨迹，或显著不同的 joint/TCP path
```

### BLOCKED

```text
故意构造完全阻断
→ planner 必须失败
```

## GUI/HTML 扩展现有 preview

当前 `src/ares_r/motion/preview.py` 已有：

- 关节轨迹播放；
- TCP/link geometry；
- obstacle；
- TOP / REAR / RIGHT / pseudo-3D views；
- q/velocity/acceleration curves。

不要重写。扩展它使其支持：

```text
scene_snapshot_id
whole-robot left+right geometry
active arm highlight
inactive arm geometry
central slab
known vs residual obstacles
TCP planned path
min clearance
planning result / failure reason
scene digest / tool revision
```

最好新增 comparison mode：

```text
FREE | REAL | BLOCKED
```

三页或 tab 均可。

## 录像方式

**只录屏 GUI**，不需要架手机。

推荐 30 s：

1. FREE 播放；
2. REAL 播放；
3. BLOCKED 显示 planning rejected；
4. terminal 显示 planner result + scene ID。

---

# 9. D4 — Supervised Real Motion

## 目的

展示真实机器人确实执行 cuRobo 轨迹。

前提：只能使用已经通过该次 commissioning gate 的 arm / route / speed / scene。

不要为了 demo 临时关闭 SafetyKernel。

## 最佳录像配置

### 手机

架在机器人前侧约 45°，同时看见：

- 两条机械臂；
- 桌面/障碍；
- TCP 行程；
- 人的手不要进入工作区。

### 屏幕录制

同时录：

- Terminal；
- cuRobo preview / dashboard；
- SafetyPermit / scene ID；
- start / target / target_reached；
- tracking error summary。

最终后期可以左右分屏。

## V0 录什么

不要追求复杂抓取。

优先录：

```text
current → commissioned safe pose
```

或一条已有真实证据的右臂 cuRobo supervised motion。

标题明确：

```text
Real cuRobo trajectory execution
```

不要称为完整 E2E。

---

# 10. D5 — Dual-Arm Whole-Robot Coordination

## 目的

这是最能回答“这是不是一台双臂机器人”的 demo。

第一版无需同时运动。

## D5 V0：顺序双臂

例如 WholeRobotPose `up`：

```text
whole-robot target = UP

coordinator:
1. freeze whole state
2. choose left first / right first
3. plan arm A while arm B is collision geometry
4. execute arm A
5. verify
6. re-freeze whole state
7. plan arm B against new arm A geometry
8. execute arm B
9. verify whole posture
```

GUI 必须始终同时画两条臂。

Terminal 不应该显示成两个孤立任务；推荐：

```text
ROBOT POSTURE: UP
phase 1/2 LEFT  planning/executing
phase 2/2 RIGHT planning/executing
WHOLE ROBOT UP = VERIFIED
```

## D5 V0 的重点不是速度

重点是：

- 一条臂的规划知道另一条臂存在；
- 两条臂共享 SafetyKernel；
- 最终是一个 whole-robot state transition。

## 录像方式

这次最好：

- 手机架好，拍完整双臂；
- 屏幕录 GUI / terminal；
- 如果能分屏，效果最好。

这会是非常适合给甲方/老师看的一个“整机能力”视频。

---

# 11. D6 — E2E Pick → Transport → Place

这是最终对朱工最有说服力的 demo。

完整阶段：

```text
PRECHECK
STOW_BOTH
NAV_PICK
WAIT_ARRIVAL
ACQUIRE_SCENE
DETECT_PICK
COMPILE_WORLD
PLAN_PICK
EXECUTE_PICK
VERIFY_GRASP
ATTACH
TRANSPORT_STOW
NAV_PLACE
WAIT_ARRIVAL
ACQUIRE_SCENE
DETECT_PLACE
COMPILE_WORLD_WITH_PAYLOAD
PLAN_PLACE
EXECUTE_PLACE
VERIFY_RELEASE
DETACH
RETREAT
STOW_BOTH
COMPLETE
```

## 手机必须拍

需要从底盘开始移动一直拍到放置结束。

## 屏幕同时录

建议有一个简单 stage dashboard：

```text
[✓] NAV_PICK
[✓] ACQUIRE_SCENE
[✓] DETECT_PICK
[▶] PLAN_PICK
[ ] EXECUTE_PICK
...
```

右侧显示当前：

```text
scene_id
target_id
active_arm
tool_revision
collision_checked
speed_profile
```

不要在第一版增加复杂动画；状态清楚最重要。

---

# 12. Demo artifact 统一目录和 Manifest

建议生成：

```text
logs/demo_runs/<run_id>/
├── manifest.json
├── terminal.log
├── world_state.json
├── scene_snapshot.json
├── collision_world.json
├── trajectory.json
├── trajectory.preview.html
├── pointcloud/
├── screenshots/
└── operator_notes.md
```

`manifest.json` 至少：

```text
run_id
created_at
git_commit
demo_id
mode
robot/tool revisions
calibration revision
scene_snapshot_id
planner result
motion executed: true/false
operator
video filename/reference（只记录，不提交大视频）
```

视频文件默认不进 Git；Git 只保留 run manifest、关键截图和小型证据。

---

# 13. 手机什么时候架起来

不要每次试验都架手机浪费时间。

定义 `RECORD_READY` 条件。

## D0/D1/D2/D3

不需要手机，主要录屏。

## D4

只有满足：

```text
planner PASS
scene valid
SafetyPermit issued
speed commissioned for this route
physical E-stop available
operator supervising
```

才提示：

```text
RECORD_READY: PHONE + SCREEN
```

然后再架手机。

## D5

两条臂的顺序计划都已 dry-run 可行后，再架手机。

## D6

E2E dry-run 从 PRECHECK 到 COMPLETE 全部通过，且每个真实阶段单独验收后，再安排正式完整录像。

---

# 14. 今天建议先实现哪些 demo

按优先级：

```text
P0 D1 Pointcloud Pipeline
P0 D3 cuRobo Planning Comparison
P1 D0 Whole Robot World View
P1 D2 Collision World
P2 D4 Supervised Real Motion
P2 D5 Dual-Arm Coordination
P3 D6 Full E2E
```

如果 BODY registration 当前尚未完成：

- 先把 D1 的 CAMERA / PLANE / LEVEL 做好；
- D3 可以先用人工/已知 cuboid 验证 preview/compare UI；
- BODY collision world 一旦可靠，立即切换 D3 到真实 scene。

不要为了录 D4/D5 提前执行未验收运动。

---

# 15. 实施要求

本轮 Codex 在实现 demo 时必须遵守：

1. 优先复用现有 `world view`、`process_static_pointcloud.py`、`motion/preview.py`、SceneSnapshot artifacts；
2. 可视化必须从真实 planner/world artifacts 读取，禁止维护一份仅用于展示的“假 scene”；
3. 所有 HTML/PNG 生成工具默认 offline；
4. GUI 不允许直接包含“绕过 SafetyKernel 执行”按钮；
5. REAL_MOTION demo 的 execution 必须继续走正式 gateway；
6. 左右臂始终在同一 whole-robot visual scene 中；
7. 不要为左右臂复制两套 viewer；
8. 每个 demo 生成 `manifest.json`；
9. 不要提交大型 PLY/EpicRaw/video 到 Git；只记录 SHA/path/provenance；
10. 运行全部 tests，保持 Python 3.8 兼容。

---

# 16. 本轮建议的代码产出

优先评估/实现：

```text
src/ares_r/visualization/
├── whole_robot.py
├── pointcloud_stages.py
├── collision_world.py
├── demo_manifest.py
└── html.py

scripts/
├── render_whole_robot_demo.py
├── render_pointcloud_demo.py
├── render_collision_world_demo.py
└── render_curobo_compare_demo.py
```

但不要机械地照此建空文件；先复用现有实现，如果 `motion/preview.py` 中直接扩展更合理，就保持代码集中。

测试至少覆盖：

```text
same SceneSnapshot → same rendered scene digest
left/right both present in whole-robot viewer
inactive arm cannot disappear from planner visualization
CAMERA vs BODY frame labels cannot be混淆
planning failure still renders a comparison artifact
manifest records git/scene/tool/calibration revisions
no visualization code imports hardware control callbacks
```

---

# 17. Exit criteria

本工作单完成时，至少能够生成以下四个无需实机运动的展示资产：

```text
D0 whole_robot_view.html/png
D1 pointcloud_pipeline.html/png set
D2 collision_world.html/png
D3 curobo_compare.html
```

并且：

- D0 始终画完整双臂机器人；
- D1 清楚显示 CAMERA → LEVEL → BODY/blocked 状态；
- D2 与真实 SceneCompiler/collision world 同源；
- D3 能明确展示 FREE / REAL / BLOCKED 对规划的影响；
- 所有资产有 run manifest；
- 没有因展示功能引入新的硬件运动入口。

随后 STOP，让用户决定何时进入 D4 真实运动录像。
