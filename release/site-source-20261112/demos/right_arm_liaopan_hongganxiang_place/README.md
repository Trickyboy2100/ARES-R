# demo-2 · 料盘放置烘干箱专机：预放置(泊位上方 30 mm, yaw 0) → 下降 30 mm 到 lower_middle 泊位 → 回 center

`demo_id: right_arm_liaopan_hongganxiang_place`，控制台别名 `demo-2-liaopan-placeto-hongganxiang`，策略 `dmp_place`。

本 Demo 是 **demo-6**（`right_arm_liaopan_dmp_place_v1`）的**参数级拷贝**：
起点同样是「已在放置站位、已持料盘、底盘不动」，脚本与 demo-5/6 完全共用
（`scripts/run_dmp_place_demo.py`，用 `--demo-id` 选择参数与证据目录），差异全部在
`parameters.json`：

| 项 | demo-6（DMP 专机） | 本 Demo（烘干箱 hongganxiang） |
|---|---|---|
| 5700 检测配置 | ID2（`right_pick`，`320,2,2,1,1,0`） | **ID3**（`right_place_rightmost`，`320,2,3,1,1,0`） |
| 放置点 | 预放置点下方 20 mm（≈ 检测点 y+5 mm） | **控制台泊位注册表 `lower_middle` · CANDIDATE** |
| 预放置点 | 检测点 + `[0, 0.005, 0.020]` m | **放置点 + BODY z 30 mm** |
| 下降量 | 20 mm | **30 mm** |
| 末端 yaw | 0° | 同（不变） |
| 下降方式 | 控制器原生 MoveL | 同（不变） |
| 规划姿态 | `TERMINAL_EXPLICIT`（只约束终点） | **`EXPLICIT` + `hard_level_manifold`（全程水平流形种子）** |
| 误检体素 | 碰撞后整族 prefix 排除 + 落点豁免 | 同（参数沿用，需现场复核） |
| 回 center | 3 mm / 3° | 同（不变） |

```
place_body     = detection_body + [0.070, -0.315, 0.273]     # BODY，来自 lower_middle 泊位偏置（revision 21）
preplace_body  = place_body    + [0, 0, 0.030]               # 相对检测点 = [0.070, -0.315, 0.303]
descent_m      = 0.030
```

## 泊位偏置从哪来（相对检测返回点）

控制台「烘干箱泊位注册表」里 `lower_middle` 是 **CANDIDATE**，内部按**检测坐标系 D** 保存。
2026-11-11 15:20 现场把 **检测 Y** 从 −0.238 改为 −0.273、**检测 Z** 从 0.060 改为 0.070
（revision 21）：

| 表达 | 值 |
|---|---|
| DETECTION 偏置 | `[0.315, -0.273, 0.070, 0, 0, 0]` m/rad |
| 换算（控制台同一公式） | `BODY = [det_Z, −det_X, −det_Y]`，`R_BODY_DETECTION = [[0,0,1],[-1,0,0],[0,-1,0]]` |
| BODY 偏置（相对 ID3 检测返回点） | **`[0.070, -0.315, 0.273]` m = `[+70, −315, +273]` mm** |
| 预放置点相对检测点 | `[0.070, -0.315, 0.303]` m（再 +30 mm z） |

> **轴映射（现场容易改错）**：检测 **Y 更负 = BODY 更高**；检测 **Z 变大 = BODY 更靠前**（不是变高）。
> 想把泊位抬高 10 mm，应改检测 Y（−0.238 → −0.248），不是检测 Z。

用 2026-11-11 15:06 的检测点 `[617.3, 207.2, 669.4]` mm 与 revision 21 复算：
`place = [687.3, -107.8, 942.4]` mm，`preplace = [687.3, -107.8, 972.4]` mm。yaw 0 下
place j3 = −26.8°（σ_min 0.0383）、preplace j3 = −43.7°（σ_min 0.0619），30 mm 下降从
j3 −43.7° 到 −26.8°，不再穿过肘奇异面。

> 历史教训（旧值 `[0.315,-0.238,0.060]` → BODY `[60,-315,238]` mm）：30 mm 下降被 IK 裁到
> 24 mm，24 mm 解落在 **j3≈0 的肘奇异面**（σ_min 0.0001、条件数 13600），控制器
> `linear_move` 接受命令但运动不启动（0 采样）。调整高度后才恢复。

