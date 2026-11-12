# demo-5 · DMP站：专机放置（下降 60 mm → 松爪）→ 回 center

`demo_id: right_arm_dmp_place_v1`，控制台别名 `demo-5-main-dmpplace`，策略 `dmp_place`。

本 Demo 是从 **demo-4**（`right_arm_sift_dmp_roundtrip_v1`）里把 `dmp_place` 与
`return_center` 两段**原样抽出**的独立单元；**起点就是 DMP 抓取站**：
不含抓取段（pick）、也**不含底盘转场**，全程不发任何底盘指令（`/api/operations/base-move`）。

## 链路

| 阶段 | 内容 | 来源 |
|---|---|---|
| 1 `place` | 5700 抓取配置 ID2 检测 → 预放置点（检测点 + BODY 偏移）→ cuRobo 规划（硬水平 + FAST→QUALITY→QUALITY 重试）→ 下降 60 mm → 松爪并回读确认 | demo-4 `stage_place` 的拷贝 |
| 2 `center` | 回全局 center，`FORCE_RESCAN` 新扫描 + 当次派发，到位后 `check_center`（3 mm / 3°） | demo-4 `stage_center` 的拷贝 |

## 开工自检（每次运行最先做，不满足直接拒绝且不运动）

| 项 | 判据 | 证据文件 |
|---|---|---|
| 站点速度上限 | `config/jaka_mini2_motion.site.json` 的 `max_velocity_rad_s` 必须**正好 0.2 rad/s**（高于=比验收值更快，低于=静默降速，两者都拒绝） | `<run>/site-ceiling.json` |
| 控制器 TCP | `/api/operations/telemetry` 右臂 `tool_id` 必须**等于 3**（tcp3，2026-11-04 起） | `<run>/tool-binding.json` |
| 控制器状态 | `errcode` / `emergency_stop` / `protective_stop` / `drag_mode` / `on_soft_limit` 必须全清 | `<run>/telemetry-before.json` |

期望值在 `parameters.json`：`required_site_max_velocity_rad_s: 0.2`、`required_tool_id: 3`。

## 前提（操作员保证）

- 底盘已停在 **DMP 抓取站**并静止——本 Demo 不发底盘指令，不需要转场；
- 右臂**已持住筛网**（demo-4 抓取结束时的状态，或其它链路完成），下降/松爪前保持夹持；
- 左臂保持当前姿态不动；
- 控制器 `errcode` / 保护停已清零，现场监督与急停可用；
- 5700 抓取配置 ID2 能检测到放置目标（`config/system.json:epic.task_profiles.right_pick`）。

夹爪起始回读会写进 `01-dmp-place/gripper-before-place.json`：`position_raw > 600`
时打印 `payload may not be held` 警告，但**不拦停**（空抓与轻夹的回读相近，不能当判据）。

## 关键约定

- **不动底盘**：`parameters.json` 里没有 `base_transit` 段，脚本也不引用
  `config/manipulation_stations.json`；手臂目标全部是 BODY 系（随当次 5700 检测自洽），
  因此不受 AMR SLAM 位姿漂移影响。
- **预放置点偏移**（`stages.dmp_place.preplace_offset_body_m`）：默认
  `[-0.023, -0.410, 0.100]`，含义是**相对 5700 检测返回点的 BODY 偏移**
  （x 前 / y 左 / z 上，单位米），不是相对当前 TCP：

  ```
  preplace_body = detection_body + offset_body
  place_body    = preplace_body - [0, 0, descent_m]
  ```

  每次运行都会把「检测点 / 偏移 / 预放置点 / 下降点 / 当前 TCP / TCP→预放置点位移」
  写进 `01-dmp-place/preplace-offset.json`（毫米），并在日志里打印一行
  `"state": "PREPLACE_TARGET"`。要改偏移，二选一：
  - 改 `parameters.json:stages.dmp_place.preplace_offset_body_m`（永久）；
  - 或用 `--preplace-offset X Y Z` 单次覆盖（米，BODY 相对检测点）。
- **下降量**（`stages.dmp_place.descent_m`）：默认 **0.060 m**（历史：0.065 实机过深触发碰撞 983092 → 0.060 → 试过 0.070 → 2026-11-09 现场回到 0.060），BODY −Z；
  执行后用 TCP 实测位移复核（±3 mm）。`place = preplace − descent`，所以下降量直接决定放置深度。
