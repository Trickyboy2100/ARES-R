# 2026-09-20 原装标定板 → BODY↔Camera 精准外参工作单

## 0. 结论

现场现在已有迁移科技原装标定板，而且 EpicEye SDK 已实测可以直接返回标定板在 CAMERA frame 下的 6D pose：

```text
epiceye.get_calibration_board_pose(...)
→ [x, y, z, qx, qy, qz, qw]
```

因此当前 production `T_body_camera` 主线改为“原装标定板作为 6D fiducial anchor”，不再优先依赖 free ICP 或底盘 command displacement。

核心关系：

```text
B = ARES-R BODY
C = Pixel Pro CAMERA
Q = vendor calibration board

T_B_C = T_B_Q · inverse(T_C_Q)
```

SDK 已直接给出 `T_C_Q`。现在唯一需要可靠求出的就是 `T_B_Q`：标定板在 BODY 中的 pose。

---

## 1. 优先级

### P0：标定板检测/点云一致性

先确认 SDK pose 和同帧 pointcloud 完全一致：

1. 同一 frameID 获取 RGB/depth/pointcloud；
2. 调用 `get_calibration_board_pose`；
3. 根据 `T_C_Q` 预测 board plane / board normal / board origin；
4. 在点云中裁出 board ROI；
5. robust plane fit；
6. 比较：
   - plane normal angle error；
   - plane distance error；
   - board center residual；
   - point-to-plane RMS；
   - grid scale sanity（当前检测 gridSize=35 mm）。

如果 SDK board pose 与实际点云不能一致，STOP，不进入 BODY calibration。

### P1：求 T_B_Q

首选三条路线按以下优先级实现。

#### Route A — 机器人 TCP 触碰 3~6 个板上已知点（首选，当前硬件可实现）

标定板保持平放在桌面，不需要安装到机械臂。

选板上至少 3 个、建议 4~6 个非共线且几何坐标已知的 grid/corner 点：

```text
p_Q_j = board-frame known 3D point
```

现场通过 JAKA 手动/低速 jog，使经过验收的 TCP/point-tip 依次触碰同一物理点；只读取 controller actual state / FK：

```text
p_B_j = actual TCP point transformed to BODY
```

用 Kabsch/Umeyama rigid registration 求：

```text
T_B_Q
```

然后：

```text
T_B_C = T_B_Q · inverse(T_C_Q)
```

要求：

- 机械臂运动必须单独获得用户明确授权；
- 优先使用当前 TCP/工具标定证据更可靠的一侧；
- 不使用视觉结果指导触碰运动，触碰由人工监督/manual jog完成；
- 接触速度低，板固定不滑动；
- 每点至少采 2 次，记录重复性；
- 4+ 点做 least-squares，至少 1 点留作 hold-out；
- 输出 point residual median/RMS/max 和 leave-one-out residual；
- 桌面 z=0.750 m 只做独立 validation，不参与“硬拉”结果。

这是当前无额外硬件情况下最推荐的 production 路线。

#### Route B — 人工测量 board pose in BODY（最快但精度次一级）

若当前不授权机械臂接触：

- 标定板平放桌面；
- board plane z 已知约 0.750 m；
- board 轴与桌边/BODY 轴人工对齐；
- 人工量取 board origin/center 相对 BODY origin 的 x/y；
- 记录尺具和估计误差。

构造 `T_B_Q` 后，用 SDK `T_C_Q` 直接得到 `T_B_C`。

Route B 可先得到 CANDIDATE；是否 COMMISSIONED 取决于实际误差预算与后续 robot/table overlay 验证。

#### Route C — 固定 board + AMR 多姿态 robot-world calibration（自动化验证/备选）

标定板固定不动。

若 AMR 能提供可信 actual map/odom/localization SE(2) pose，则对多个 base pose i：

```text
T_W_B(i) · T_B_C · T_C_Q(i) = T_W_Q
```

联合求：

```text
T_B_C
T_W_Q
```

要求：

- 使用 actual pose，不使用 relative command displacement 充当精确真值；
- 至少包含平移和小 yaw 变化，否则 planar tx/ty 可观性不足；
- 当前底盘 localization confidence/pose quality 必须写入权重；
- Route C 主要作为 Route A/B 的 independent cross-check，不用低质量 AMR localization 覆盖更强的 board/TCP 几何证据。

---

## 2. 为什么 board 比静态桌面/ICP 更强

桌面平面只给 normal 和法向距离；free ICP 对当前机器人几何存在多解。

原装 board SDK 直接给 `T_C_Q` 完整 6DoF，且 board 尺寸/grid 固定。因此只要得到一次可靠 `T_B_Q`，完整 camera→BODY 外参就直接确定，不需要每帧重新 ICP。

