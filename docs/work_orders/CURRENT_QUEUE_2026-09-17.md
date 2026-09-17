# CURRENT QUEUE — 2026-09-17

当前项目只认这一条队列。旧工作单保留为历史证据，不应重复执行。

## 已完成，不再排队

1. `2026-09-17_POINTCLOUD_CUROBO_AVOIDANCE_DEMO_ORDER.md`
   - 已完成 DEMO_OFFLINE_ONLY pointcloud → SceneSnapshot → cuRobo FREE/AVOID/BLOCK；
   - 已完成 fast-path latency benchmark；
   - 不再重复。

2. `2026-09-17_CUROBO_POINTCLOUD_AB_AVOIDANCE_DEMO_ORDER.md`
   - 其中 generic planning-only 目标已被上面的完成结果覆盖；
   - 其中 `T_body_camera` commissioning 和 production A/B 部分由新的统一工作单接管；
   - 不单独执行。

3. `planning/20260917-body-camera-base-sweep` 中的 `2026-09-17_BODY_CAMERA_BASE_SWEEP_TERMINAL_ORDER.md`
   - 设计思想保留；
   - 已被“桌边人工对齐”这个新现场事实更新；
   - 不单独执行。

## 当前唯一 Active Task

执行：

`docs/work_orders/2026-09-17_BODY_CAMERA_ALIGNMENT_TO_PRODUCTION_AB_QUEUE.md`

顺序固定：

```text
桌面法向 + 0.75m 高度
→ 桌边方向 yaw prior
→ <=0.15m 底盘小范围 sweep 验证 yaw
→ 人工测量 camera x/y + constrained refinement
→ T_body_camera commissioning
→ production BODY SceneSnapshot
→ production A/B CLEAR/AVOID/BLOCK planning-only
→ 明日 supervised real-motion go/no-go
```

## 本队列禁止事项

- 机械臂运动；
- 夹爪运动；
- 底盘旋转；
- 底盘单次平移 > 0.15m；
- Skill Library / LLM；
- 实时 GUI；
- nvblox / MPC；
- 为了 PASS 放宽 calibration/collision gate；
- 使用 DEMO_ONLY `T_body_camera` 获得实机执行许可。

所有新增工作必须位于 `/home/yikun/ARES-R`。