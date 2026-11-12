# demo-4 · SIFT筛网抓取 → 抬升230mm → 底盘转场 → DMP专机放置 → 回center

`demo_id: right_arm_sift_dmp_roundtrip_v1`，控制台别名 `demo-4-main-siftgrasp-dmpplace`。

## 链路

| 阶段 | 内容 | 实现来源 |
|---|---|---|
| 1 `pick` | 5700 ID6 识别 → cuRobo 预抓取 → 接近闭爪 → 连续抬升 230 mm → 保持 | **完全复用 demo3**：`scripts/prepare_sift_lift_hold.py` + `scripts/run_sift_lift_hold.py`（本 Demo 只编排） |
| 2 `transit` | 底盘 SIFT抓取站 → DMP抓取站，**先原地旋转到目标 yaw，再 BODY 相对平移** | `scripts/run_sift_dmp_roundtrip.py::stage_transit`，站位读 `config/manipulation_stations.json` |
| 3 `place` | 5700 抓取配置 ID2 检测 → 预放置点（检测点 + 偏移）→ cuRobo 规划 → 下降 60 mm → 松爪 | 复用 2026-11-02 的 DMP 放置实现（检测→预放置→下降→释放） |
| 4 `center` | 回全局 center 并做 `check_center` 验收 | `ares_r.manipulation.task_contract.center_goal` |

## 关键约定

- **站内偏移（`stages.dmp_place.preplace_offset_body_m`）**：默认 `[-0.020, -0.445, 0.100]`，即相对 5700 返回点的 x−20 mm / y−445 mm / z+100 mm。现场标定后用 `--preplace-offset` 覆盖即可。
- **下降量（`stages.dmp_place.descent_m`）**：默认 0.060 m，BODY −Z；执行后用 TCP 实测位移复核（±3 mm）。
- **偏航**：默认保持下发现场的 TCP yaw；`--yaw-deg` 可强行修正到指定 BODY yaw（末端 yaw 误差会被 `validate_level_path` 校验）。
- **硬水平门限**：`platform.level_tolerance_deg = 4.5`（任务合同上限）。cuRobo 轨迹倾斜超限会自动换模式并多轮重试（`platform.planning_rounds`）。
- **站位可改**：`config/manipulation_stations.json` 里 `SIFT-BLC-GRSP` 与 `DMP` 的 `slam_pose` 随时可重新登记；本 Demo 每次都读最新值，不做缓存。
- **场景策略**：转场/放置段 `AUTO_FRESH`（不逐段强扫），回 center 段 `FORCE_RESCAN`。
- **持物碰撞体**：默认不下发（`attach_payload_collision: false`）。若要开，可给 `attached_object_geometry`/`attached_object_revision`，且必须带 `point_ownership`，否则场景构建会 fail-closed（`ATTACHMENT_OWNERSHIP_TEMPLATE_REQUIRED`）。

## 运行

```bash
# 干跑（只做检测、规划、底盘预览，不动任何轴）
PYTHONPATH=src .venv/bin/python scripts/run_sift_dmp_roundtrip.py \
  --output worklog/evidence/demo-runs/right_arm_sift_dmp_roundtrip_v1/dry-$(date +%Y%m%d-%H%M%S) \
  --stage all

# 实机（每段各自授权，现场确认必填）
PYTHONPATH=src .venv/bin/python scripts/run_sift_dmp_roundtrip.py \
  --output worklog/evidence/demo-runs/right_arm_sift_dmp_roundtrip_v1/run-$(date +%Y%m%d-%H%M%S) \
  --stage all --execute --onsite-observer-confirmed

# 单段
PYTHONPATH=src .venv/bin/python scripts/run_sift_dmp_roundtrip.py --output <dir> --stage place --execute --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_sift_dmp_roundtrip.py --output <dir> --stage transit --execute --onsite-observer-confirmed
PYTHONPATH=src .venv/bin/python scripts/run_sift_dmp_roundtrip.py --output <dir> --stage center --execute --onsite-observer-confirmed
```

每段授权短语取自 `parameters.json`：

| 阶段 | 授权短语 |
|---|---|
| pick | `RIGHT SIFT PICK LIFT230 HOLD`（沿用 demo3） |
| transit | `MOVE BASE` |
| place / center | `RIGHT SCENE_AWARE SUPERVISED` |

## 安全约束（代码强制）

1. 必须 `--execute` **且** `--onsite-observer-confirmed`；
2. 每个输出目录只能派发一次（`demo-run.json` 一次写），防止重复下发；
3. 控制器 `errcode` / `emergency_stop` / `protective_stop` / `on_soft_limit` 未清零时拒绝任何运动；
4. 每次规划尝试都要求 `base_pose_revision` 不变，否则目标作废；
5. 目标碰撞用**当次最新扫描**在规划阶段判定（`INVALID_START_COLLISION` / `INVALID_GOAL_COLLISION` 会中止而不是绕过）；
6. 松爪前必须确认到位（预放置点 ±5 mm、下降位移 ±3 mm）；
7. 不清除任何控制器错误/保护停——需要人工确认后重跑；
8. 左臂（非作业臂）在每段执行前后做关节/工具一致性检查。

## 证据

每次运行在 `--output` 下产出：

```
01-sift-pick-lift230/   prepare.log, preparation.json, hold.log, hold-contract-copy.json
02-base-transit/        transit-contract.json, leg-N.json, transit-result.json
03-dmp-place/           detection.json, place-contract.json, plans.json,
                        preplace*.json, descend*.json, preplace-arrival.json,
                        descent-check.json, release.json
04-return-center/       center-goal.json, center-check.json
summary.json
```

## 已知限制

- 四段组合尚未完成端到端实机闭环（`commissioning_state: CANDIDATE_UNVERIFIED_NO_PHYSICAL_FULL_CYCLE`）；抓取抬升与 DMP 放置各自已有实机证据。
- 相机/5700 检测点会漂移（同工位不同批次 ±10 mm 量级），预放置点按当次检测结果计算，不复用历史坐标。
- 腕部自观测残影（`observed_remaining_observed_unknown_occupied_*`）偶尔会让起始位姿被判碰撞；此时需要人工把手臂挪开 30–50 mm 后重跑该段。