- **下降方式**（`stages.dmp_place.descent_mode`，默认 **`CONTROLLER_LINEAR_MOVE`**，
  2026-11-09 现场要求）：预放置到位后**不经过 cuRobo**，直接读控制器实时 TCP，把
  BODY −Z 的 60 mm 换算到控制器基座系（本站 yaw 45°、z 轴竖直，等价于 base z −60 mm），
  用控制器原生 `linear_move`（MoveL）走一条竖直直线——效果与在 JAKA App 里 jog 下去一致。
  速度 `stages.dmp_place.descent_speed_mm_s`（默认 10 mm/s，60 mm 约 6 s）。
  保留的守卫：控制器 errcode/急停/保护停/drag/软限位/碰撞 全清、`tool_id=3`、
  站点速度上限预检（用 IK 估算关节速度）、运动中每 50 ms 轮询（一出现 errcode/碰撞
  立即 `motion_abort()`）、到位后复核位移与横向偏差（`descend_tolerance_m` /
  `descent_lateral_tolerance_mm`）。
  证据：`01-dmp-place/descend.direct-move.json`（起止 TCP、基座系增量、逐次采样、
  实测位移与关节速度）。
  **注意**：这条路径不看观测体素模型。2026-11-09 的 cuRobo 检查曾报落点比
  `observed_support_00_component_01_protruding_obstacle_000` 深 7.93 mm，
  MoveL 会真实压到该位置，控制器碰撞保护可能触发（锁存后需示教器清除）。
  改回规划式下降：`descent_mode: "CUROBO_PLAN"` 或 `--descent-mode CUROBO_PLAN`。
- **松爪后先沿 BODY x− 后退 55 mm**（`stages.dmp_place.post_release_retreat`，
  2026-11-09 加入）：与 demo-3（`right_arm_sift_pick_lift_replace_reset_v1`）的
  `retreat` 段一致 —— 该段是 `validated_reverse_of: contact`，用 FK 从其 native 轨迹
  实测得 BODY x **−54.99 mm**、y/z ≈ 0。本 Demo 用同一个控制器原生 `linear_move`
  走 `[-55, 0, 0] mm`（10 mm/s），再从「已脱离接触」的位姿规划回 center。
  证据：`01-dmp-place/retreat.direct-move.json` + `retreat-check.json`。
  > 2026-11-09 实机教训：松爪后直接规划 center，工具还在槽里，第一段斜向抽出
  > （−y 25 mm、+z 10 mm，用时 3.66 s）触发控制器 `errcode=983092` 碰撞并锁存保护停。
  > 所以"先竖直/侧向退出，再规划"是必须的，不能省。
  > **距离为何是 40 mm 而不是 demo-3 的 55 mm**：本 Demo 的预放置点几何下，x−55 mm 会把
  > j3 从 −112.09° 推到 −128.38°，越过站点软限位下限 −125°（hard −130° 再内缩 5°）；
  > IK 实算 x−55→−128.3（违规）、x−40→−124.0（OK）、x−30→−121.1、z+40→−114.5。
  > 另外 `controller_body_move()` 会在 MoveL 前用 IK 预判目标关节，越软限位时沿同方向
  > **自动缩短行程**（`DISTANCE_CLAMPED` + `clamped_mm`），完全不可行才拒绝。
- **软限位快速失败**：`stage_center` 开工前先做 `soft_limit_report()`；起点任一路关节
  已在 `[lower+soft, upper-soft]` 之外时立即 `START_POSE_OUTSIDE_SOFT_LIMIT` 失败并
  打印关节/允许区间（证据 `02-return-center/start-soft-limit.json`），不再像 2026-11-09
  那样 FAST+QUALITY+QUALITY 三次尝试白等 ~170 s 后才报同一句 `ValueError: site soft joint limit`。
- **起点倾斜门**（`platform.level_tolerance_deg`，默认 **5.0°**，2026-11-09 由 4.5° 放宽）：水平门限量的是**整条路径
  （含起点）**。若手臂当前 TCP 本来就倾斜超过 5.0°，任何规划都会以同一原因被拒——
  脚本会**在开工前直接拒绝**（`START_POSE_NOT_LEVEL`，见 `01-dmp-place/start-tilt.json`），
  不会再白跑多轮。处理：先调平（例如跑 demo-0 回 center，或示教器调平），
  确需带倾斜起步时用 `--level-tolerance <度>` 显式放宽。
- **进度输出**：每进入一个阶段打印一行 JSON（`stage` / `phase` / `prepare_elapsed_s` /
  `planning_elapsed_s` / `total_elapsed_s`），阻塞等待（规划、原生执行）时每 5 s 打一行
  心跳；控制台的「当前阶段」与「准备/规划累计」就来自这些行。
