# demo-6 · 料盘放置除尘收料专机：预放置(检测点 y+5 mm, yaw 0) → 下降 10 mm → 回 center

`demo_id: right_arm_liaopan_dmp_place_v1`，控制台别名 `demo-6-liaopan-placetoDMP`，策略 `dmp_place`。

本 Demo 是 **demo-5**（`right_arm_dmp_place_v1`）的**料盘专机拷贝**：
起点同样是 DMP 抓取站、同样**不含抓取段与底盘转场**（全程不发 `/api/operations/base-move`），
脚本与 demo-5 共用，差异全部在 `parameters.json`：

| 项 | demo-5 | demo-6（本 Demo） |
|---|---|---|
| 预放置点 | 检测点 + `[-0.023, -0.410, 0.100]` m | **检测点 + BODY y+5 mm**（x/z 不偏移） |
| 末端 yaw | 保持当前 TCP yaw | **固定 0°**（`yaw_target_deg = 0.0`） |
| 下降量 | 60 mm | **10 mm**（`place = preplace − 10 mm`，不再等于检测点） |
| 下降方式 | 控制器原生 MoveL | 同（不变） |
| 误检体素 | 无策略（fail-closed） | **整族按前缀排除 + 落点豁免**（现场确认） |
| 夹持物 | 筛网 | **料盘** |

```
preplace_body = detection_body + [0, 0.005, 0]
place_body    = preplace_body - [0, 0, 0.010]      # 与检测点无关
```

实现上**与 demo-5 共用一个脚本** `scripts/run_dmp_place_demo.py`，
本 Demo 通过 `--demo-id right_arm_liaopan_dmp_place_v1` 选择自己的 `parameters.json`
与证据目录；代码里没有 demo 分支，差异只由参数驱动
（`plan_direct_to_place` 的「单腿直放」分支也保留在代码里，当前为 `false`）。

## 链路

| 阶段 | 内容 |
|---|---|
| 1 `place` | 5700 抓取配置 ID2 检测 → 预放置点（检测点 y+5 mm，末端 yaw=0）→ cuRobo 规划（硬水平 5° + FAST→QUALITY→QUALITY 多轮；已确认误检的鬼影体素整族排除）→ 到位复核（±5 mm）→ **控制器原生 MoveL 下降 10 mm**（不经过 cuRobo）→ 位移复核（±3 mm）→ 松爪回读确认 → 沿 BODY x− 后退 40 mm |
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

- 底盘已停在 **DMP 抓取站**并静止——本 Demo 不发底盘指令；
- 右臂**已持住料盘**（此前链路完成抓取/抬升），规划与松爪前保持夹持；
- 左臂保持当前姿态不动；控制器 `errcode` / 保护停已清零，现场监督与急停可用；
- 5700 抓取配置 ID2 能检测到放置目标。

夹爪起始回读写进 `01-dmp-place/gripper-before-place.json`：`position_raw > 600` 时打印
`payload may not be held` 警告，但**不拦停**（空抓与轻夹回读相近，不能当判据）。

## 落点体素豁免与误检家族（本 Demo 的关键差异，2026-11-09 现场确认）

检测点作为落点时，cuRobo 会报 `INVALID_GOAL_COLLISION`；把落点抬到检测点上方 20 mm 后
仍然穿透同一个凸起体素 16.8 mm。现场确认这些体素是**误检**，因此开启
`stages.dmp_place.goal_collision_waiver`：

## 误检体素处理（本 Demo 的关键差异，2026-11-09 现场确认）

检测点作为落点时 cuRobo 报 `INVALID_GOAL_COLLISION`（穿透 16.8 mm）；实测更麻烦的是：
**只豁免“落点穿透的那几个”不够** —— 鬼影簇每次扫描重新编号，落点穿透的是
`observed_support_00_component_01`，而限住**路径**的是同族 `component_02`（净空 1.3 mm），
cuRobo 只能绕 244 mm，中段末端倒倒 **17°**，被 5° 水平门限拒（这就是 2026-11-09
第一次实机/干跑失败的原因）。