> ⚠️ 注册表偏置是 CANDIDATE，可能被现场重新标定。代码运行时不读注册表，只用
> `parameters.json:stages.dmp_place.preplace_offset_body_m` 的固定值；若注册表
> `offset_m_rad` 或 revision 变化，必须重算并更新参数（当前记录 revision 21，
> 预放置 BODY 偏置 `[0.070,-0.315,0.303]`）。

## 链路

| 阶段 | 内容 |
|---|---|
| 1 `place` | 5700 抓取配置 **ID3** 检测 → 预放置点（泊位上方 30 mm，末端 yaw=0）→ cuRobo 规划（`EXPLICIT` + 水平流形种子、硬水平 5° + FAST→QUALITY→QUALITY 多轮；误检鬼影体素按家族排除）→ 到位复核（±5 mm）→ **控制器原生 MoveL 下降 30 mm**（不经过 cuRobo）→ 位移复核（±3 mm）→ 松爪回读确认 → 沿 BODY x− 后退 40 mm |
| 2 `center` | 回全局 center，`FORCE_RESCAN` 新扫描 + 当次派发，到位后 `check_center`（3 mm / 3°） |

## 开工自检（每次运行最先做，不满足直接拒绝且不运动）

| 项 | 判据 | 证据文件 |
|---|---|---|
| 站点速度上限 | `config/jaka_mini2_motion.site.json` 的 `max_velocity_rad_s` 必须**正好 0.2 rad/s** | `<run>/site-ceiling.json` |
| 控制器 TCP | `/api/operations/telemetry` 右臂 `tool_id` 必须**等于 3**（tcp3） | `<run>/tool-binding.json` |
| 控制器状态 | `errcode` / `emergency_stop` / `protective_stop` / `drag_mode` / `on_soft_limit` 全清 | `<run>/telemetry-before.json` |
| 起点水平 | 起点 TCP 倾斜 ≤ `platform.level_tolerance_deg`（5.0°），否则 `START_POSE_NOT_LEVEL` | `01-dmp-place/start-tilt.json` |

期望值在 `parameters.json`：`required_site_max_velocity_rad_s: 0.2`、`required_tool_id: 3`。

## 前提（操作员保证）

- 底盘已停在**烘干箱放置站位**（`config/manipulation_stations.json` 的 `PLACE_STATION`）并静止——本 Demo 不发底盘指令；
- 右臂**已持住料盘**（此前链路完成抓取/抬升/转场），规划与松爪前保持夹持；
- 左臂保持当前姿态不动；控制器 `errcode` / 保护停已清零，现场监督与急停可用；
- 5700 抓取配置 **ID3** 能检测到烘干箱泊位参考点；目标泊位 `lower_middle` 已清空并在控制台确认。

夹爪起始回读写进 `01-dmp-place/gripper-before-place.json`：`position_raw > 600` 时打印
`payload may not be held` 警告，但**不拦停**（空抓与轻夹回读相近，不能当判据）。

## 全程水平规划（本 Demo 与 demo-6 的关键差异，2026-11-11 现场要求）

`stages.dmp_place.hard_level_manifold` 打开后，放置腿的 `/api/motion/plan` 请求从
`TERMINAL_EXPLICIT`（只约束终点姿态）改为 **`EXPLICIT` + `hard_level_manifold`**：

- `explicit_rotation` = 起点最近水平 roll 分支 + yaw 0，作为**整条路径**的姿态目标参与优化；
- worker 用 `build_level_manifold_seeds()` 从起点到预放置点沿水平流形生成连续 IK 种子
  （`ik_samples=25`），并把这些种子作为唯一 goal 候选；
- 规划完成后**仍**用 `validate_level_path`（5° 硬门限、yaw 0）逐点复核 + 同因早停，
  流形只是让求解器一开始就沿水平路径走，不替代独立校验。

为什么必须开：2026-11-11 同目标连续 4 次规划（FAST 13.04°/12.17°，QUALITY 7.87°/7.58°）
全部被事后 5° 门限拒，QUALITY 单次 43–84 s，240 s 内没有任何运动。当时请求里
`orientation_lock=null`、`hard_level_manifold=null`，中途姿态完全不受约束。

## 误检体素处理（沿用 demo-6，需现场复核）

demo-6 在 DMP 台面场景确认过的两个策略，本 Demo 原样继承：

