# 2026-09-17 队列收敛：桌边对齐 → BODY↔Camera 外参 → Production A↔B 避障 Demo

## 0. 为什么重排队列

上一轮已经完成 `DEMO_OFFLINE_ONLY` 的真实 Pixel Pro 点云 → `ObservationEpoch → WorldModel → SceneSnapshot → SceneCompiler → cuRobo` 链，并得到 FREE / AVOID / BLOCK planning-only 结果；同时已有 latency benchmark。

因此不再重复“证明人工/DEMO_ONLY collision world 会影响 cuRobo”。下一阶段唯一主线是：

```text
把 T_body_camera 做到可验收
→ 用 production BODY scene 重跑 pointcloud collision world
→ 定义真实 A/B
→ 每次从 A/B 出发 fresh scan + fresh plan
→ 再决定是否进入 supervised real motion
```

本轮新现场事实：操作员已经手动调整底盘，使机器人 BODY 左右方向轴基本与桌面前缘平行、BODY 正前方向基本与桌边法向垂直。这个信息作为 `OPERATOR_ALIGNMENT_PRIOR`，只能用于初始化和交叉验证，不能直接标记为标定真值。

当前 production `T_body_camera` 仍保持 `null/UNCOMMISSIONED`；在通过本文 commissioning gate 前，不得用于实机碰撞安全。

所有新代码、日志、图片、manifest、配置都必须位于 `/home/yikun/ARES-R` 内。不要新建新的 `ARES-R_AUDIT_*` 工作目录；旧审计目录仅允许读取历史证据。

---

# 1. 当前已知事实

当前桌面主平面跨 4 帧稳定：

```text
mean normal_camera ≈ [0.046354, 0.647166, 0.760939]
mean plane d       ≈ -0.820625 m
normal max drift   ≈ 0.0862°
offset std         ≈ 0.425 mm
```

人工确认桌面高度：

```text
z_table_body = 0.750 m
```

因此 camera optical center 的 BODY z 初始估计约：

```text
z_camera_body ≈ 0.750 + 0.820625 = 1.570625 m
```

此值只用于初值/校验，不直接写死。

上一轮自由 6DoF auto-registration 仍为多解；DEMO candidate 仅可用于离线展示，不能升级为 production 外参。

上一轮 planning-only Demo 已经完成：FREE success；AVOID success 且相对 FREE 最大 TCP 偏移约 58.49 mm；BLOCK expected failure。不要重复开发这一证明链。

上一轮性能：

```text
perception→scene p50 ≈ 4.085 s, p95 ≈ 4.279 s
cuRobo planning p50 ≈ 1.112 s, p95 ≈ 1.144 s
sense→plan p50 ≈ 5.186 s, p95 ≈ 5.316 s
```

当前主要性能瓶颈是 frame fetch、robot/tool self-filter 和 voxel；性能优化排在外参 commissioning 与真实 A/B 之后。

---

# 2. 先利用“桌边已与 BODY 轴对齐”的新先验

## 2.1 桌面 support plane 决定 roll/pitch/z

继续使用当前稳定 support plane：

- normal → roll / pitch；
- `z_table_body = 0.750 m` → camera z；
- 输出 per-frame z、mean/std/max residual。

## 2.2 桌边方向作为 yaw prior

在 LEVEL frame 中提取桌面前缘/长直边方向，优先使用：

```text
support-plane convex hull / boundary
→ line RANSAC / robust PCA
→ dominant in-plane orthogonal directions
```

根据现场人工摆正关系建立：

```text
table front edge  ≈ BODY +Y / -Y direction
table outward normal ≈ BODY +X / -X direction
```

必须通过 Pixel Pro 灰度图和点云可视化确认选中的确是桌面边，不得把料架/秤边缘当桌边。

保存：

```text
operator_alignment_prior.json
  state = OPERATOR_ALIGNED_UNCOMMISSIONED
  table_edge_direction_level
  candidate_body_x
  candidate_body_y
  yaw_prior_deg
  confidence/evidence
```

该 prior 不获得 `planning_allowed=true`。

---

# 3. 底盘小范围 sweep 改成“验证 yaw”，不是从零求所有自由度

用户授权：底盘前/后/左/右单次平移 `<= 0.15 m`，禁止旋转，禁止机械臂/夹爪运动。

