# CURRENT QUEUE — 2026-09-17

当前项目只认这一条队列。旧工作单保留为历史证据，不应重复执行。

## 已完成，不再排队

1. `2026-09-17_POINTCLOUD_CUROBO_AVOIDANCE_DEMO_ORDER.md`
   - 已完成 DEMO_OFFLINE_ONLY pointcloud → SceneSnapshot → cuRobo FREE/AVOID/BLOCK；
   - 已完成 fast-path latency benchmark；
   - 不再重复。

2. `2026-09-17_CUROBO_POINTCLOUD_AB_AVOIDANCE_DEMO_ORDER.md`
   - generic planning-only 目标已完成；
   - production 外参与真实 A/B 后续由当前精准标定主线接管；
   - 不单独执行。

3. `2026-09-17_BODY_CAMERA_ALIGNMENT_TO_PRODUCTION_AB_QUEUE.md`
   - table plane / table edge / base sweep 代码与证据保留；
   - 这些方法降级为 sanity check / validation；
   - 不再作为 production `T_body_camera` 的主求解方法。

## 当前唯一 Active Task

执行：

`docs/work_orders/2026-09-17_PRECISION_BODY_CAMERA_TARGET_CALIBRATION_ORDER.md`

production 主线改为：

```text
固定 Pixel Pro eye-to-hand camera
+ 右 JAKA Mini2 携带刚性标定板
+ 18~24 个多样化 flange poses
+ 同步 actual robot state + RGB/depth/pointcloud
→ board 2D/3D features
→ Robot-World/Hand-Eye 初值
→ 联合优化 T_body_camera + T_flange_board
→ hold-out validation
→ 右臂求解 / 左臂交叉验证
→ T_body_camera COMMISSIONED
→ production BODY SceneSnapshot
→ production A/B CLEAR / real-obstacle AVOID / BLOCK
→ supervised real-motion go/no-go
```

## 当前保留但降级为验证的现场信息

```text
桌面 support plane
桌高 0.750 m
桌边与 BODY 轴人工对齐 prior
AMR 前/后/右小范围 sweep
```

用途：检测 z/yaw/frame sign/相对位移错误；不得用麦轮 command displacement 作为毫米级 production tx/ty 真值。

## 当前动作边界

在用户再次明确授权机械臂运动前：

- 不执行机械臂运动；
- 不执行夹爪运动；
- 已有 AMR sweep 若正在进行，只能完成已授权的小范围 validation，不再把它作为主标定数据；
- 不做新的底盘旋转；
- 不开始真实 A/B 执行。

当前 Codex 优先完成：

```text
标定板定义/检测
3D corner extraction
robot state capture contract
OpenCV hand-eye / robot-world-hand-eye initial solver
3D robust nonlinear refinement
hold-out validation
Terminal workflow
18~24 pose collection plan
```

## 禁止事项

- 自由 6DoF ICP 继续作为 production 主 solver；
- 为了 PASS 放宽 calibration gate；
- 使用 DEMO_ONLY `T_body_camera` 获得实机执行许可；
- Skill Library / LLM；
- 实时 GUI / nvblox / MPC 优先于 production extrinsic；
- 新建 `/home/yikun/ARES-R_AUDIT_*` 工作目录。

所有新增代码、配置、日志和 evidence 必须位于 `/home/yikun/ARES-R`。
