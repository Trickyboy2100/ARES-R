# 2026-09-17 cuRobo 官方风格 A↔B 点云避障 Demo 工作单

## 0. 为什么做这个 Demo

这个 Demo 不是一次性展示代码，而是当前 ARES-R 最值得做的 commissioning 子链：

```text
固定起点 A
→ 扫描真实点云
→ 构建 collision world
→ cuRobo 规划到 B
→ 无障碍时近似直达

固定起点 A / B
→ 再扫描真实点云
→ 场景中有障碍
→ cuRobo 规划绕障
```

它直接验证：

```text
Pixel Pro → 坐标变换 → 场景构建 → cuRobo → trajectory preview
```

后续真实 Pick / Place 复用同一条生产数据链，禁止另造 demo-only 假场景实现。

本轮默认 planning-only。只有 `T_body_camera`、collision world、SafetyKernel、速度和执行链完成现场 commissioning 后，才允许升级为 supervised real motion。

---

# 1. 先把 `T_body_camera` 问题彻底说清

ARES-R BODY 定义：

```text
+X = robot / vehicle forward
+Y = robot left
+Z = up
```

Pixel Pro 原始点云在 CAMERA frame。

`T_body_camera` 是固定 4×4 刚体变换：

```text
p_body = T_body_camera · p_camera
```

它只描述“相机在整台机器人 BODY 上安装在哪里、朝哪个方向”。

因为相机固定在机器人头部并随底盘一起移动，所以这个矩阵只需 commission 一次；底盘在场地中移动并不会改变 `T_body_camera`，除非相机机械安装发生变化。

### 1.1 当前桌面平面解决了什么

当前四帧 RANSAC 已稳定找到 support plane，并给出相机约 49.55° 的俯视角。

桌面法向能确定：

- 相机相对“竖直方向”的 roll / pitch；
- 若 BODY 中桌面高度已知，可约束沿桌面法向的平移。

但单个水平面无法唯一确定：

- 绕竖直轴 yaw；
- 桌面内 X 平移；
- 桌面内 Y 平移。

所以 `LEVEL_FRAME` 不是 BODY。

### 1.2 推荐最快的完整标定办法

不要继续只靠一帧右臂几何做自由 ICP，因为当前已经证明存在多解。

优先级：

#### 方法 A：恢复 vendor / Epic Pro 已有外参

继续搜索项目导出、runSpace、cam2Base、space calibration。若能找到有 provenance 的矩阵，直接验证。

#### 方法 B：3D 对应点一次性求解（推荐）

建立至少 6 个、推荐 9 个非共线 calibration landmarks。

每个 landmark 同时有：

```text
p_camera_i
    Pixel Pro 深度/点云中的 3D 点

p_body_i
    同一物理点在 ARES-R BODY 中的已知坐标
```

用 Kabsch / Umeyama rigid registration 求：

```text
R_body_camera, t_body_camera
```

然后做 hold-out 验证。

landmark 来源优先：

1. 安装在机器人本体/刚性 calibration fixture 上、BODY 坐标可测的标记；
2. 明天现场允许安全运动时，用右臂 TCP / calibration pointer 到 6–9 个分散位置，由 JAKA FK 提供 BODY 坐标，相机提供对应 3D 点；
3. 不建议仅用桌面上未经精确 BODY 测量的位置充当一劳永逸外参。

桌面平面作为额外约束与 sanity check，而不是唯一标定来源。

### 1.3 commissioning 后验证

至少报告：

- calibration points RMS / max；
- hold-out points RMS / max；
- support-plane level residual；
- 机器人模型与点云 overlay；
- 4 帧重复性；
- calibration revision/hash。

production 配置只有通过验收才允许：

```text
state = COMMISSIONED
planning_allowed = true
```

否则只允许：

```text
state = DEMO_ONLY_UNCOMMISSIONED
planning_allowed_for_real_execution = false
```

---

# 2. A↔B Demo 几何设计

第一版使用右臂，因为当前右臂已有真实 cuRobo→ServoJ 证据；整机仍必须包含左臂作为 inactive collision geometry。

定义两个可重复 TCP 目标：

```text
A
B
```

要求：

- A/B 在右臂私有或已授权 workspace；
- 相同 TCP orientation；
- 主要沿 BODY 水平面方向平移；
- 目标距离建议先取 0.15–0.30 m 的明显但安全距离；
- 不进入 BODY 中央 14 cm exclusion；
- 不贴近奇异点、关节软限位、桌边或未知设备；
- 所有数值必须由真实 cuRobo/robot model preview 选择，禁止仅凭目测写死。

保存为 versioned demo profile，而不是临时脚本常量：

```text
config/demo_pointcloud_ab.site.json
```

包含 A/B pose、arm、tool revision、speed profile、ROI、minimum clearance、scene mode、calibration revision。

---

# 3. 三个 Planning-only Demo

所有 Demo 都必须从当前端点重新扫描并重新建 scene。

## D-A：CLEAR

```text
robot at A
→ capture pointcloud
→ build BODY collision world
→ plan A→B
```

期望：

- planning PASS；
- TCP path 接近直接路线；
- 保存 scene + trajectory + preview + timing。

## D-B：AVOID

在 A/B 之间放置一个 Pixel Pro 可见、尺寸稳定、不会误认为机器人/桌面的障碍物。

