# 2026-09-17 BODY↔Camera 外参：底盘小范围平移标定 + Terminal 一体化工作单

## 0. 目标

当前 ARES-R 已经能稳定从 Pixel Pro 点云中识别桌面主平面，并建立 `LEVEL_ONLY_NOT_BODY` 坐标：桌面法向稳定、俯角约 49.55°。但完整 `T_body_camera` 仍未 commission，因此 CAMERA 点云尚不能可靠转换为 ARES-R BODY 坐标，也不能作为双臂实机避障的正式输入。

本轮目标是利用：

- 已知桌面高度 `z_body = 0.750 m`；
- 已授权、且现场确认安全的底盘前后/左右 `<= 0.15 m` 平移；
- Pixel Pro 多帧点云；
- 当前 ARES-R BODY 坐标定义；
- 已知左右臂基座和机器人模型；

把 `T_body_camera` 从“多解诊断”推进到“可量化验证的候选”，并把整套标定/场景流程接入 ARES-R Terminal。

所有新代码、配置、日志、图片、manifest 都必须位于 `/home/yikun/ARES-R` 内。禁止新建新的 `/home/yikun/ARES-R_AUDIT_*` 工作目录；旧审计目录只允许读。

## 1. 当前事实与几何结论

当前跨四帧桌面主平面：

```text
mean normal_camera ≈ [0.046354, 0.647166, 0.760939]
mean plane d       ≈ -0.820625 m
normal max drift   ≈ 0.0862°
offset std         ≈ 0.425 mm
```

桌面高度由现场人工确认：

```text
z_table_body = 0.750 m
```

若主平面确实为桌面，且法向方向一致，则相机光心的 BODY 高度候选约为：

```text
z_camera_body ≈ 0.750 + 0.820625 = 1.570625 m
```

这一数值只能作为 `z` 约束和 sanity check，不能单独生成完整 `T_body_camera`。

单张静态水平桌面只能可靠约束：

- roll/pitch；
- camera 到桌面的法向距离；
- 配合桌面已知高度，可约束 `t_z`。

它不能唯一确定：

- BODY yaw；
- `t_x`；
- `t_y`。

因此禁止把 `LEVEL_ONLY_NOT_BODY` 或当前 auto-registration 任一多解矩阵标成 `COMMISSIONED`。

## 2. 用户授权的底盘运动范围

本轮仅授权为了相机/BODY 外参标定而进行的小范围底盘平移：

```text
前/后/左/右单次 |translation| <= 0.15 m
```

禁止：

- 机械臂运动；
- 夹爪运动；
- 底盘旋转/yaw；
- 超过 0.15 m 的单次平移；
- 连续自动巡航；
- 在未确认工作区静态/净空时继续运动。

建议实际 sweep 使用 `0.10 m`，而不是顶满 0.15 m：

```text
O      原点
X+     +0.10 m forward
O      返回
X-     -0.10 m backward
O      返回
Y+     +0.10 m left
O      返回
Y-     -0.10 m right
O      返回
```

移动速度采用保守低速（默认 `0.05 m/s`，不得超过当前 AMR site limit）；每次动作必须单独确认，动作后等待底盘静止/settle，再触发相机。

如果当前 AMR adapter 没有可信的“真实到站/静止”反馈，本轮 calibration sweep 必须采用：

```text
command accepted
→ operator confirms physically stopped
→ settle >= 1 s
→ capture
```

不得把 HTTP 返回成功当作实际到位。

## 3. 为什么底盘平移有用

相机与 BODY 刚性连接，`T_body_camera` 在所有 sweep pose 中保持不变。

对静态环境，两次点云之间可以估计相机相对运动 `ΔT_camera`。底盘命令提供 BODY 中的已知运动方向：

```text
+X_body / -X_body / +Y_body / -Y_body
```

通过多方向平移，可以稳定确定 CAMERA 轴与 BODY 的水平轴方向，从而解决 LEVEL frame 中“yaw arbitrary”的问题。