所以参数里开了两层，都是 fail-closed：

```json
"false_positive_voxels": {
  "enabled": true,
  "allowed_prefixes": [
    "observed_support_00_component_",
    "observed_support_01_support_surface",
    "observed_remaining_observed_unknown_occupied_"
  ]
},
"goal_collision_waiver": { "enabled": true, "max_penetration_mm": 20.0,
  "allowed_prefixes": [ "（同上三项）" ] }
```

- **`false_positive_voxels`（整族排除）**：遇到 `INVALID_GOAL_COLLISION` 时，从**当次真实请求的净空表**
  里把所有白名单前缀命名的对象一次性放进 `ignore_cuboid_ids` 重规划同一段（实测一次排除 205–214 个）。
  名字不是猜的，也不是写死的清单；worker 对未知名字 fail-closed。证据：
  `01-dmp-place/false-positive-voxels-preplace.json`。
- **`goal_collision_waiver`（落点穿透豁免）**：保留作为第二层网，只豁免“实际穿透目标位姿”
  且深度 ≤ 20 mm 的对象。证据：`goal-collision-waiver-preplace.json`；若对象不在白名单/超深，
  写 `goal-collision-waiver-rejected-preplace.json` 并打印具体对象与原因（上一版失败时就靠它定位到
  `component_00` vs `component_01` 的编号漂移）。

白名单**只**到这三个家族，**不要**扩到 `observed_support_` / `observed_remaining_structure_` /
`known_support_table` / 机器人自身链路：那样会把真实结构也从碰撞世界里去掉
（2026-11-09 曾用更宽的豁免，结果 cuRobo 规划出横向 263 mm 的绕行路径，实机撞到结构并锁存保护停 `errcode=983092`）。
5° 水平硬门限与同因早停也一直保留。

**干跑实测量（2026-11-09，仅检测+规划、未派发；中间还强制 invalidate 场景重扫一次）**：

| 项 | 值 |
|---|---|
| 首次 FAST 尝试 | **直接可用（6.1–6.3 s）**，无需 QUALITY |
| 整段准备+规划 | 12.6 s / 19.3 s（含检测 3.2 s、场景刷新） |
| 规划路径长度 / 直距 / 比值 | 0.175 m / 0.173 m / **1.01**（几乎直线） |
| 路径最大偏离直线 | 36 mm（失败时为 228–244 mm） |
| 水平门限 | `max_level_error_deg = 2.42°`（门限 5.0°，通过） |
| 限制对象 | 已变成真实结构 `observed_remaining_structure_structure_007` |

## 关键约定

- **不动底盘**：没有 `base_transit` 段，脚本不引用 `config/manipulation_stations.json`；
  手臂目标全是 BODY 系（随当次 5700 检测自洽），不受 AMR SLAM 漂移影响。
- **预放置点 / 下降**：`preplace_offset_body_m = [0,0,0.02]`、`descent_m = 0.02`，
  二者必须相等，否则落点会离开检测点。每次运行把「检测点 / 偏移 / 预放置点 / 落点 /
  当前 TCP → 预放置点位移」写进 `01-dmp-place/preplace-offset.json`，并打印 `"state": "PREPLACE_TARGET"`。
  单次覆盖：`--preplace-offset X Y Z`（米，BODY 相对检测点）、`--descent-m`。
- **下降方式** `CONTROLLER_LINEAR_MOVE`：读控制器实时 TCP，把 BODY −Z 的 20 mm 换算到
  控制器基座系，用原生 `linear_move`（MoveL）走直线（等同 JAKA App 里 jog 下去），
  20 mm 约 2 s（`descent_speed_mm_s = 10`）。**这条路径不看观测体素模型**，MoveL 会真实压到
  目标位置；保留的守卫：控制器 errcode/急停/保护停/drag/软限位/碰撞全清、`tool_id=3`、
  站点速度上限预检（IK 估速）、运动中每 50 ms 轮询（出碰撞立即 `motion_abort`）、
  到位后复核位移（±3 mm）与横向偏差（`descent_lateral_tolerance_mm`）。