- **同因重复轮次早停**：同一场景快照下 cuRobo 对同一请求是确定性的，整轮被同一原因拒掉时
  不再跑下一轮（`rounds-skipped.json`），避免 3 轮 × 3 模式 ≈ 150 s 的无效等待。
- **下降必须是“可用的竖直线”**（现为**关闭**的精门限）：下降段规划后逐个采样点 FK，算出
  `lateral_max_mm`（TCP 横向偏移）与 `z_min_below_goal_mm`（中途最低 z 相对目标），阈值取
  `platform.descent_lateral_tolerance_mm`（20 mm）/ `platform.descent_min_z_above_goal_mm`（−2 mm）。
  **2026-11-09 现场要求取消硬门限**：`platform.descent_axis_gate_enabled = false` 时指标仍写入
  `<label>.descent-axis.json` 并在超标时打印 WARNING，但**不再拒绝派发**。
  > 2026-11-09 实机教训：豁免掉“误检体素”后，cuRobo 规划出一条横向 263 mm、中途比目标 z 低 8 mm 的
  > 绕行路径，旧逻辑只告警就放行，执行 3.3 s 后控制器报 `errcode=983092`（`collision=1`）并锁存保护停。
- **落点穿透豁免**（`stages.dmp_place.goal_collision_waiver`，**默认关闭**）：现场确认某些体素为误检时用。
  当规划返回 `INVALID_GOAL_COLLISION`，脚本从干涉表里提取**实际穿透**的对象，若它们全部
  匹配 `allowed_prefixes` 且穿透深度 ≤ `max_penetration_mm`（默认 10 mm），则把这些对象放进
  `ignore_cuboid_ids`（规划器本来的机制）重规划同一段，并写
  `01-dmp-place/goal-collision-waiver-<label>.json`（对象名 + 穿透量 + 操作员批准记录）。
  任一对象不匹配前缀或超深，就整次不豁免（fail-closed）；豁免只对本次运行的后续腿生效。
  **2026-11-09 已关闭**：当日豁免后规划出绕行路径、控制器碰撞（983092）并锁存保护停，
  说明这些体素不是完全误检；重新开启前先看 `platform.descent_*` 门限与现场几何。
- **起点穿透豁免**（`stages.dmp_place.start_collision_waiver`，**默认开启**）：
  规划第一步会做起点自检（`clearance_details([start])`，任一对象净空 ≤ 0 即
  `INVALID_START_COLLISION`，此时一条轨迹都不会生成）。2026-11-09 实机遇到
  `observed_remaining_observed_unknown_occupied_000` 穿透 3.1 mm 导致 6 次尝试全拒。
  开启豁免后：解析该平表（对象名 → 签名净空），只把**实际穿透**且前缀在
  `allowed_prefixes`、深度 ≤ `max_penetration_mm`（默认 5 mm）的对象放进
  `ignore_cuboid_ids` 重规划同一段；任一对象越界仍整次不豁免（fail-closed）。
  证据：`01-dmp-place/start-collision-<label>.json`（穿透明细 + 建议）与
  `start-collision-waiver-<label>.json`（被排除的对象 + 策略）。
  注意：被排除的对象在**整条路径**上都不再检查，只对现场确认过的误检体素开启。
- **已在预放置点则不重跑**（`stages.dmp_place.skip_preplace_within_tolerance_m`，默认 5 mm）：
  当前 TCP 已在预放置点 ±5 mm 内时直接规划下降段，避免目标窗口里的腕部自观测残影
  （`INVALID_GOAL_COLLISION`）导致预放置段无法重规划。
- **偏航**：默认保持下发现场的 TCP yaw；`--yaw-deg` 可强行修正（末端 yaw 由
  `validate_level_path final_yaw_rad` 校验）。
- **硬水平门限**：`platform.level_tolerance_deg = 5.0`；超限自动换模式并多轮重试
  （`platform.planning_rounds`）。2026-11-09 的 60 mm 下降段实测 `max_level_error_deg = 4.684°`，
  因此把门限从 4.5° 放到 5.0°；该值仍是 fail-closed 的硬门（不是告警）。
- **场景策略**：放置段 `AUTO_FRESH`，回 center 段 `FORCE_RESCAN`。
- **持物碰撞体**：默认不下发（`attach_payload_collision: false`）。若要开，必须带
  `point_ownership`，否则场景构建 fail-closed（`ATTACHMENT_OWNERSHIP_TEMPLATE_REQUIRED`）。
- **授权短语**：CLI 用 `RIGHT DMP PLACE`（`parameters.json:authorization_phrase`）；
  下发到 `/api/operations/execute` 的仍是 `RIGHT SCENE_AWARE SUPERVISED`
  （canonical_backend 只认这一句），两者不要混用。