注意：纯平移不会让相机光心的 BODY 平面内位置 `t_x/t_y` 完全可观。因此本轮要把问题拆成：

1. 桌面法向 → roll/pitch；
2. 多方向底盘平移 → yaw；
3. 桌面已知高度 → `t_z`；
4. `t_x/t_y` → 通过已知机器人几何约束或一次人工测量/已知 BODY landmark 求解。

如果最终只剩 `t_x/t_y` 不可观，必须明确报告，不得硬猜。

## 4. 新增 ARES-R 标定模块

建议实现：

```text
src/ares_r/calibration/
  __init__.py
  body_camera.py
  rigid_registration.py
```

至少提供：

```text
fit_table_plane(...)
estimate_level_rotation(...)
estimate_yaw_from_base_sweep(...)
estimate_camera_height_from_table(...)
solve_planar_translation_from_robot_geometry(...)
validate_body_camera_transform(...)
```

每个函数必须纯计算、可离线测试。

不得直接在算法模块里调用 AMR/JAKA/Epic motion API。

## 5. 底盘 sweep 数据采集

所有本轮输出放到：

```text
logs/calibration/body_camera/<run_id>/
```

每个 pose 目录保存：

```text
manifest.json
frame.epicraw
pointcloud.ply   # debug/evidence，可选保存
image8bit.png
plane_fit.json
relative_registration.json
```

顶层保存：

```text
run_manifest.json
motion_plan.json
solve_result.json
validation.json
```

其中 `run_manifest.json` 必须记录：

- git commit；
- Pixel Pro SN；
- frameID/hash；
- BODY motion command；
- operator stop confirmation；
- capture timestamp；
- table height = 0.750 m；
- algorithm parameters；
- any rejected frame。

## 6. 点云相对运动估计

对 sweep 相邻帧，先做：

```text
invalid remove
→ 10 mm voxel
→ table/large static background features
→ global/feature seed if needed
→ ICP refinement
```

不要直接用机械臂自身作为唯一 ICP 几何，因为机器人与相机同属移动平台，在 CAMERA frame 中它不会像外界那样提供独立环境运动约束。

重点使用桌面、电子秤、料架、固定背景等静态场景。

每个 pair 输出：

```text
estimated camera relative translation
estimated camera relative rotation
fitness
RMSE
expected BODY translation direction
angular drift
```

如果某次底盘平移过程中出现明显 yaw 漂移（例如点云估计旋转超过预设小阈值），该 pair 必须拒绝，不能用于标定。

## 7. yaw 求解

利用至少两个非共线平移方向：

```text
+X_body
+Y_body
```

与 CAMERA 中估计到的相机运动方向配对，结合桌面法向作为第三轴，求唯一正交旋转 `R_body_camera`。

要求：

- 用 +X/-X、+Y/-Y 多组数据做冗余；
- 输出每组 yaw estimate；
- 输出 mean/std/max disagreement；
- 方向符号必须通过返回原点的逆向 motion cross-check。

## 8. z 求解

使用桌面：

```text
z_table_body = 0.750 m
```

和 CAMERA 平面方程，在已知旋转后求 camera origin 的 BODY `z`。

输出：

```text
z_camera_body
per-frame estimate
std
max residual
```

当前约 `1.5706 m` 只作为 sanity check，不写死。

## 9. x/y 求解

首选顺序：

### 9.1 约束后的机器人模型配准

当前自动注册多解主要来自 yaw/translation 同时未知。现在先用 sweep 固定 `R_body_camera` 与 `t_z`，只优化 `t_x/t_y`，再用当前右臂 live joints + 已审计 cuRobo/URDF 几何做 constrained planar registration。

要求：

- 只允许优化 `t_x/t_y`；
- 使用多个相机帧联合优化；
- 输出 residual / inlier ratio；
- 多初始化结果必须收敛到近似同一平移。

### 9.2 如果仍不稳定

要求现场人工量取一次：

```text
BODY origin → Pixel Pro optical center
```