```json
"false_positive_voxels": {
  "enabled": true,
  "site_reconfirmation_required": true,
  "allowed_prefixes": [
    "observed_support_00_component_",
    "observed_support_01_support_surface",
    "observed_remaining_observed_unknown_occupied_"
  ]
},
"goal_collision_waiver": { "enabled": true, "max_penetration_mm": 20.0,
  "site_reconfirmation_required": true, "allowed_prefixes": [ "（同上三项）" ] }
```

- **`false_positive_voxels`（碰撞后整族排除）**：遇到 `INVALID_GOAL_COLLISION` 时，从**当次真实请求的净空表**
  里把所有白名单前缀命名的对象一次性放进 `ignore_cuboid_ids` 重规划同一段。
  名字不是猜的，也不是写死的清单；worker 对未知名字 fail-closed。
  **不做规划前预排除**：只有真出现碰撞错误时才排除，避免把真实障碍提前删掉。
  证据：`01-dmp-place/false-positive-voxels-preplace.json`。
- **`goal_collision_waiver`（落点穿透豁免）**：第二层网，只豁免“实际穿透目标位姿”且深度 ≤ 20 mm 的对象。
  证据：`goal-collision-waiver-preplace.json`；越界写 `goal-collision-waiver-rejected-preplace.json` 并中止。
- 白名单**只**到这三个家族，**不要**扩到 `observed_support_` / `observed_remaining_structure_` /
  `known_support_table` / 机器人自身链路（2026-11-09 曾用更宽豁免，cuRobo 绕行 263 mm 并实机撞结构，
  `errcode=983092` 保护停）。5° 水平硬门限与同因早停一直保留。
- **2026-11-11 更正**：之前把限制路径的 `observed_support_01_component_01_protruding_obstacle_051`
  当成误检并要求“规划前整族排除”，是现场看错了——**它不是误检**。该家族已从白名单删除，
  `preemptive_prefixes` / `ignore_cuboid_prefixes` 机制也已回退；实际存在的障碍照旧 fail-closed。

## 关键约定

- **不动底盘**：没有 `base_transit` 段，脚本不引用 `config/manipulation_stations.json`；
  手臂目标全是 BODY 系（随当次 5700 ID3 检测自洽），不受 AMR SLAM 漂移影响。
- **预放置点 / 下降**：`preplace_offset_body_m = [0.070, -0.315, 0.303]`、`descent_m = 0.03`。
  每次运行把「检测点 / 偏移 / 预放置点 / 落点 / 当前 TCP → 预放置点位移」写进
  `01-dmp-place/preplace-offset.json`，并打印 `"state": "PREPLACE_TARGET"`。
  单次覆盖：`--preplace-offset X Y Z`（米，BODY 相对检测点）、`--descent-m`。
- **下降方式** `CONTROLLER_LINEAR_MOVE`：读控制器实时 TCP，把 BODY −Z 的 30 mm 换算到
  控制器基座系，用原生 `linear_move`（MoveL）走直线，30 mm 约 3 s（`descent_speed_mm_s = 10`）。
  **这条路径不看观测体素模型**；保存的守卫：控制器 errcode/急停/保护停/drag/软限位/碰撞全清、
  `tool_id=3`、站点速度上限预检、运动中每 50 ms 轮询（出碰撞立即 `motion_abort`）、
  到位后复核位移（±3 mm）与横向偏差（`descent_lateral_tolerance_mm`）。
- **硬水平门限**：`platform.level_tolerance_deg = 5.0`，量的是**整条路径（含起点）**，fail-closed。
  本 Demo 另开 `hard_level_manifold`，把水平姿态提前交给规划器（不只是事后校验）；
  实际下发的 manifold 选项写在 `01-dmp-place/place-contract.json:hard_level_manifold`。
- **起终点穿透豁免**（`start_collision_waiver`，默认开启）：只豁免实际穿透、前缀在白名单、
  深度 ≤ 5 mm 的观测体素；越界整次不豁免。
- **松爪后先沿 BODY x− 后退 40 mm**（`post_release_retreat`）：烘干箱泊位离机器人更远
  （BODY y −315 mm），关节余量需在首次分段运行时复核；越软限位时 `controller_body_move()`
  会沿同方向自动缩短（`DISTANCE_CLAMPED`）。
