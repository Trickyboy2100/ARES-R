# CURRENT QUEUE — 2026-09-20

当前项目只认这一条队列。旧工作单保留为历史证据，不应重复执行。

## 已完成，不再排队

1. `2026-09-17_POINTCLOUD_CUROBO_AVOIDANCE_DEMO_ORDER.md`
   - 已完成 DEMO_OFFLINE_ONLY pointcloud → SceneSnapshot → cuRobo FREE/AVOID/BLOCK；
   - 已完成 fast-path latency benchmark；
   - 不再重复。

2. `2026-09-17_CUROBO_POINTCLOUD_AB_AVOIDANCE_DEMO_ORDER.md`
   - generic planning-only 目标已完成；
   - production 外参与真实 A/B 后续由当前 vendor-board 主线接管；
   - 不单独执行。

3. `2026-09-17_BODY_CAMERA_ALIGNMENT_TO_PRODUCTION_AB_QUEUE.md`
   - table plane / table edge / base sweep 代码与证据保留为 validation；
   - 不再作为 production `T_body_camera` 主求解。

4. `2026-09-17_TARGETLESS_BODY_CAMERA_MOTION_CALIBRATION_ORDER.md`
   - targetless motion / AX=XB 设计保留；
   - 现已有原装标定板且 SDK 可直接返回 board 6D pose；
   - 因此降级为 secondary cross-check，不再是主线。

5. `2026-09-17_PRECISION_BODY_CAMERA_TARGET_CALIBRATION_ORDER.md`
   - 该方案假设“标定板需安装到机械臂”；
   - 现场原装 board 当前平放桌面即可被 SDK 识别；
   - 不再要求把 board 安装到机械臂。

## 当前唯一 Active Task

执行：

`docs/work_orders/2026-09-20_VENDOR_BOARD_BODY_CAMERA_CALIBRATION_ORDER.md`

production 主线改为：

```text
原装 vendor calibration board 固定在桌面
+ EpicEye SDK 直接给 T_camera_board
+ 同帧 pointcloud 验证 board pose
→ 求 T_body_board
   Route A: 机械臂 TCP 触碰 3~6 个已知 board 点（首选，需另行授权）
   Route B: 人工测量 board pose in BODY
   Route C: AMR actual pose + 多位置 board observation robot-world solve（备选/验证）
→ T_body_camera = T_body_board · inv(T_camera_board)
→ board/table/双臂/已知障碍 hold-out validation
→ T_body_camera COMMISSIONED
→ production BODY SceneSnapshot
→ production A/B CLEAR / real-obstacle AVOID / BLOCK
```

## 当前已确认现场事实

- 原装 calibration board 已平放桌面；
- SDK `get_calibration_board_pose` 已实测 Success；
- gridSize = 35 mm；
- board pose 可直接得到 CAMERA-frame translation + quaternion；
- AMR y 横移目前已实机跑通；
- AMR 横移用于 viewpoint / consistency validation，不作为毫米级 absolute extrinsic 真值；
- 桌面高度约 0.750 m，继续作为 z sanity check。

## 当前动作边界

- 不因本工作单自动授权机械臂运动；
- 不因本工作单自动授权夹爪运动；
- 已有 AMR 平移能力可以继续用于 board 多视角/validation，但需遵守现有现场安全边界；
- 机械臂触碰 board（Route A）必须获得用户新的明确授权后才能执行；
- production 外参通过前，不开始真实 A/B 执行。

## Codex 当前优先完成

```text
vendor board detector wrapper
→ same-frame board pose ↔ pointcloud plane consistency
→ Route A/B/C data schema + solver
→ Terminal integration
→ T_body_board / T_body_camera validation tooling
→ known obstacle BODY hold-out check
→ 给出最少现场操作步骤
```

## 禁止事项

- 再用 free 6DoF ICP 作为 production 主 solver；
- 仅凭桌面/桌边猜完整外参；
- 使用 AMR relative command displacement 当毫米级 ground truth；
- 为了 PASS 放宽 calibration gate；
- 使用 DEMO_ONLY `T_body_camera` 获得实机执行许可；
- Skill Library / LLM；
- 实时 GUI / nvblox / MPC 优先于 production extrinsic；
- 新建 `/home/yikun/ARES-R_AUDIT_*` 工作目录。

所有新增代码、配置、日志和 evidence 必须位于 `/home/yikun/ARES-R`。