至少量取水平 `x/y`，单位 mm，并记录测量方法/误差。该测量仅作为先验，再由点云/robot overlay 做 refinement。

不要继续让自由 6DoF ICP 猜。

## 10. Commissioning 门

最终生成：

```text
config/body_camera_extrinsics.site.json
```

状态只能是：

```text
UNCOMMISSIONED
CANDIDATE
COMMISSIONED
```

只有同时满足以下条件才允许 `COMMISSIONED`：

1. table normal 跨帧稳定；
2. sweep yaw 由 +X/-X/+Y/-Y 一致支持；
3. table z 转换后在 BODY 中约为 `0.750 m`，多帧残差达到设定门限；
4. 右臂模型 overlay 在多个 sweep 帧中 residual 达标；
5. `t_x/t_y` 多初始化/多帧解稳定；
6. 变换矩阵正交、det(R)=+1；
7. 把不同 sweep pose 点云变到各自 BODY frame 后，静态场景相对运动与已知底盘运动一致；
8. 人工可视化检查无明显轴翻转或镜像。

门限在实现前先根据传感器噪声和现有 residual 提出，不得靠放宽阈值让结果通过。

## 11. Terminal 一体化

本轮必须把标定流程接入 ARES-R Terminal，避免以后靠独立脚本拼接。

建议命令：

```text
calib body-camera status
calib body-camera capture origin
calib body-camera sweep plan
calib body-camera sweep run x+ 0.10
calib body-camera sweep run x- 0.10
calib body-camera sweep run y+ 0.10
calib body-camera sweep run y- 0.10
calib body-camera solve
calib body-camera validate
calib body-camera show
```

要求：

- `sweep run` 只允许 AMR 平移，不允许旋转；
- 单次距离硬限制 `<=0.15 m`；
- 每次都要求现场显式确认；
- 机械臂、夹爪 API 不得被调用；
- Terminal 输出当前 `T_body_camera` 状态和是否允许生成 BODY Scene。

## 12. 之后的 Scene / 避障入口

一旦 `T_body_camera = COMMISSIONED`，Terminal 应支持标准流程：

```text
scene acquire
scene show
scene benchmark
curobo ab plan clear
curobo ab plan avoid
curobo ab plan block
```

其中：

```text
scene acquire
```

执行：

```text
Pixel Pro capture/decode
→ CAMERA→BODY
→ BODY ROI
→ 双臂/tool self-filter
→ support/table separation
→ residual voxel/cluster/AABB
→ ObservationEpoch
→ WorldModel.freeze()
→ SceneSnapshot
```

所有新 scene/benchmark/demo 输出均位于 ARES-R：

```text
logs/scenes/
logs/demo_runs/
worklog/evidence/
```

大型 EpicRaw/PLY 不提交 Git；提交 manifest/hash、参数、摘要和关键截图。

## 13. 性能计时

标定通过后立刻测：

```text
capture
fetch/decode
camera_to_body
ROI
self_filter
table separation
voxel
cluster/AABB
WorldModel commit
SceneCompiler
curobo world update
planning
TOTAL sense-to-plan
```

记录 p50/p90/p95/max，并据此决定未来：

```text
Static Snapshot
Checkpoint Rescan
Scene Watchdog
Reactive MPC
```

而不是预先写死扫描频率。

## 14. 本轮退出条件

本轮可以完成到底盘 sweep 和 candidate/commissioning；不得执行机械臂。

最终必须明确回答：

1. `T_body_camera` 是否已经可准确用于 BODY 点云？
2. 若未 commission，精确缺哪一维/哪项证据？
3. table height 0.75 m 得到的 camera z 是多少？
4. 底盘 sweep 解出的 yaw 稳定性如何？
5. constrained x/y registration 是否唯一？
6. Scene pipeline 是否已经可以生成 BODY SceneSnapshot？
7. sense-to-plan 预计/实测延迟是多少？
8. 明天周帅旭可以从哪条 Terminal 命令开始？

完成后停止，不自行开始机械臂运动。