```text
robot at A or B
→ capture fresh pointcloud
→ obstacle appears in residual scene
→ plan to opposite endpoint
```

期望：

- obstacle 来自真实扫描；
- planner 不能穿过 obstacle AABB / known model；
- trajectory 相比 CLEAR 有明显空间偏移；
- minimum clearance 可计算并展示。

如果当前 real residual scene 没有合适障碍，可增加明确标识 `DEMO_OBSTACLE_AUGMENTATION` 的人工 cuboid 做规划对照，但最终展示优先使用真实扫描障碍。

## D-C：BLOCK（planning-only）

使用明确标识的测试障碍完全封住通路或目标邻域。

期望：

```text
NO_PLAN / planning failed
```

禁止通过降低碰撞 margin 或关闭障碍来“通过”。

---

# 4. 点云 collision world 必须这样生成

```text
EpicRaw / in-memory depth/pointcloud
→ invalid/zero removal
→ mm→m exactly once
→ camera→BODY
→ BODY manipulation ROI
→ self-filter whole robot:
   chassis / left arm / right arm / grippers / tool / attached object
→ support table recognized as known geometry
→ target/allowed-contact object separated
→ 5–10 mm voxel
→ unknown residual clustering
→ conservative AABB + explicit inflation
→ known geometry merge
→ ObservationEpoch
→ WorldModel.freeze()
→ SceneSnapshot
→ SceneCompiler
→ cuRobo world
```

不得把 CAMERA-frame AABB 直接交给 cuRobo。

不得把桌面切成大量 residual boxes；桌面应作为一个 support surface / conservative cuboid。

inactive left arm 必须保留在 world 中。

---

# 5. 实时性 / latency benchmark

当前工程有实时性要求，所以 Demo 必须记录全链耗时。

区分两种模式：

### Evidence/debug path

允许保存 EpicRaw、PLY、PNG、JSON。

### Fast online path

禁止为了处理而落地 PLY/PNG：

```text
camera SDK memory
→ numpy/depth/points
→ scene processing
→ cuRobo
```

仅关键帧/异常帧异步留证。

至少分别计时：

```text
camera_trigger
frame_fetch
EpicRaw/depth decode
pointcloud generation
camera_to_body
ROI crop
self_filter
support/table handling
voxel
cluster + AABB
WorldModel/ObservationEpoch
SceneSnapshot freeze
SceneCompiler
cuRobo world update
collision query
full planning
TOTAL sense_to_plan
```

Benchmark：

- camera/scene pipeline warm-up >= 3；
- scene update >= 20 iterations；
- cuRobo planning >= 10 iterations per CLEAR/AVOID case；
- 报告 mean / p50 / p90 / p95 / max；
- 报告等效 scene Hz。

根据测量值再决定未来：

```text
V0 static scan-at-stage
V1 checkpoint rescan
V1.5 continuous scene watchdog + stop/replan
V2 nvblox / MPC reactive avoidance
```

不要本轮直接上 nvblox 或实时 GUI。

---

# 6. Demo 可视化产物

每次 run 生成同一个 run directory：

```text
logs/demo_runs/<run_id>/
```

至少包含：

```text
manifest.json
00_camera_rgb.png
01_camera_cloud.png
02_level_support.png
03_body_world.png
04_body_roi.png
05_self_filter_before_after.png
06_collision_world.png
07_curobo_trajectory.png
trajectory.preview.html
timing.json
terminal.log
```

`06_collision_world` 与 cuRobo 真正使用的 SceneCompiler output 必须同源。

`07_curobo_trajectory` 同时显示：

- A/B；
- right arm；
- inactive left arm；
- table；
- obstacle；
- TCP path；
- BODY axes；
- center exclusion。

CLEAR 与 AVOID 尽量保持相同相机视角与坐标范围，便于并排比较录像。

---

# 7. 进入真实运动的单独门槛

planning-only Demo 完成不等于可执行。

真实运动前至少要求：

```text
T_body_camera = COMMISSIONED
A/B = commissioned
speed profile = commissioned
whole-robot collision model accepted
inactive arm geometry live and fresh
SceneSnapshot valid
trajectory collision_checked=true
start joints match
Tool/TCP revision match
SafetyKernel permit issued
operator present + physical E-stop available
```

首次执行：

```text
CLEAR only
precision/slow
confirm_each_stage=true
```

CLEAR 成功后才做真实 AVOID。

每次到 A 或 B：

```text
stop
settle
fresh scan
fresh scene
fresh plan
```

不复用上一次 trajectory。

---

# 8. 本轮 Exit Criteria

完成并 STOP：

1. `T_body_camera` 问题被实现为可执行的 commissioning 工具/流程，而不是继续自由 ICP 猜测；
2. A/B demo profile 完成；
3. CLEAR / AVOID / BLOCK 三个 planning-only Demo 能从同一生产 scene pipeline运行；
4. obstacle 真正改变 cuRobo result；
5. latency benchmark 给出 scene update 与 planning p50/p95；
6. 输出适合录屏的统一可视化；
7. 列出明天 real-motion 的最小 blockers；
8. 不执行机械臂、夹爪或 AMR。

不要开始实时 GUI、Isaac UI、LLM、Skill Library 或动态 MPC。