- **进度输出**：每阶段一行 JSON（`stage` / `phase` / `prepare_elapsed_s` / `planning_elapsed_s` /
  `total_elapsed_s`），阻塞时每 5 s 心跳；控制台的「当前阶段」「准备/规划累计」来自这些行。
- **同因重复轮次早停**：同一场景快照下 cuRobo 对同一请求是确定性的，整轮被同一原因拒掉时
  不再跑下一轮（`rounds-skipped.json`）。
- **场景策略**：放置段 `AUTO_FRESH`，回 center 段 `FORCE_RESCAN`。
- **持物碰撞体**：默认不下发（`attach_payload_collision: false`）；若要开必须带 `point_ownership`。
- **授权短语**：CLI 用 `RIGHT DMP PLACE`（与 demo-5/6 相同，因为控制台 `dmp_place` 策略共用同一条
  子进程命令）；下发到 `/api/operations/execute` 的仍是 `RIGHT SCENE_AWARE SUPERVISED`。

## 运行

```bash
# 干跑（只做自检 + 检测 + 规划，不动任何轴）——第一次务必先跑这条核对落点
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_hongganxiang_place --stage all

# 实机（现场确认必填）——与控制台卡片同一条命令
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_hongganxiang_place --stage all --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 分段确认：只到预放置点 / 只到下降到底（夹爪不松）
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_hongganxiang_place --stage place --stop-after preplace --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_hongganxiang_place --stage place --stop-after descend --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 只回 center  /  停止
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_hongganxiang_place --stage center --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stop
```

不传 `--output` 时证据落在
`worklog/evidence/demo-runs/right_arm_liaopan_hongganxiang_place/run_<timestamp_ns>/`；
控制台验收要求 `last-run.json` 的 `result == PLACE_CENTER_COMPLETE`
（单段时为 `AT_PREPLACE` / `AT_DESCENT` / `PLACED_AND_RELEASED` / `AT_CENTER`）。

## 安全约束（代码强制）

1. 必须 `--execute` **且** `--authorization 'RIGHT DMP PLACE'` **且** `--onsite-observer-confirmed`；
2. 每个输出目录每段只能派发一次（`<label>.dispatched-once.json` 在派发**前**写入）；
3. 控制器 `errcode` / `emergency_stop` / `protective_stop` / `drag_mode` / `on_soft_limit`
   未清零时拒绝任何运动；
4. 站点速度上限不是 0.2 rad/s 时拒绝（高于/低于都拒绝）；控制器 `tool_id` 不是 3 时拒绝；
5. 每次规划尝试都要求 `base_pose_revision` 不变，否则目标作废；
6. 目标碰撞用**当次最新扫描**判定；豁免只覆盖白名单内的实际穿透对象，其余一律中止；
7. 松爪前必须确认到位（预放置点 ±5 mm、下降位移 ±3 mm）；
8. 不清除任何控制器错误/保护停——人工确认后重跑；
9. 左臂（非作业臂）在放置段执行前后做关节/工具一致性检查；
10. 全程不发底盘指令（无 `base-move`），因此不受 AMR SLAM 漂移影响。

## 证据

```
01-dmp-place/     gripper-before-place.json, detection.json, preplace-offset.json,
                  place-contract.json, start-tilt.json,
                  preplace_r*/ 的 attempt/level/axis-proof/plan_handle, plans.json,
                  planned-tool-binding.json, preplace-arrival.json | preplace-skipped.json,
                  goal-collision.json | goal-collision-waiver-preplace.json,
                  descent.direct-move.json, descent-check.json,
                  stop-after-preplace.json | stop-after-descend.json,
                  release.json, retreat.direct-move.json, retreat-check.json,
                  <label>.telemetry-dispatch.json / .execute-request.json / .result.json,
                  retry-preplace-1/ | retry-descend-1/（仅命中已知零运动瞬态时）
02-return-center/ center-goal.json, center_r1.*, center-check.json
site-ceiling.json, tool-binding.json, telemetry-before.json,
dry-run.json | demo-run.json, summary.json, result.json, last-run.json
```

> 证据目录名 `01-dmp-place` / `02-return-center` 沿用共享脚本的固定布局（脚本对
> `--demo-id` 只切换参数与证据根目录，不改段内子目录名）；本 Demo 的 `01-dmp-place`
> 实际是「烘干箱放置」段。
