# 2026-09-17 无额外标定硬件的 BODY↔Camera 精准标定工作单

## 0. 现场约束与结论

现场没有 ChArUco / AprilGrid / 精密标定板等额外硬件。production `T_body_camera` 的主线因此改为 **targetless motion-based calibration**：利用固定 Pixel Pro、静态前方环境、底盘可控运动和点云配准，估计相机相对 ARES-R BODY 的固定 6DoF 外参。

禁止继续把单帧自由 6DoF robot-cloud ICP 作为 production 主 solver；桌面/桌边/右臂模型仍可作为约束和验证。

当前已授权的底盘动作只有前/后/左/右单次 <= 0.15 m 的平移。底盘 yaw 旋转只有在用户另行明确授权后才能执行。

所有代码、日志、配置、图片、manifest 必须位于 `/home/yikun/ARES-R`。

---

## 1. 可观测性：必须先在软件里显式判断

设固定外参：

```text
X = T_body_camera
```

对任意两次机器人姿态：

```text
A_i X = X B_i
```

其中：

- `A_i`：BODY 在两次采样间的真实相对运动；
- `B_i`：Pixel Pro 通过静态环境点云配准估计出的 CAMERA 相对运动。

### 1.1 只有纯平移时

若所有 `A_i` 都是纯平移：

```text
R_body_camera
```

可由多个非共线平移方向约束，但 `t_body_camera` 会从 hand-eye 平移方程中消掉，因此 **绝对 tx/ty 不能只靠纯平移恢复**。

所以当前已授权的前/后/右平移可用于：

- 估计/验证 yaw 与轴正负号；
- 验证点云尺度；
- 验证 scene registration；
- 不能单独完成 production tx/ty。

### 1.2 若允许小角度 BODY yaw 旋转

如果以后用户授权安全的小角度原地旋转，旋转会让相机光心因为其相对 BODY 中心的水平偏置而产生圆弧位移，从而使 `tx/ty` 可观。

结合：

- 多方向平移；
- 至少 2~4 个正负 yaw 旋转；
- 已知桌面高度约 0.750 m；

可以在没有标定板的情况下求完整 `T_body_camera`。

若没有可信底盘实际 pose/odometry，可从静态环境点云序列估计相机轨迹，再把机器人运动约束写入联合优化；但必须把底盘 slip / 非理想旋转中心计入不确定度。

---

## 2. 第一优先：审计底盘是否提供真实位姿

在任何新运动前，先在 ARES-R 与现场 AMR API/SDK 中搜索：

```text
pose
position
localization
odom
odometry
slam pose
robot pose
x/y/yaw
twist / velocity
```

目标是判断是否能获得时间戳化的实际 BODY SE(2) 位姿，而不是只得到 command accepted。

输出：

```text
worklog/evidence/body_camera_targetless/amr_pose_api_audit.md
```

分级：

```text
A = 有高可信 SLAM/localization pose，可直接作为 A_i
B = 只有 wheel odom / approximate pose，可作带权先验
C = 只有 command displacement，无实际 pose
```

如果为 A：优先走标准 motion-based hand-eye。
如果为 B/C：继续第 4 节 joint optimization，但不得把 command displacement 当毫米级真值。

---

## 3. CAMERA 运动估计：静态场景多帧配准

对每次相机采样的前方静态环境：

```text
raw cloud
→ invalid remove
→ 10~20 mm voxel for registration
→ remove robot/self region where possible
→ support plane + fixed background features
→ FPFH/feature seed if needed
→ Generalized ICP / point-to-plane ICP refinement
→ B_i = T_Ci_Cj
```

不得用随机机器人自身几何作为主要 scene-registration 参照，因为机器人与相机刚性共动。

建议组合：

- Open3D Generalized ICP / point-to-plane ICP；
- multi-scale coarse→fine；
- robust kernel；
- pairwise registration + pose graph consistency；
- 对低 fitness / 高 RMSE pair fail-closed。

每个 pair 保存：

```text
relative transform
fitness
RMSE
inlier count
static-scene region used
registration direction consistency
```

---

## 4. 无标定板联合求解器

实现：

```text
src/ares_r/calibration/targetless_motion.py
```

### 4.1 有真实 AMR pose 时

从 AMR pose 得到 `A_i`，从点云配准得到 `B_i`，先解：

```text
A_i X = X B_i
```

使用多个 motion pair，并对结果做 robust nonlinear refinement。

优化变量：

```text
X = T_body_camera
```

目标项：

```text
SE(3) hand-eye residual over all motion pairs
```

再加入弱约束：

```text
table normal → body +Z
table height → z≈0.750 m
operator table-edge direction → yaw sanity prior
```

### 4.2 无可信 AMR pose 时

联合优化：

```text
X = T_body_camera
P_i = each BODY pose in a local world, constrained to planar SE(2)
```