推荐第一次只做：

```text
O       origin capture
X+      +0.08~0.10 m forward
O       return + capture
Y+      +0.08~0.10 m left
O       return + capture
```

如果 table-edge yaw prior 与 X+/Y+ sweep 的 yaw 估计一致，再按需要补 X-/Y- 做冗余；若不一致，必须补 X-/Y-，不得选择性忽略。

底盘速度保守使用 `<=0.05 m/s`；每次单独确认。当前没有可靠 AMR 到站/静止闭环时：

```text
command accepted
→ operator visually confirms stopped
→ settle >= 1 s
→ capture
```

对静态环境做 frame-to-frame registration；重点使用桌面、电子秤、料架、固定背景。机械臂随相机一起移动，不得作为底盘相对运动 ICP 的主要静态参照。

输出每个 pair：

```text
estimated camera relative translation
estimated rotation drift
fitness / RMSE
expected BODY direction
inferred yaw
```

要求 table-edge yaw prior 与 base-sweep yaw 做交叉验证。

建议初始门：

```text
yaw disagreement target <= 2 deg
return-to-origin inverse-direction consistency clearly passes
```

如当前数据噪声证明该门不合理，先报告再调整，不得仅为了 PASS 放宽。

---

# 4. x/y 不再自由 6DoF ICP：只解平面平移

在 roll/pitch/z/yaw 被上述步骤固定后，只剩 camera origin 在 BODY 水平面的 `t_x/t_y`。

首选并行做两条：

## 4.1 人工测量先验（推荐，最快）

现场量取 BODY origin 到 Pixel Pro optical center 的水平投影：

```text
x_body_camera_measured_mm
y_body_camera_measured_mm
```

BODY origin 定义仍是两臂基座之间身体中心的地面投影；记录使用的测量基准、卷尺/尺具、估计误差。

不要假定 `y=0`，即使相机目测在中轴附近也要记录实测。

保存到：

```text
config/body_camera_mount_measurement.site.json
```

状态为 `MEASURED_PRIOR`。

## 4.2 受约束点云/机器人模型 refinement

固定 R 与 tz，只允许优化 tx/ty；使用当前右臂 live joints 与已审计 cuRobo/URDF 几何做多帧联合配准。

要求：

- 不允许 yaw/roll/pitch/z 再漂移；
- 多个初始化应收敛到近似相同 tx/ty；
- 输出 median/RMS/p90/inlier ratio；
- 与人工 x/y measurement 对比；
- 如果模型代理几何导致结果不稳定，保留人工测量为主、模型 overlay 为验证，不再退回自由 6DoF ICP。

---

# 5. Terminal 必须成为统一入口

在 ARES-R Terminal 接入：

```text
calib body-camera status
calib body-camera capture origin
calib body-camera table-edge
calib body-camera sweep plan
calib body-camera sweep run x+ 0.10
calib body-camera sweep run y+ 0.10
calib body-camera sweep run x- 0.10
calib body-camera sweep run y- 0.10
calib body-camera mount-measurement show
calib body-camera solve
calib body-camera validate
calib body-camera show
```

`sweep run` 必须：

- 只允许 translation；
- 单次 `<=0.15 m`；
- 禁止 yaw；
- 要求现场显式确认；
- 机械臂、夹爪 API 不得调用；
- 所有数据进入 `logs/calibration/body_camera/<run_id>/`。

Terminal 输出至少显示：

```text
roll/pitch source = TABLE
z source          = TABLE_HEIGHT_0.750
 yaw prior         = TABLE_EDGE_OPERATOR_ALIGNED
 yaw validation    = BASE_SWEEP
xy source          = MEASURED_PRIOR + CONSTRAINED_REFINEMENT
state              = UNCOMMISSIONED/CANDIDATE/COMMISSIONED
BODY_SCENE_ALLOWED = YES/NO
```

---

# 6. Commissioning Gate

生成：

```text
config/body_camera_extrinsics.site.json
```

状态只能为：

```text
UNCOMMISSIONED
CANDIDATE
COMMISSIONED
```

只有同时满足才允许 COMMISSIONED：

