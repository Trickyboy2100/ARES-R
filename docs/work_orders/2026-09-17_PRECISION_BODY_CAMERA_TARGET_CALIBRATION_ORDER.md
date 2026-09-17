# 2026-09-17 精准 BODY↔Camera 外参：机器人携带标定板的 Eye-to-Hand 标定工作单

## 0. 结论先行

当前桌面平面 + 桌边方向 + 底盘小范围平移可继续保留为 sanity check / 方向验证，但不再作为 production `T_body_camera` 的主标定方法。

本轮 production 主方法改为：

```text
固定 Pixel Pro（eye-to-hand）
+ 右 JAKA Mini2 携带刚性标定板
+ 多姿态采集
+ robot FK / controller flange pose
+ board pose in CAMERA
→ Robot-World/Hand-Eye 初值
→ 基于 3D 点残差的联合非线性优化
→ hold-out validation
→ T_body_camera
```

目标是直接标定“点云 CAMERA frame → ARES-R BODY frame”的 6DoF 刚体变换，而不是继续依赖自由 ICP 猜整个机器人姿态。

---

## 1. 为什么替换当前主方案

当前 DEMO_ONLY 自由配准存在明显多解与大残差，不适合作为 production 外参。桌面单平面只能稳定约束 roll/pitch/法向距离；桌边和底盘平移主要提供 yaw/轴向验证；麦轮底盘的实际平移量、滑移与当前缺少高可信闭环位姿反馈，都不适合承担毫米级绝对外参标定。

因此：

- TABLE / table edge：保留为辅助约束与验收；
- BASE SWEEP：保留为 cross-check，不做主求解；
- FREE 6DoF ICP：停止作为 production solver；
- 主 solver：多姿态 robot-held target eye-to-hand calibration。

---

## 2. 标定硬件

优先使用一块刚性、尺寸可测、平整的多特征标定板：

```text
首选：ChArUco board / AprilGrid
备选：高精度圆点阵列 calibration board
```

要求：

- 标定板固定在右臂 flange 或刚性工具支架上，优先 flange，避免夹爪柔性/间隙；
- 标定板物理尺寸、marker/corner spacing 以 mm 记录；
- 板面不可翘曲；
- 若是打印板，固定到刚性平板并实测关键尺寸；
- 标定板全程不能相对 flange 发生移动。

若现场已有相机/视觉厂家原配 3D calibration board，优先使用原板并记录型号与尺寸。

---

## 3. 坐标与核心方程

定义：

```text
B = ARES-R BODY
G = 右臂 flange / gripper reference
T = calibration target board
C = Pixel Pro pointcloud CAMERA frame
```

每个姿态 i：

```text
T_B_G(i) · T_G_T = T_B_C · T_C_T(i)
```

未知：

```text
T_B_C = production T_body_camera
T_G_T = 标定板相对 flange 的固定安装变换
```

这两个 6DoF 变换可以利用多姿态数据联合求解，因此不要求人工精确量出 board 到 flange 的安装偏置。

---

## 4. CAMERA 侧观测：不要只用单像素 depth

每帧：

1. 获取同一 frameID 的 RGB / depth / pointcloud；
2. 在 RGB 中做 ChArUco / AprilGrid 亚像素角点检测；
3. 用标定板区域的 depth / pointcloud 做 robust plane fit；
4. 对每个亚像素角点，用 camera intrinsic 形成 ray，并与该帧 board plane 求交，得到 3D `p_C_ij`；
5. 同时保留传统 PnP 结果作为独立对照。

目的：减少直接读取角点单个 depth pixel 的噪声、空洞与边缘飞点。

每帧输出：

```text
frame_id
board_corner_count
2D reprojection RMS
board plane RMS
T_C_T initial
3D corner observations
```

---

## 5. ROBOT 侧观测

每个标定姿态必须读取“实际 controller 状态”，而不是只记录命令目标：

```text
joint_position_actual
flange_pose_actual / controller FK
T_B_G(i)
```

其中：

```text
T_B_G = T_B_armbase · T_armbase_G
```

使用当前已审计 BODY↔arm-base 固定安装变换，并把 revision/hash 写入 manifest。

捕获前要求机器人静止，连续两次关节读取差异低于阈值后再触发相机。

---

## 6. 采集姿态设计

不使用“所有板姿态几乎平行”的退化数据。

第一版目标 18–24 个有效姿态，至少覆盖：

```text
FOV 左 / 中 / 右
近 / 中 / 远 3 个深度层级
不同高度
board roll / pitch 各 ±15~30 deg 范围内变化
yaw 有明显变化
```

原则：

- 标定板始终完整或大部分可见；
- 避免极端斜角导致 depth 质量明显恶化；
- 避免奇异位形和工作区边界；
- 每个 pose 记录 robot state + camera frame + board detection quality；
- 低质量帧允许拒绝，但必须记录拒绝原因。

预留约 20% 姿态作为 hold-out validation，不参与最终优化。

---

## 7. Solver：OpenCV 初值 + 自定义 3D bundle refinement