相机 pose 由点云 pose graph 给出 `C_i`，要求：

```text
C_i ≈ P_i X
```

同时加入动作约束：

```text
forward command → ΔP primarily +X
right command   → ΔP primarily -Y
return command  → near inverse motion
if yaw motion later authorized: ΔP is primarily Rz(theta)
```

command displacement 只作软约束，不作为绝对距离真值。

### 4.3 纯平移不可观维度必须显式报告

如果当前数据只有平移，不允许 solver“靠正则化”假装解出 tx/ty。

必须输出 observability report，例如：

```text
rotation: OBSERVABLE
tz: OBSERVABLE_FROM_TABLE_HEIGHT
tx/ty: UNOBSERVABLE_WITH_TRANSLATION_ONLY
```

只有引入以下任一独立信息后，才允许 tx/ty 进入 candidate：

1. 用户另行授权小角度原地 yaw，且旋转中心可信；
2. AMR 提供实际 SE(2) pose；
3. 可见机器人/底座已知 BODY 几何用于 constrained model refinement；
4. 一次人工量取 camera optical center 相对 BODY origin 的水平 x/y。

---

## 5. 旋转中心法（无额外硬件时的推荐补充）

如果用户后续明确授权底盘小角度原地 yaw，则优先做：

```text
O
→ yaw +θ
→ O
→ yaw -θ
→ O
```

第一版建议只做小角度，具体角度/速度由现场净空和 AMR 能力决定，必须再次获得明确授权后执行。

对静态场景点云估计 CAMERA trajectory。理想原地 yaw 时，camera optical center 在水平面上绕 BODY origin 走圆弧：

- rotation axis → BODY +Z；
- circle center → BODY origin 的水平位置；
- circle radius/vector → camera `tx/ty`；
- table plane + table height → camera `tz`；
- forward/right translation motions → BODY +X/+Y 的方向与 yaw 零位。

实现 circle/SE(2) constrained bundle fit，并用正负 yaw、返回原位和多个角度做冗余。

若拟合显示实际旋转中心漂移明显，则把 base yaw 视为低可信，不 commission；转而使用已知 robot/body geometry 或人工 x/y prior。

---

## 6. 已知机器人几何作为无额外硬件 refinement

当前 Pixel Pro 能看到部分右臂/工具。待 motion-based solver 提供稳定 rotation 与平移初值后，可做 constrained model refinement：

```text
fixed R_body_camera and/or narrow prior
+ live right-arm joints
+ cuRobo/URDF link geometry in BODY
+ camera cloud robot ROI
→ optimize only remaining weak dimensions
```

要求：

- 不再自由 6DoF；
- 使用多个 base poses 共同优化同一个 `T_body_camera`；
- 多初始化必须收敛；
- 左臂只做独立 cross-check，不用扭曲 camera extrinsic 去迁就错误的 arm-base transform。

---

## 7. Validation / commissioning

候选 `T_body_camera` 必须通过独立验证：

1. TABLE：各帧转 BODY 后桌面高度稳定接近 0.750 m；
2. TABLE NORMAL：接近 BODY +Z；
3. MULTI-POSE STATIC SCENE：同一外部物体在不同 base pose 下经 BODY/world compensation 后一致；
4. RETURN-TO-ORIGIN：往返运动后的 camera pose graph 闭环残差小；
5. RIGHT ARM OVERLAY：模型与 robot cloud 对齐；
6. LEFT ARM CROSS-CHECK：如果可见，独立验证；
7. AXIS SIGN：BODY +X / -Y 动作与 scene 相对移动方向一致；
8. R 正交且 det(R)=+1。

先根据实测噪声建立 error budget，再设 COMMISSIONED threshold；不得为了 PASS 放宽门。

---

## 8. Terminal

复用/扩展：

```text
calib body-camera status
calib body-camera targetless plan
calib body-camera capture <label>
calib body-camera registration solve
calib body-camera observability
calib body-camera validate
calib body-camera show
calib body-camera commission
```

如果以后用户授权 yaw：

```text
calib body-camera sweep yaw-plus <angle>
calib body-camera sweep yaw-minus <angle>
```

这些命令必须再次检查 motion authorization，不得沿用旧平移授权。

---

## 9. 本轮立即执行范围

在现有授权下，Codex 现在应：

1. 完成 AMR actual-pose API 审计；
2. 完成多帧 static-scene registration / pose graph；
3. 用已有 origin / forward / right / return 数据估计 CAMERA motion；
4. 生成 observability report；
5. 实现 `AX=XB` 与 joint planar optimization solver；
6. 把桌面 0.75 m、桌边、已有 base translation 作为 validation；
7. 若 tx/ty 因纯平移不可观，明确 STOP 在该门，不伪造值；
8. 输出“若允许小角度 yaw，需要怎样的最小 motion sequence”。

本轮仍禁止机械臂/夹爪运动，且没有新的 yaw 授权。
