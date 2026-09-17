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
   - 这些方法作为 targetless calibration 的约束/validation；
   - 不再把 command displacement 当 production tx/ty 真值。

4. `2026-09-17_PRECISION_BODY_CAMERA_TARGET_CALIBRATION_ORDER.md`
   - 需要额外刚性标定板/target；
   - 当前现场没有该硬件条件；
   - 设计保留为未来高精度可选方案，不在当前队列执行。

## 当前唯一 Active Task

执行：

`docs/work_orders/2026-09-17_TARGETLESS_BODY_CAMERA_MOTION_CALIBRATION_ORDER.md`

当前 production 主线：

```text
固定 Pixel Pro
+ 静态前方环境
+ 底盘多姿态运动
+ 点云 scene registration / pose graph
+ AMR actual pose（若可获得）
→ motion-based hand-eye AX=XB
→ planar constrained joint optimization
→ table normal / table height / table edge validation
→ visible robot geometry constrained refinement（如需要）
→ T_body_camera COMMISSIONED
→ production BODY SceneSnapshot
→ production A/B CLEAR / real-obstacle AVOID / BLOCK
```

## 当前可观测性原则

- 仅有纯平移时，可很好验证 rotation/yaw、轴正负号、尺度；
- 仅靠纯平移不能唯一恢复 absolute tx/ty，solver 不得通过正则化伪造；
- 完整 tx/ty 需要以下任一独立信息：
  1. 用户另行授权小角度原地 yaw，使 camera offset 对旋转中心可观；
  2. AMR 提供可信 actual SE(2) pose / SLAM localization；
  3. 可见 robot/body 已知 BODY 几何做 constrained refinement；
  4. 一次人工量取 camera optical center 相对 BODY origin 的水平 x/y。

当前桌面高度 `0.750 m` 用于约束/验证 camera z。

## 当前动作边界

- 已授权：前/后/左/右单次 <= 0.15 m 的底盘纯平移，用于 calibration/validation；
- 不执行机械臂运动；
- 不执行夹爪运动；
- 当前没有新的底盘 yaw 授权；
- 不开始真实 A/B 执行；
- 如需要 yaw calibration motion，必须先向用户明确说明最小角度/序列并获得单独授权。

## 当前 Codex 优先完成

```text
AMR actual-pose / localization API 审计
→ static-scene multi-frame registration
→ camera pose graph
→ observability report
→ AX=XB motion-based solver
→ planar constrained joint optimization
→ table 0.75m / table-edge / existing translation sweep validation
→ 给出是否还缺 tx/ty，以及最小补充运动方案
```

## 禁止事项

- 自由 6DoF ICP 继续作为 production 主 solver；
- 在纯平移不可观条件下伪造 tx/ty；
- 为了 PASS 放宽 calibration gate；
- 使用 DEMO_ONLY `T_body_camera` 获得实机执行许可；
- Skill Library / LLM；
- 实时 GUI / nvblox / MPC 优先于 production extrinsic；
- 新建 `/home/yikun/ARES-R_AUDIT_*` 工作目录。

所有新增代码、配置、日志和 evidence 必须位于 `/home/yikun/ARES-R`。