### 7.1 初值

实现两条初值并交叉比较：

```text
OpenCV calibrateHandEye / eye-to-hand equivalent
OpenCV calibrateRobotWorldHandEye (AX=ZB)
```

至少比较 Shah / Li 或可用方法，不把单一 solver 当绝对真值。

### 7.2 production refinement

最终 production 求解使用 SciPy/Ceres 风格 SE(3) 非线性最小二乘，联合优化：

```text
T_B_C
T_G_T
```

最小化所有训练姿态、所有有效角点的 3D BODY 残差：

```text
r_ij = T_B_C · p_C_ij - T_B_G(i) · T_G_T · p_T_j
```

使用：

```text
Huber/Cauchy robust loss
per-corner depth/plane quality weight
SO(3) exponential-map parameterization
```

可额外加入弱约束：

```text
table normal / table z = 0.750 m
operator table-edge yaw prior
```

但这些只能做 weak prior / sanity check，不得压过 target+robot 的直接测量。

---

## 8. Validation：一定要用未参与求解的姿态

至少 4–6 个 hold-out poses。

对 hold-out 报告：

```text
3D point residual median / RMS / p95 / max
translation consistency
rotation consistency
board plane residual
2D reprojection residual
```

再做 3 组独立 system-level check：

1. TABLE：点云变到 BODY 后，桌面高度应稳定接近 `z=0.750 m`；
2. ROBOT OVERLAY：右臂真实点云与 cuRobo/URDF 模型对齐；
3. LEFT ARM CROSS-CHECK：不重新优化相机外参，只用左臂多个静态姿态/模型验证。若左臂产生系统性偏移，应优先检查 `T_body_leftbase`，不要重新扭曲 camera extrinsic。

如果条件允许，右臂求解、左臂验证是 production commissioning 的首选模式。

---

## 9. Commissioning gate

生成：

```text
config/body_camera_extrinsics.site.json
```

必须包含：

```text
T_body_camera
state
solver_revision
board_definition_hash
right_arm_base_revision
camera_intrinsics_revision
camera_serial
training_pose_ids
holdout_pose_ids
error_statistics
created_at
```

状态：

```text
UNCOMMISSIONED
CANDIDATE
COMMISSIONED
```

不得提前写死误差门限。先基于 Pixel Pro 点云噪声、机器人 FK/绝对精度和实测结果给出 error budget；然后设定 production threshold。

参考目标：应明显优于当前 DEMO_ONLY 的厘米级多解。若仍为厘米级或 yaw/translation 多解，则直接 FAIL，不进入避障执行。

---

## 10. Base sweep / table edge 的新角色

之前已实现的：

```text
table plane
table edge yaw prior
AMR +/- translation sweep
```

全部保留，但降级为 validation：

- table plane：检测 frame flip / z 方向 / 高度偏差；
- table edge：检测 yaw 大错误；
- base sweep：检测 CAMERA→BODY 轴正负号、相对位移一致性；
- 不再用麦轮平移命令值承担 production tx/ty 标定。

如果 base sweep 与 target-based calibration 明显冲突，优先检查：

```text
AMR slip / command-vs-actual motion
frame convention
board detection
T_body_armbase
```

不得平均两个互相矛盾的结果。

---

## 11. ARES-R Terminal 入口

实现/扩展：

```text
calib body-camera status
calib body-camera board define
calib body-camera board detect
calib body-camera target capture <pose_id>
calib body-camera target list
calib body-camera target solve
calib body-camera target validate
calib body-camera target show
calib body-camera commission
```

每个 capture 自动记录：

```text
camera frameID/hash
actual joints
actual flange pose
T_body_armbase revision
board detections
pointcloud/depth quality
```

所有输出只放：

```text
/home/yikun/ARES-R/logs/calibration/body_camera/<run_id>/
```

禁止再新建 ARES-R_AUDIT_* 目录。

---

## 12. 运行时 pointcloud→BODY

一旦 `T_body_camera=COMMISSIONED`，实时变换本身非常简单：

```text
p_body = T_body_camera · p_camera
```

运行时精度不靠继续 ICP，而靠：

```text
固定且 versioned T_body_camera
正确 depth scale/intrinsics
camera mount 未移动
frame timestamp/provenance
capture 时机器人状态同步
```

后续在线避障只需要对百万点做矩阵变换/ROI/self-filter，不再每帧重新标定 CAMERA→BODY。

---

## 13. 本轮退出条件

本工作单的目标是实现 production 标定能力，而不是立刻移动机械臂。

先完成：

1. target board 定义与 detector；
2. CAMERA 侧 2D+3D corner extraction；
3. robot state capture contract；
4. OpenCV initial solvers；
5. joint 3D nonlinear refinement；
6. train/hold-out validation；
7. Terminal workflow；
8. manifest/config schema；
9. 输出下一次现场实际采集需要的 18–24 个 pose 计划。

机械臂运动需单独获得现场授权；若未授权，本轮只能完成软件、board 准备与 pose preview。