- **硬水平门限**：`platform.level_tolerance_deg = 5.0`，量的是**整条路径（含起点）**，fail-closed。
- **起终点穿透豁免**（`start_collision_waiver`，默认开启）：只豁免实际穿透、前缀在白名单、
  深度 ≤ 5 mm 的观测体素；越界整次不豁免。
- **松爪后先沿 BODY x− 后退 40 mm**（`post_release_retreat`）：松爪后直接从槽内斜着抽出会
  卡住结构（2026-11-09 demo-5 实测 `errcode=983092` 碰撞并锁存保护停）。
  `controller_body_move()` 会用 IK 预判目标关节，越软限位时沿同方向自动缩短（`DISTANCE_CLAMPED`）。
- **进度输出**：每阶段一行 JSON（`stage` / `phase` / `prepare_elapsed_s` / `planning_elapsed_s` /
  `total_elapsed_s`），阻塞时每 5 s 心跳；控制台的「当前阶段」「准备/规划累计」来自这些行。
- **同因重复轮次早停**：同一场景快照下 cuRobo 对同一请求是确定性的，整轮被同一原因拒掉时
  不再跑下一轮（`rounds-skipped.json`）。
- **场景策略**：放置段 `AUTO_FRESH`，回 center 段 `FORCE_RESCAN`。
- **持物碰撞体**：默认不下发（`attach_payload_collision: false`）；若要开必须带 `point_ownership`。
- **授权短语**：CLI 用 `RIGHT DMP PLACE`（与 demo-5 相同）；下发到 `/api/operations/execute`
  的仍是 `RIGHT SCENE_AWARE SUPERVISED`（canonical_backend 只认这一句）。

## 运行

```bash
# 干跑（只做自检 + 检测 + 规划，不动任何轴）
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_dmp_place_v1 --stage all

# 实机（现场确认必填）—— 与控制台卡片同一条命令
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_dmp_place_v1 --stage all --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 分段确认：只到预放置点 / 只到下降到底（夹爪不松）
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_dmp_place_v1 --stage place --stop-after preplace --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_dmp_place_v1 --stage place --stop-after descend --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed

# 只回 center  /  停止
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py \
  --demo-id right_arm_liaopan_dmp_place_v1 --stage center --execute \
  --authorization 'RIGHT DMP PLACE' --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_dmp_place_demo.py --stop
```

不传 `--output` 时证据落在
`worklog/evidence/demo-runs/right_arm_liaopan_dmp_place_v1/run_<timestamp_ns>/`；
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

## 已知限制

- 本 Demo 只做过**干跑**（检测 + 规划 + 门限校验），**尚未实机运行**
  （`commissioning_state: CANDIDATE_UNVERIFIED_PLACE_CENTER`）。第一次实机建议先
  `--stage place --stop-after preplace` 确认预放置位姿，再放行 20 mm 下降。
- 下降 20 mm 是**物理放置深度**，由料盘/工装高度决定；换夹具后需重新标定。
- 落点豁免依赖现场确认的 3 类误检对象；若 5700/body 相机视野变化导致出现新的穿透对象，
  豁免会整次失效（fail-closed）——这是有意的。
- 5700 检测点会漂移（同工位不同批次 ±10 mm 量级），预放置点始终按当次检测计算。
- 底盘必须由操作员事先停在 DMP 站：本 Demo 不校验也不修正底盘位置。
- 控制器瞬态 `errcode=4128769`（派发瞬间 servo 激活前被拒，**0 采样、无运动**）：内置
  与 demo-0/demo-5 同款的**单次自动重试**（FAULT + 含 `errcode=4128769` + 0 采样 +
  控制器全清 + 关节差 ≤0.2° 四条同时成立），命中时在 `<run>/retry-<label>-1/`
  重新规划派发一次；其它失败一律直接上抛。