1. support plane 跨帧稳定；
2. table edge 被人工/图像明确确认；
3. table-edge yaw prior 与 base sweep yaw 一致；
4. table 变到 BODY 后高度稳定在约 0.750 m；
5. tx/ty 有独立人工测量或其它已知 BODY landmark 约束；
6. constrained tx/ty refinement 不出现大范围多解；
7. 多 sweep pose 变换后，静态外界相对 BODY 的变化方向/量与底盘平移一致；
8. 右臂模型与右臂点云 overlay 无明显整体偏轴/镜像；
9. R 正交、det(R)=+1；
10. 所有 provenance、revision、hash 完整。

不要使用当前 DEMO_ONLY candidate 的宽 residual 作为通过依据。

---

# 7. 外参通过后，才进入 Production A↔B planning-only

旧工作单中的 generic planning-only FREE/AVOID/BLOCK 已经完成，不再重复。

本阶段的新目标是：**用 COMMISSIONED `T_body_camera` 重跑真实 production scene。**

流程：

```text
scene acquire
→ production CAMERA→BODY
→ BODY ROI
→ whole-robot/tool self-filter
→ table known geometry
→ real residual AABB
→ ObservationEpoch
→ SceneSnapshot
→ SceneCompiler
```

检查：

- 之前因 DEMO 外参误差导致 endpoint collision 的 residual AABB 是否明显减少/消失；
- 不得为了让端点可规划而任意丢弃真实 obstacle；
- 如果某 AABB 仍与起点/目标重叠，要判断是 self-filter/target语义问题还是真实碰撞。

然后定义 versioned A/B：

```text
config/demo_pointcloud_ab.site.json
```

A/B 要求：同一右臂、相同末端姿态、水平 0.15~0.30m 左右、远离中央 slab/桌边/奇异区，并由 planner preview 选定。

执行三个 production planning-only 检查：

```text
CLEAR  fresh scan → plan PASS
AVOID  放置真实可见障碍 → fresh scan → plan绕行
BLOCK  明确测试 blocker → expected no-plan
```

AVOID 优先使用真实物理障碍；人工 augmentation 仅可作为额外 planner regression，不作为最终现场展示主证据。

本阶段仍不执行机械臂。

---

# 8. 明天进入 real-motion 前的最后准备

当且仅当外参与 production A/B planning-only 均通过，输出：

```text
READY_FOR_SUPERVISED_CLEAR = YES/NO
READY_FOR_SUPERVISED_AVOID = YES/NO
```

CLEAR real-motion 的最低门：

```text
T_body_camera COMMISSIONED
A/B commissioned
whole-robot collision scene valid
inactive arm geometry fresh
Tool/TCP revision match
speed profile commissioned
trajectory collision_checked=true
start-state match
SafetyKernel permit
operator present + E-stop
```

首次 real motion 只做 CLEAR、precision/slow、逐阶段确认；CLEAR 成功以后才做真实 AVOID。

---

# 9. 性能：本轮只复测，不先优化

已有：

```text
perception→scene p50 ≈ 4.085 s
planning p50 ≈ 1.112 s
sense→plan p50 ≈ 5.186 s
```

外参通过后，用 production scene 复测一次，确认量级。

不要在本轮先投入实时 GUI、nvblox、MPC 或大规模性能重构。完成可执行 Demo 基座后，下一独立任务再优化：

```text
frame fetch
self-filter
voxel
pipeline concurrency
```

---

# 10. 本轮 Exit Criteria

必须按顺序完成并停止：

1. table-edge yaw prior 有明确可视化/数值证据；
2. 小范围 base sweep 完成并验证 yaw；
3. table height 0.75 m 给出稳定 camera z；
4. tx/ty 有人工 measurement prior，并完成 constrained refinement/overlay；
5. `T_body_camera` 明确停在 UNCOMMISSIONED / CANDIDATE / COMMISSIONED 之一；
6. 若 COMMISSIONED：production BODY SceneSnapshot 建成；
7. 若 production scene 建成：production A/B CLEAR/AVOID/BLOCK planning-only 完成；
8. 输出明天 supervised CLEAR/AVOID 的 go/no-go；
9. 所有文件在 `/home/yikun/ARES-R`；
10. 本轮禁止机械臂和夹爪运动；AMR 只允许本工作单规定的 <=0.15m 平移标定动作。

不要继续 Skill Library / LLM / 实时 GUI / nvblox / MPC。