## 运行

```bash
# 干跑（只做自检 + 检测 + 规划，不动任何轴）
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stage all

# 实机（现场确认必填）—— 与控制台卡片同一条命令
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --stage all --execute --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 单段 / 组合
#   all / place_center = 放置（预放置 + 下降 60 mm + 松爪）+ 回 center
#   place              = 只做放置；可加 --stop-after preplace|descend|release 分段确认
#   center             = 只回 center
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stage place --stop-after preplace --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stage center --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 停止
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stop
```

不传 `--output` 时证据落在
`worklog/evidence/demo-runs/right_arm_dmp_place_v1/run_<timestamp_ns>/`；
控制台验收要求 `last-run.json` 的 `result == PLACE_CENTER_COMPLETE`
（单段时为 `AT_PREPLACE` / `AT_DESCENT` / `PLACED_AND_RELEASED` / `AT_CENTER`）。

## 安全约束（代码强制）

1. 必须 `--execute` **且** `--authorization 'RIGHT DMP PLACE'` **且**
   `--onsite-observer-confirmed`；
2. 每个输出目录每段只能派发一次（`<label>.dispatched-once.json` 在派发**前**写入）；
3. 控制器 `errcode` / `emergency_stop` / `protective_stop` / `drag_mode` /
   `on_soft_limit` 未清零时拒绝任何运动；
4. 站点速度上限不是 0.2 rad/s 时拒绝（高于/低于都拒绝）；控制器 `tool_id` 不是 3 时拒绝；
5. 每次规划尝试都要求 `base_pose_revision` 不变，否则目标作废；
6. 目标碰撞用**当次最新扫描**判定（`INVALID_START_COLLISION` / `INVALID_GOAL_COLLISION`
   会中止而不是绕过）；
7. 松爪前必须确认到位（预放置点 ±5 mm、下降位移 ±3 mm）；
8. 不清除任何控制器错误/保护停——人工确认后重跑；
9. 左臂（非作业臂）在放置段执行前后做关节/工具一致性检查；
10. 全程不发底盘指令（无 `base-move`），因此不受 AMR SLAM 漂移影响；若底盘需要换站，请先用 demo-4 或运营脚本完成转场。

## 证据

```
01-dmp-place/     gripper-before-place.json, detection.json, preplace-offset.json,
                  place-contract.json, start-tilt.json, preplace_r*/descend_r* 的
                  attempt/level/axis-proof/plan_handle, plans.json,
                  planned-tool-binding.json, preplace-arrival.json | preplace-skipped.json,
                  descent-check.json, stop-after-*.json, release.json,
                  goal-collision.json | goal-collision-waiver-<label>.json,
                  <label>.telemetry-dispatch.json / .execute-request.json / .result.json,
                  retry-<label>-1/（仅命中已知零运动瞬态时）
02-return-center/ center-goal.json, center_r1.*, center-check.json
site-ceiling.json, tool-binding.json, telemetry-before.json,
dry-run.json | demo-run.json, summary.json, result.json, last-run.json
```

## 已知限制

- 「place + center」组合尚未做过实机端到端验收
  （`commissioning_state: CANDIDATE_UNVERIFIED_PLACE_CENTER`）；
  DMP 放置沿自 demo-4 / 2026-11-02 的实现，回 center 沿自 demo-0/demo-4 的合同。
- 5700 检测点会漂移（同工位不同批次 ±10 mm 量级），预放置点始终按当次检测计算。
- 底盘必须由操作员事先停在 DMP 站：本 Demo 不校验也不修正底盘位置；
  AMR 上报位姿不跟手推（无轮速事件、日志停在上次运动），也不要用它当挪车基准。
- 腕部自观测残影（`observed_remaining_observed_unknown_occupied_*`）偶尔会让**目标位姿**
  被判碰撞（`INVALID_GOAL_COLLISION`，典型穿透 0.5–3 mm）：已在预放置点时会被
  `skip_preplace_within_tolerance_m` 跳过；否则先把手臂抬开 30–60 mm 再重规划。
- 控制器瞬态 `errcode=4128769`（派发瞬间 servo 激活前被拒，**0 采样、无运动**）：本 Demo
  已内置与 demo-0 同款的**单次自动重试**，但四条必须同时成立——FAULT 且原因含
  `errcode=4128769`、原生 0 采样、控制器现在全清、关节与派发前相差 ≤0.2°。命中时在
  `<run>/retry-<label>-1/` 重新扫描、重新规划、再派发一次（`retry-reason.json` 记录原因）；
  其它任何失败一律直接上抛，不重试。