运行时：

```text
p_B = T_B_C · p_C
```

board 不需要永远留在桌上。

如果 board 后续仍可见，可做 health-check：

```text
predicted T_B_Q = T_B_C · T_C_Q
vs commissioned T_B_Q
```

超过阈值则 scene 标记 calibration drift / invalid。

---

## 3. 对避障点云的直接验收

T_B_C candidate/commissioned 后必须做同帧验证：

### 3.1 Board check

将 board 周围点云变换到 BODY：

- board 平面高度/法向与 `T_B_Q` 一致；
- board geometry 与 SDK pose overlay 重合；
- 输出 board point-to-plane RMS 和 center/orientation residual。

### 3.2 Table check

- support table transformed z 应稳定接近 0.750 m；
- 4+ 帧高度 std / max residual；
- 桌面 normal 应与 BODY +Z 对齐。

### 3.3 Robot check

- right-arm model overlay；
- left-arm cross-check；
- 不重新优化 camera 外参去“迁就”左右臂；若单侧系统偏移，检查对应 `T_body_armbase` / TCP / robot model。

### 3.4 Obstacle check

在桌面放一个尺寸已知的箱体/物体：

- CAMERA cloud → BODY；
- cluster/AABB center/dims；
- 人工量测物体相对 BODY/table 的位置作 hold-out；
- 报告 center error / dimension error。

通过以上四项后，才允许 production pointcloud collision scene。

---

## 4. ARES-R Terminal 统一入口

所有功能必须位于 `/home/yikun/ARES-R` 并接入 Terminal：

```text
calib body-camera board status
calib body-camera board capture
calib body-camera board verify-cloud

calib body-camera board survey begin
calib body-camera board survey add <board_point_id>
calib body-camera board survey list
calib body-camera board survey solve
calib body-camera board survey validate

calib body-camera board manual-pose set ...
calib body-camera board robot-world solve

calib body-camera solve
calib body-camera validate
calib body-camera commission
calib body-camera show
```

输出：

```text
logs/calibration/body_camera/<run_id>/
config/body_camera_extrinsics.site.json
```

禁止创建新的 `ARES-R_AUDIT_*`。

---

## 5. 与当前 AMR 横移成果的关系

当前 y 横移已经实机跑通，这是好事，但它不再承担 production 外参的主要绝对真值。

保留用途：

- board 固定时改变 viewpoint；
- 验证 CAMERA/BODY axis sign；
- 做多位置 board pose consistency；
- future robot-world calibration；
- 检查 extrinsic 在不同 base poses 下是否保持一致。

AMR relative command 的距离/状态不能单独当毫米级真值，除非 actual localization/odom 另行验证。

---

## 6. Commissioning Gate

生成的 `config/body_camera_extrinsics.site.json` 状态只能为：

```text
UNCOMMISSIONED
CANDIDATE
COMMISSIONED
```

只有以下结果同时成立才允许 COMMISSIONED：

1. SDK board detection stable；
2. SDK board pose 与同帧 pointcloud board plane 一致；
3. `T_B_Q` 有独立 BODY 几何来源（Route A preferred；或足够可靠的 Route B/C）；
4. calibration point / hold-out residual 在误差预算内；
5. table z≈0.750 m 且 normal 正确；
6. right-arm + left-arm cross-check 无明显整体 frame error；
7. 已知测试障碍在 BODY 中的位置/尺寸与人工 hold-out 测量一致；
8. 多次重新 capture 得到相同 extrinsic / board-in-BODY consistency；
9. provenance：camera SN、SDK/FW、board/grid definition、tool/TCP revision、BODY/base revision 全部记录。

门限必须根据实测噪声设定；目标应明显优于之前 DEMO_ONLY 的厘米级多解。

---

## 7. 之后立即做的 production Demo

外参通过后：

```text
scene acquire
→ CAMERA→BODY
→ whole-robot self-filter
→ table known geometry
→ real residual obstacle
→ SceneSnapshot
→ SceneCompiler
→ cuRobo
```

然后重跑：

```text
CLEAR
AVOID（真实物理障碍）
BLOCK
```

仍先 planning-only。真实机械臂执行必须另行获得授权与 SafetyPermit。

---

## 8. 当前退出条件

本轮先完成：

1. vendor-board SDK detector 封装；
2. same-frame board↔pointcloud consistency checker；
3. Route A/B/C solver 软件；
4. Terminal commands；
5. board survey / manual pose schema；
6. 输出最少现场操作步骤。

在用户未授权机械臂触碰前，不执行机械臂运动。
